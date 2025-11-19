from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import List, Optional
import sys
from pathlib import Path
import time
import aiofiles
import re
import requests
import asyncio
from contextlib import asynccontextmanager
import json
import aiohttp
import os
import unicodedata
import platform
from dotenv import load_dotenv
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.easyid3 import EasyID3
from mutagen.oggopus import OggOpus
from lyrics_client import lyrics_client

from api.auth import require_auth
from download_state import download_state_manager

load_dotenv()

sys.path.append(str(Path(__file__).parent.parent))

from tidal_client import TidalAPIClient
from troi_integration import TroiIntegration, TroiTrack

class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def log_success(msg: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_warning(msg: str):
    print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {msg}")

def log_info(msg: str):
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {msg}")

def log_step(step: str, msg: str):
    print(f"{Colors.MAGENTA}[{step}]{Colors.RESET} {msg}")

def fix_unicode(text: str) -> str:
    if not text:
        return text
    
    try:
        if '\\u' in text:
            text = text.encode('raw_unicode_escape').decode('unicode_escape')
    except:
        pass
    
    try:
        text = unicodedata.normalize('NFC', text)
    except:
        pass
    
    return text

def romanize_japanese(text: str) -> Optional[str]:
    if not text:
        return None
    
    has_japanese = any('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in text)
    
    if not has_japanese:
        return None
    
    try:
        import pykakasi
        kakasi = pykakasi.kakasi()
        result = kakasi.convert(text)
        romanized = ' '.join([item['hepburn'] for item in result])
        return romanized
    except ImportError:
        return None
    except Exception as e:
        log_warning(f"Romanization failed: {e}")
        return None

app = FastAPI(title="Troi Tidal Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tidal_client = TidalAPIClient()

class Settings(BaseSettings):
    music_dir: str = str(Path.home() / "music")
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    
    class Config:
        env_file = Path(__file__).parent.parent / ".env"
        case_sensitive = False

settings = Settings()

class TroiGenerateRequest(BaseModel):
    username: str
    playlist_type: str = "periodic-jams"

class TrackSearchResult(BaseModel):
    id: int
    title: str
    artist: str
    album: Optional[str] = None
    duration: Optional[int] = None
    cover: Optional[str] = None
    quality: Optional[str] = None

class TroiTrackResponse(BaseModel):
    title: str
    artist: str
    mbid: Optional[str]
    tidal_id: Optional[int]
    tidal_exists: bool
    album: Optional[str]

class DownloadTrackRequest(BaseModel):
    track_id: int
    artist: str
    title: str
    quality: str = "LOSSLESS"

DOWNLOAD_DIR = Path(settings.music_dir)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

print(f"Download directory: {DOWNLOAD_DIR}")

active_downloads = {}
troi_progress_queues = {}

MP3_QUALITY_MAP = {
    "MP3_128": 128,
    "MP3_256": 256,
}

OPUS_QUALITY_MAP = {
    "OPUS_192VBR": 192,
}

def extract_items(result, key: str) -> List:
    if not result:
        return []
    
    if isinstance(result, list):
        if len(result) > 0 and isinstance(result[0], dict):
            first_elem = result[0]
            if key in first_elem:
                nested = first_elem[key]
                if isinstance(nested, dict) and 'items' in nested:
                    return nested['items']
                elif isinstance(nested, list):
                    return nested
        return result
    
    if isinstance(result, dict):
        if key in result and isinstance(result[key], dict):
            return result[key].get('items', [])
        
        if 'items' in result:
            return result['items']
    
    return []

def extract_track_data(track_response) -> List:
    if not track_response:
        return []
    
    if isinstance(track_response, list):
        for item in track_response:
            if isinstance(item, dict) and 'items' in item:
                return item['items']
        return []
    
    if isinstance(track_response, dict):
        return track_response.get('items', [])
    
    return []

def extract_stream_url(track_data) -> Optional[str]:
    if isinstance(track_data, list):
        entries = track_data
    else:
        entries = [track_data]
    
    for entry in entries:
        if isinstance(entry, dict) and 'OriginalTrackUrl' in entry:
            return entry['OriginalTrackUrl']
    
    for entry in entries:
        if isinstance(entry, dict) and 'manifest' in entry:
            manifest = entry['manifest']
            try:
                import base64
                decoded = base64.b64decode(manifest).decode('utf-8')
                
                try:
                    import json
                    manifest_json = json.loads(decoded)
                    if 'urls' in manifest_json and manifest_json['urls']:
                        return manifest_json['urls'][0]
                except json.JSONDecodeError:
                    pass
                
                import re
                url_match = re.search(r'https?://[^\s"]+', decoded)
                if url_match:
                    return url_match.group(0)
            except Exception as e:
                log_error(f"Failed to decode manifest: {e}")
    
    return None

async def transcode_to_mp3(source_path: Path, target_path: Path, bitrate_kbps: int):
    try:
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source_path),
                    "-vn",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    f"{bitrate_kbps}k",
                    str(target_path),
                ],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                error_output = result.stderr if result.stderr else "Unknown error"
                raise Exception(f"FFmpeg failed: {error_output}")
        else:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                f"{bitrate_kbps}k",
                str(target_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_output = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"FFmpeg failed: {error_output}")
                
    except FileNotFoundError:
        raise Exception("ffmpeg not found. Please install ffmpeg and ensure it is on the PATH.")
    except Exception as e:
        raise Exception(f"Failed to transcode to MP3: {e}")
      
async def transcode_to_opus(source_path: Path, target_path: Path, bitrate_kbps: int):
  try:
    if platform.system() == "Windows":
      import subprocess
      result = subprocess.run(
        [
          "ffmpeg",
          "-y",
          "-i",
          str(source_path),
          "-vn",
          "-codec:a",
          "libopus",
          "-b:a",
          f"{bitrate_kbps}k",
          "-map_metadata",
          "0",
          str(target_path),
        ],
        capture_output=True,
        text=True
      )
      
      if result.returncode != 0:
        error_output = result.stderr if result.stderr else "Unknown error"
        raise Exception(f"FFmpeg failed: {error_output}")
    else:
      process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-codec:a",
        "libopus",
        "-b:a",
        f"{bitrate_kbps}k",
        "-map_metadata",
        "0",
        str(target_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
      )
      stdout, stderr = await process.communicate()

      if process.returncode != 0:
        error_output = stderr.decode() if stderr else "Unknown error"
        raise Exception(f"FFmpeg failed: {error_output}")
        
  except FileNotFoundError:
    raise Exception("ffmpeg not found. Please install ffmpeg and ensure it is on the PATH.")
  except Exception as e:
    raise Exception(f"Failed to transcode to Opus: {e}")

async def search_track_with_fallback(artist: str, title: str, track_obj) -> bool:
    artist_fixed = fix_unicode(artist)
    title_fixed = fix_unicode(title)
    
    log_info(f"Searching: {artist_fixed} - {title_fixed}")
    
    query = f"{artist_fixed} {title_fixed}"
    result = tidal_client.search_tracks(query)
    
    if result:
        tidal_tracks = extract_items(result, 'tracks')
        if tidal_tracks and len(tidal_tracks) > 0:
            first_track = tidal_tracks[0]
            track_obj.tidal_id = first_track.get('id')
            track_obj.tidal_exists = True
            
            album_data = first_track.get('album', {})
            track_obj.album = album_data.get('title') if isinstance(album_data, dict) else None
            
            log_success(f"Found on Tidal - ID: {track_obj.tidal_id}")
            return True
    
    romanized_title = romanize_japanese(title_fixed)
    romanized_artist = romanize_japanese(artist_fixed)
    
    if romanized_title or romanized_artist:
        search_artist = romanized_artist if romanized_artist else artist_fixed
        search_title = romanized_title if romanized_title else title_fixed
        
        log_info(f"Trying romanized: {search_artist} - {search_title}")
        
        query_romanized = f"{search_artist} {search_title}"
        result = tidal_client.search_tracks(query_romanized)
        
        if result:
            tidal_tracks = extract_items(result, 'tracks')
            if tidal_tracks and len(tidal_tracks) > 0:
                first_track = tidal_tracks[0]
                track_obj.tidal_id = first_track.get('id')
                track_obj.tidal_exists = True
                
                album_data = first_track.get('album', {})
                track_obj.album = album_data.get('title') if isinstance(album_data, dict) else None
                
                log_success(f"Found via romanization - ID: {track_obj.tidal_id}")
                return True
    
    log_error("Not found on Tidal")
    return False

@app.on_event("startup")
async def startup_event():
    tidal_client.cleanup_old_status_cache()
    download_state_manager._cleanup_old_entries()

async def download_file_async(track_id: int, stream_url: str, filepath: Path, filename: str, metadata: dict = None):
    processed_path = filepath
    try:
        log_step("3/4", f"Downloading {filename}...")
        
        if track_id not in active_downloads:
            active_downloads[track_id] = {'progress': 0, 'status': 'downloading'}
        
        download_state_manager.set_downloading(track_id, 0, metadata)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    log_error(f"Download failed: {error_msg}")
                    if track_id in active_downloads:
                        active_downloads[track_id] = {'progress': 0, 'status': 'failed'}
                        download_state_manager.set_failed(track_id, error_msg, metadata)
                        await asyncio.sleep(5)
                        del active_downloads[track_id]
                    return
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                active_downloads[track_id] = {
                                    'progress': progress,
                                    'status': 'downloading'
                                }
                                download_state_manager.update_progress(track_id, progress)
                                print(f"  Progress: {progress}%", end='\r')
                            
                            await asyncio.sleep(0.01)
        
        if metadata:
            if metadata.get('target_format') == 'mp3':
                bitrate = metadata.get('bitrate_kbps', 256)
                mp3_path = filepath.with_suffix('.mp3')
                log_step("3.5/4", f"Transcoding to MP3 ({bitrate} kbps)...")
                active_downloads[track_id] = {
                    'progress': 95,
                    'status': 'transcoding'
                }
                download_state_manager.update_progress(track_id, 95)
                await transcode_to_mp3(filepath, mp3_path, bitrate)
                processed_path = mp3_path
                metadata['file_ext'] = '.mp3'
                try:
                    filepath.unlink()
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    log_warning(f"Failed to remove intermediate file: {exc}")
            elif metadata.get('target_format') == 'opus':
                bitrate = metadata.get('bitrate_kbps', 192)
                opus_path = filepath.with_suffix('.opus')
                log_step("3.5/4", f"Transcoding to Opus ({bitrate} kbps)...")
                active_downloads[track_id] = {
                    'progress': 95,
                    'status': 'transcoding'
                }
                download_state_manager.update_progress(track_id, 95)
                await transcode_to_opus(filepath, opus_path, bitrate)
                processed_path = opus_path
                metadata['file_ext'] = '.opus'
                try:
                    filepath.unlink()
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    log_warning(f"Failed to remove intermediate file: {exc}")
            else:
                processed_path = filepath
                metadata.setdefault('file_ext', filepath.suffix)
        
        if metadata:
            log_step("4/4", "Writing metadata tags...")
            await write_metadata_tags(processed_path, metadata)
        
        final_path = await organize_file_by_metadata(processed_path, metadata)
        
        active_downloads[track_id] = {
            'progress': 100,
            'status': 'completed'
        }
        download_state_manager.set_completed(track_id, final_path.name, metadata)
        
        file_size_mb = final_path.stat().st_size / 1024 / 1024
        display_name = final_path.name if final_path else filename
        log_success(f"Downloaded: {display_name} ({file_size_mb:.2f} MB)")
        log_info(f"Location: {final_path}")
        print(f"{'='*60}\n")
        
        await asyncio.sleep(5)
        
        if track_id in active_downloads:
            del active_downloads[track_id]
        
    except Exception as e:
        log_error(f"Download error: {e}")
        import traceback
        traceback.print_exc()
        
        if track_id in active_downloads:
            active_downloads[track_id] = {'progress': 0, 'status': 'failed'}
            download_state_manager.set_failed(track_id, str(e), metadata)
            await asyncio.sleep(5)
            del active_downloads[track_id]
        
        if filepath.exists():
            try:
                filepath.unlink()
                log_info(f"Cleaned up partial file: {filename}")
            except Exception:
                pass
        
        if processed_path and processed_path != filepath and processed_path.exists():
            try:
                processed_path.unlink()
                log_info(f"Cleaned up partial file: {processed_path.name}")
            except Exception:
                pass

async def write_metadata_tags(filepath: Path, metadata: dict):
    try:
        with open(filepath, 'rb') as f:
            header = f.read(12)
        
        is_flac = header[:4] == b'fLaC'
        is_m4a = header[4:8] == b'ftyp' or header[4:12] == b'ftypM4A '
        is_mp3 = header[:3] == b'ID3' or filepath.suffix.lower() == '.mp3' or metadata.get('target_format') == 'mp3'
        is_opus = header[:4] == b'OggS' or filepath.suffix.lower() == '.opus' or metadata.get('target_format') == 'opus'
        
        quality = metadata.get('quality', 'UNKNOWN')
        
        if is_flac:
            log_info(f"File format: FLAC ({quality})")
            await write_flac_metadata(filepath, metadata)
        elif is_m4a:
            log_info(f"File format: M4A/AAC ({quality})")
            await write_m4a_metadata(filepath, metadata)
        elif is_mp3:
            log_info(f"File format: MP3 ({quality})")
            await write_mp3_metadata(filepath, metadata)
        elif is_opus:
            log_info(f"File format: Opus ({quality})")
            await write_opus_metadata(filepath, metadata)
        else:
            log_warning(f"Unknown file format, skipping metadata")
            log_info(f"Header: {header.hex()}")
        
    except Exception as e:
        log_warning(f"Failed to write metadata: {e}")
        import traceback
        traceback.print_exc()

async def write_flac_metadata(filepath: Path, metadata: dict):
    try:
        audio = FLAC(str(filepath))
        
        if metadata.get('title'):
            audio['TITLE'] = metadata['title']
        if metadata.get('artist'):
            audio['ARTIST'] = metadata['artist']
        if metadata.get('album'):
            audio['ALBUM'] = metadata['album']
        if metadata.get('album_artist'):
            audio['ALBUMARTIST'] = metadata['album_artist']
        if metadata.get('date'):
            audio['DATE'] = metadata['date']
        if metadata.get('track_number'):
            audio['TRACKNUMBER'] = str(metadata['track_number'])
        if metadata.get('total_tracks'):
            audio['TRACKTOTAL'] = str(metadata['total_tracks'])
        if metadata.get('disc_number'):
            audio['DISCNUMBER'] = str(metadata['disc_number'])
        if metadata.get('genre'):
            audio['GENRE'] = metadata['genre']
        
        if metadata.get('musicbrainz_trackid'):
            audio['MUSICBRAINZ_TRACKID'] = metadata['musicbrainz_trackid']
        if metadata.get('musicbrainz_albumid'):
            audio['MUSICBRAINZ_ALBUMID'] = metadata['musicbrainz_albumid']
        if metadata.get('musicbrainz_artistid'):
            audio['MUSICBRAINZ_ARTISTID'] = metadata['musicbrainz_artistid']
        if metadata.get('musicbrainz_albumartistid'):
            audio['MUSICBRAINZ_ALBUMARTISTID'] = metadata['musicbrainz_albumartistid']
        
        await fetch_and_store_lyrics(filepath, metadata, audio)
        
        if metadata.get('cover_url'):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(metadata['cover_url']) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            picture = Picture()
                            picture.type = 3
                            picture.mime = 'image/jpeg'
                            picture.desc = 'Cover'
                            picture.data = image_data
                            audio.add_picture(picture)
                            log_success("Added cover art")
            except Exception as e:
                log_warning(f"Failed to add cover art: {e}")
        
        audio.save()
        log_success("FLAC metadata tags written")
        
    except Exception as e:
        log_warning(f"Failed to write FLAC metadata: {e}")
        raise

async def write_m4a_metadata(filepath: Path, metadata: dict):
    try:
        audio = MP4(str(filepath))
        
        if metadata.get('title'):
            audio['\xa9nam'] = metadata['title']
        if metadata.get('artist'):
            audio['\xa9ART'] = metadata['artist']
        if metadata.get('album'):
            audio['\xa9alb'] = metadata['album']
        if metadata.get('album_artist'):
            audio['aART'] = metadata['album_artist']
        if metadata.get('date'):
            audio['\xa9day'] = metadata['date']
        if metadata.get('genre'):
            audio['\xa9gen'] = metadata['genre']
        
        if metadata.get('track_number'):
            track_num = metadata['track_number']
            total_tracks = metadata.get('total_tracks') or 0
            audio['trkn'] = [(track_num, total_tracks)]
        
        if metadata.get('disc_number'):
            disc_num = metadata['disc_number']
            audio['disk'] = [(disc_num, 0)]
        
        await fetch_and_store_lyrics(filepath, metadata, None)
        
        if metadata.get('cover_url'):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(metadata['cover_url']) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            audio['covr'] = [MP4Cover(image_data, imageformat=MP4Cover.FORMAT_JPEG)]
                            log_success("Added cover art")
            except Exception as e:
                log_warning(f"Failed to add cover art: {e}")
        
        audio.save()
        log_success("M4A metadata tags written")
        
    except Exception as e:
        log_warning(f"Failed to write M4A metadata: {e}")
        raise

async def write_mp3_metadata(filepath: Path, metadata: dict):
    try:
        audio = MP3(str(filepath), ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
            audio.save()
        
        try:
            tags = EasyID3(str(filepath))
        except ID3NoHeaderError:
            audio.add_tags()
            audio.save()
            tags = EasyID3(str(filepath))
        
        if metadata.get('title'):
            tags['title'] = metadata['title']
        if metadata.get('artist'):
            tags['artist'] = metadata['artist']
        if metadata.get('album'):
            tags['album'] = metadata['album']
        if metadata.get('album_artist'):
            tags['albumartist'] = metadata['album_artist']
        if metadata.get('genre'):
            tags['genre'] = metadata['genre']
        if metadata.get('date'):
            tags['date'] = metadata['date']
        if metadata.get('track_number'):
            track_num = metadata['track_number']
            total_tracks = metadata.get('total_tracks')
            if total_tracks:
                tags['tracknumber'] = f"{track_num}/{total_tracks}"
            else:
                tags['tracknumber'] = str(track_num)
        if metadata.get('disc_number'):
            disc_num = metadata['disc_number']
            total_discs = metadata.get('total_discs', 0)
            tags['discnumber'] = f"{disc_num}/{total_discs}" if total_discs else str(disc_num)
        
        tags.save()
        
        await fetch_and_store_lyrics(filepath, metadata, None)
        
        if metadata.get('cover_url'):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(metadata['cover_url']) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            audio = MP3(str(filepath), ID3=ID3)
                            if audio.tags is None:
                                audio.add_tags()
                            audio.tags.delall('APIC')
                            audio.tags.add(APIC(
                                encoding=3,
                                mime='image/jpeg',
                                type=3,
                                desc='Cover',
                                data=image_data
                            ))
                            audio.save()
                            log_success("Added cover art")
            except Exception as e:
                log_warning(f"Failed to add cover art: {e}")
        
        log_success("MP3 metadata tags written")
        
    except Exception as e:
        log_warning(f"Failed to write MP3 metadata: {e}")
        raise

async def write_opus_metadata(filepath: Path, metadata: dict):
    try:
        audio = OggOpus(str(filepath))
        
        if metadata.get('title'):
            audio['TITLE'] = metadata['title']
        if metadata.get('artist'):
            audio['ARTIST'] = metadata['artist']
        if metadata.get('album'):
            audio['ALBUM'] = metadata['album']
        if metadata.get('album_artist'):
            audio['ALBUMARTIST'] = metadata['album_artist']
        if metadata.get('date'):
            audio['DATE'] = metadata['date']
        if metadata.get('track_number'):
            audio['TRACKNUMBER'] = str(metadata['track_number'])
        if metadata.get('total_tracks'):
            audio['TRACKTOTAL'] = str(metadata['total_tracks'])
        if metadata.get('disc_number'):
            audio['DISCNUMBER'] = str(metadata['disc_number'])
        if metadata.get('genre'):
            audio['GENRE'] = metadata['genre']
        
        if metadata.get('musicbrainz_trackid'):
            audio['MUSICBRAINZ_TRACKID'] = metadata['musicbrainz_trackid']
        if metadata.get('musicbrainz_albumid'):
            audio['MUSICBRAINZ_ALBUMID'] = metadata['musicbrainz_albumid']
        if metadata.get('musicbrainz_artistid'):
            audio['MUSICBRAINZ_ARTISTID'] = metadata['musicbrainz_artistid']
        if metadata.get('musicbrainz_albumartistid'):
            audio['MUSICBRAINZ_ALBUMARTISTID'] = metadata['musicbrainz_albumartistid']
        
        await fetch_and_store_lyrics(filepath, metadata, audio)
        
        audio.save()
        log_success("Opus metadata tags written")
        
    except Exception as e:
        log_warning(f"Failed to write Opus metadata: {e}")
        raise

async def fetch_and_store_lyrics(filepath: Path, metadata: dict, audio_file=None):
    if metadata.get('title') and metadata.get('artist'):
        try:
            log_info("Fetching lyrics...")
            lyrics_result = await lyrics_client.get_lyrics(
                track_name=metadata['title'],
                artist_name=metadata['artist'],
                album_name=metadata.get('album'),
                duration=metadata.get('duration')
            )
            
            if lyrics_result:
                if lyrics_result.synced_lyrics:
                    metadata['synced_lyrics'] = lyrics_result.synced_lyrics
                    log_success("Synced lyrics found (will save to .lrc)")
                elif lyrics_result.plain_lyrics:
                    metadata['plain_lyrics'] = lyrics_result.plain_lyrics
                    log_success("Plain lyrics found (will save to .txt)")
                
        except Exception as e:
            log_warning(f"Failed to fetch lyrics: {e}")
        
        if audio_file and metadata.get('synced_lyrics'):
            try:
                lyrics_text = metadata['synced_lyrics']
                
                for i, line in enumerate(lyrics_text.split('\n')):
                    if line.strip():
                        audio_file[f'LYRICS_LINE_{i+1}'] = line.strip()
                
                log_success(f"Embedded {len(lyrics_text.splitlines())} lines of lyrics")
            except Exception as e:
                log_warning(f"Failed to embed lyrics: {e}")

def sanitize_path_component(name: str) -> str:
    if not name:
        return "Unknown"
    
    invalid_chars = r'<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')
    
    name = name.strip('. ')
    
    if len(name) > 200:
        name = name[:200].strip()
    
    return name or "Unknown"

async def organize_file_by_metadata(temp_filepath: Path, metadata: dict) -> Path:
    try:
        artist = metadata.get('album_artist') or metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        title = metadata.get('title', temp_filepath.stem)
        track_number = metadata.get('track_number')
        file_ext = metadata.get('file_ext')
        if not file_ext:
            file_ext = temp_filepath.suffix or '.flac'
        file_ext = file_ext if file_ext.startswith('.') else f".{file_ext}"
        
        artist_folder = sanitize_path_component(artist)
        album_folder = sanitize_path_component(album)
        
        if track_number:
            track_str = str(track_number).zfill(2)
            filename = f"{track_str} - {sanitize_path_component(title)}{file_ext}"
        else:
            filename = f"{sanitize_path_component(title)}{file_ext}"
        
        final_dir = DOWNLOAD_DIR / artist_folder / album_folder
        final_path = final_dir / filename
        
        final_dir.mkdir(parents=True, exist_ok=True)
        
        if final_path.exists():
            log_warning(f"File already exists at: {final_path}")
            if temp_filepath.exists() and temp_filepath != final_path:
                temp_filepath.unlink()
                temp_lrc = temp_filepath.with_suffix('.lrc')
                if temp_lrc.exists():
                    temp_lrc.unlink()
                temp_txt = temp_filepath.with_suffix('.txt')
                if temp_txt.exists():
                    temp_txt.unlink()
            return final_path
        
        if temp_filepath != final_path:
            import shutil
            shutil.move(str(temp_filepath), str(final_path))
            log_success(f"Organized to: {artist_folder}/{album_folder}/{filename}")
            
            temp_lrc_path = temp_filepath.with_suffix('.lrc')
            if temp_lrc_path.exists():
                final_lrc_path = final_path.with_suffix('.lrc')
                shutil.move(str(temp_lrc_path), str(final_lrc_path))
                log_success("Moved .lrc file to organized location")
            
            temp_txt_path = temp_filepath.with_suffix('.txt')
            if temp_txt_path.exists():
                final_txt_path = final_path.with_suffix('.txt')
                shutil.move(str(temp_txt_path), str(final_txt_path))
                log_success("Moved .txt file to organized location")
        
        if metadata.get('synced_lyrics') and metadata.get('target_format') != 'opus':
            lrc_path = final_path.with_suffix('.lrc')
            try:
                with open(lrc_path, 'w', encoding='utf-8') as f:
                    f.write(metadata['synced_lyrics'])
                log_success("Saved synced lyrics to .lrc file")
            except Exception as e:
                log_warning(f"Failed to save .lrc file: {e}")
        
        elif metadata.get('plain_lyrics') and metadata.get('target_format') != 'opus':
            txt_path = final_path.with_suffix('.txt')
            try:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(metadata['plain_lyrics'])
                log_success("Saved plain lyrics to .txt file")
            except Exception as e:
                log_warning(f"Failed to save .txt file: {e}")
        
        if metadata.get('target_format') == 'opus' and metadata.get('cover_url'):
            cover_path = final_dir / 'cover.jpg'
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(metadata['cover_url']) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            with open(cover_path, 'wb') as f:
                                f.write(image_data)
                            log_success("Saved cover art to cover.jpg")
            except Exception as e:
                log_warning(f"Failed to save cover art: {e}")
        
        return final_path
        
    except Exception as e:
        log_warning(f"Failed to organize file: {e}")
        import traceback
        traceback.print_exc()
        return temp_filepath

@app.get("/api")
async def api_root():
    return {"status": "ok", "message": "Troi Tidal Downloader API"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/troi/generate")
async def generate_troi_playlist(
    request: TroiGenerateRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(require_auth)
):
    import uuid
    progress_id = str(uuid.uuid4())
    
    background_tasks.add_task(
        troi_generate_with_progress,
        request.username,
        request.playlist_type,
        progress_id
    )
    
    return {"progress_id": progress_id}

async def troi_generate_with_progress(username: str, playlist_type: str, progress_id: str):
    queue = asyncio.Queue()
    troi_progress_queues[progress_id] = queue
    
    try:
        await queue.put({
            "type": "info",
            "message": f"Generating Troi playlist for {username}...",
            "progress": 0,
            "total": 0
        })
        
        tracks = TroiIntegration.generate_playlist(username, playlist_type)
        
        for track in tracks:
            track.title = fix_unicode(track.title)
            track.artist = fix_unicode(track.artist)
            if track.album:
                track.album = fix_unicode(track.album)
        
        await queue.put({
            "type": "info",
            "message": f"Generated {len(tracks)} tracks from Troi",
            "progress": 0,
            "total": len(tracks)
        })
        
        validated_tracks = []
        for i, track in enumerate(tracks, 1):
            display_text = f"{track.artist} - {track.title}"
            
            await queue.put({
                "type": "validating",
                "message": f"Validating: {display_text}",
                "progress": i,
                "total": len(tracks),
                "current_track": {
                    "artist": track.artist,
                    "title": track.title
                }
            })
            
            log_info(f"[{i}/{len(tracks)}] Validating: {display_text}")
            
            await search_track_with_fallback(track.artist, track.title, track)
            
            validated_tracks.append({
                "title": track.title,
                "artist": track.artist,
                "mbid": track.mbid,
                "tidal_id": track.tidal_id,
                "tidal_exists": track.tidal_exists,
                "album": track.album
            })
            
            await asyncio.sleep(0.1)
        
        found_count = sum(1 for t in validated_tracks if t.get("tidal_exists"))
        
        log_info(f"Validation complete: {found_count}/{len(validated_tracks)} found on Tidal")
        
        await queue.put({
            "type": "complete",
            "message": f"Validation complete: {found_count}/{len(validated_tracks)} found on Tidal",
            "progress": len(tracks),
            "total": len(tracks),
            "tracks": validated_tracks,
            "found_count": found_count
        })
        
    except Exception as e:
        log_error(f"Troi generation error: {str(e)}")
        await queue.put({
            "type": "error",
            "message": str(e),
            "progress": 0,
            "total": 0
        })
    finally:
        await queue.put(None)

@app.get("/api/troi/progress/{progress_id}")
async def troi_progress_stream(
    progress_id: str,
    username: str = Depends(require_auth)
):
    async def event_generator():
        if progress_id not in troi_progress_queues:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid progress ID'})}\n\n"
            return
        
        queue = troi_progress_queues[progress_id]
        
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    if message is None:
                        break
                    
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                    
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    
        finally:
            if progress_id in troi_progress_queues:
                del troi_progress_queues[progress_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8"
        }
    )

@app.get("/api/search/tracks")
async def search_tracks(q: str, username: str = Depends(require_auth)):
    try:
        result = tidal_client.search_tracks(q)
        
        if not result:
            return {"items": []}
        
        tracks = extract_items(result, 'tracks')
        
        return {
            "items": [
                TrackSearchResult(
                    id=track['id'],
                    title=track['title'],
                    artist=track.get('artist', {}).get('name', 'Unknown'),
                    album=track.get('album', {}).get('title'),
                    duration=track.get('duration'),
                    cover=track.get('album', {}).get('cover'),
                    quality=track.get('audioQuality')
                )
                for track in tracks
            ]
        }
    except Exception as e:
        log_error(f"Error searching tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/albums")
async def search_albums(q: str, username: str = Depends(require_auth)):
    try:
        result = tidal_client.search_albums(q)
        
        if not result:
            return {"items": []}
        
        albums = extract_items(result, 'albums')
        
        return {"items": albums}
    except Exception as e:
        log_error(f"Error searching albums: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/artists")
async def search_artists(q: str, username: str = Depends(require_auth)):
    try:
        log_info(f"Searching for artist: {q}")
        result = tidal_client.search_artists(q)
        
        if not result:
            log_info("No results from API")
            return {"items": []}
        
        log_info(f"API response type: {type(result)}")
        
        artists = extract_items(result, 'artists')
        
        log_info(f"Found {len(artists)} artists")
        if artists:
            log_info(f"First artist: {artists[0].get('name', 'Unknown')} (ID: {artists[0].get('id')})")
        
        return {"items": artists}
    except Exception as e:
        log_error(f"Error searching artists: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/album/{album_id}/tracks")
async def get_album_tracks(album_id: int, username: str = Depends(require_auth)):
    try:
        log_info(f"Fetching tracks for album {album_id}...")
        result = tidal_client.get_album(album_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Album not found")
        
        log_info(f"Album API response type: {type(result)}")
        
        album_metadata = None
        raw_items = []
        
        if isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], dict):
                if 'title' in result[0] and 'id' in result[0]:
                    album_metadata = result[0]
            
            for item in result:
                if isinstance(item, dict) and 'items' in item:
                    raw_items = item['items']
                    break
        elif isinstance(result, dict):
            if 'items' in result:
                raw_items = result['items']
            if 'title' in result and 'id' in result:
                album_metadata = result
        
        log_info(f"Found album metadata: {album_metadata is not None}")
        log_info(f"Found {len(raw_items)} raw items")
        
        tracks = []
        for raw_item in raw_items:
            if not raw_item or not isinstance(raw_item, dict):
                continue
            
            track_data = raw_item.get('item', raw_item)
            
            if not isinstance(track_data, dict):
                continue
            
            if album_metadata:
                if 'album' not in track_data or not track_data['album']:
                    track_data['album'] = album_metadata
                elif isinstance(track_data.get('album'), dict):
                    track_data['album'] = {
                        **album_metadata,
                        **track_data['album']
                    }
            
            tracks.append(track_data)
        
        log_info(f"Extracted {len(tracks)} tracks")
        
        track_results = []
        for track in tracks:
            try:
                track_id = track.get('id')
                if not track_id:
                    log_warning(f"Track missing ID: {track.get('title', 'Unknown')}")
                    continue
                
                artist_name = "Unknown"
                if 'artist' in track:
                    if isinstance(track['artist'], dict):
                        artist_name = track['artist'].get('name', 'Unknown')
                    elif isinstance(track['artist'], str):
                        artist_name = track['artist']
                elif 'artists' in track and track['artists']:
                    first_artist = track['artists'][0]
                    if isinstance(first_artist, dict):
                        artist_name = first_artist.get('name', 'Unknown')
                
                album_dict = track.get('album')
                if isinstance(album_dict, dict):
                    album_title = album_dict.get('title')
                    album_cover = album_dict.get('cover')
                else:
                    album_title = None
                    album_cover = None
                
                track_results.append(TrackSearchResult(
                    id=track_id,
                    title=track.get('title', 'Unknown'),
                    artist=artist_name,
                    album=album_title,
                    duration=track.get('duration'),
                    cover=album_cover or track.get('cover'),
                    quality=track.get('audioQuality')
                ))
            except Exception as e:
                log_error(f"Error processing track: {e}")
                continue
        
        log_info(f"Successfully processed {len(track_results)} tracks")
        
        response_data = {"items": track_results}
        
        if album_metadata:
            response_data["album"] = {
                "id": album_metadata.get('id'),
                "title": album_metadata.get('title'),
                "cover": album_metadata.get('cover'),
                "artist": album_metadata.get('artist'),
                "releaseDate": album_metadata.get('releaseDate'),
                "numberOfTracks": album_metadata.get('numberOfTracks'),
                "numberOfVolumes": album_metadata.get('numberOfVolumes'),
            }
            log_info(f"Including album metadata: {album_metadata.get('title')}")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting album tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/artist/{artist_id}")
async def get_artist(artist_id: int, username: str = Depends(require_auth)):
    try:
        log_info(f"Fetching artist {artist_id}...")
        result = tidal_client.get_artist(artist_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Artist not found")
        
        log_info(f"Artist API response type: {type(result)}")
        
        artist_data = None
        tracks = []
        albums = []
        visited = set()
        
        def is_track_like(obj):
            if not isinstance(obj, dict):
                return False
            return all(key in obj for key in ['id', 'title', 'duration']) and 'album' in obj
        
        def is_album_like(obj):
            if not isinstance(obj, dict):
                return False
            return all(key in obj for key in ['id', 'title', 'cover'])
        
        def is_artist_like(obj):
            if not isinstance(obj, dict):
                return False
            return all(key in obj for key in ['id', 'name', 'type'])
        
        def scan_value(value, depth=0):
            if depth > 10:
                return
            
            if not value:
                return
            
            if isinstance(value, list):
                for item in value:
                    scan_value(item, depth + 1)
                return
            
            if not isinstance(value, dict):
                return
            
            obj_id = id(value)
            if obj_id in visited:
                return
            visited.add(obj_id)
            
            if is_artist_like(value):
                nonlocal artist_data
                if not artist_data:
                    artist_data = value
            
            if 'items' in value and isinstance(value['items'], list):
                for item in value['items']:
                    if not isinstance(item, dict):
                        continue
                    
                    actual_item = item.get('item', item)
                    
                    if is_track_like(actual_item):
                        tracks.append(actual_item)
                    elif is_album_like(actual_item):
                        albums.append(actual_item)
            
            if 'modules' in value and isinstance(value['modules'], list):
                for module in value['modules']:
                    if isinstance(module, dict):
                        if 'pagedList' in module:
                            paged_list = module['pagedList']
                            if isinstance(paged_list, dict):
                                scan_value(paged_list, depth + 1)
                        
                        scan_value(module, depth + 1)
            
            for nested_value in value.values():
                scan_value(nested_value, depth + 1)
        
        scan_value(result)
        
        if not artist_data:
            if tracks and 'artist' in tracks[0]:
                artist_obj = tracks[0]['artist']
                if isinstance(artist_obj, dict):
                    artist_data = artist_obj
            elif albums and 'artist' in albums[0]:
                artist_obj = albums[0]['artist']
                if isinstance(artist_obj, dict):
                    artist_data = artist_obj
        
        if not artist_data:
            artist_data = {
                'id': artist_id,
                'name': 'Unknown Artist'
            }
        
        tracks_sorted = sorted(
            tracks,
            key=lambda t: t.get('popularity', 0),
            reverse=True
        )[:50]
        
        def get_album_timestamp(album):
            release_date = album.get('releaseDate')
            if not release_date:
                return 0
            try:
                from datetime import datetime
                return datetime.fromisoformat(release_date.replace('Z', '+00:00')).timestamp()
            except:
                return 0
        
        albums_sorted = sorted(
            albums,
            key=get_album_timestamp,
            reverse=True
        )
        
        log_info(f"Found: {len(tracks_sorted)} tracks, {len(albums_sorted)} albums")
        if tracks_sorted:
            log_info(f"Sample track: {tracks_sorted[0].get('title', 'Unknown')}")
        if albums_sorted:
            log_info(f"Sample album: {albums_sorted[0].get('title', 'Unknown')}")
        
        return {
            "artist": artist_data,
            "tracks": tracks_sorted,
            "albums": albums_sorted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting artist: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/start")
async def start_download(
    background_tasks: BackgroundTasks,
    username: str = Depends(require_auth)
):
    return {"status": "started"}

@app.get("/api/download/stream/{track_id}")
async def get_stream_url(
    track_id: int,
    quality: str = "LOSSLESS",
    username: str = Depends(require_auth)
):
    try:
        log_info(f"Getting stream URL for track {track_id} at {quality} quality...")
        
        track_data = tidal_client.get_track(track_id, quality)
        
        if not track_data:
            raise HTTPException(status_code=404, detail="Track not found")
        
        stream_url = extract_stream_url(track_data)
        
        if not stream_url:
            raise HTTPException(status_code=404, detail="Stream URL not found")
        
        log_info(f"Found stream URL: {stream_url[:50]}...")
        
        return {
            "stream_url": stream_url,
            "track_id": track_id,
            "quality": quality
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting stream URL: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/state")
async def get_download_states(username: str = Depends(require_auth)):
    return {
        "active": download_state_manager.get_all_active(),
        "completed": download_state_manager.get_all_completed(),
        "failed": download_state_manager.get_all_failed()
    }

@app.get("/api/download/progress/{track_id}")
async def download_progress_stream(
    track_id: int,
    username: str = Depends(require_auth)
):
    async def event_generator():
        last_progress = -1
        no_data_count = 0
        max_no_data = 60
        
        saved_state = download_state_manager.get_download_state(track_id)
        if saved_state:
            progress = saved_state.get('progress', 0)
            status = saved_state['status']
            yield f"data: {json.dumps({'progress': progress, 'track_id': track_id, 'status': status})}\n\n"
            
            if status == 'completed':
                yield f"data: {json.dumps({'progress': 100, 'track_id': track_id, 'status': 'completed'})}\n\n"
                return
            elif status == 'failed':
                error = saved_state.get('error', 'Download failed')
                yield f"data: {json.dumps({'progress': 0, 'track_id': track_id, 'status': 'failed', 'error': error})}\n\n"
                return
        
        try:
            while True:
                current_progress = -1
                current_status = 'unknown'
                
                if track_id in active_downloads:
                    download_info = active_downloads[track_id]
                    current_progress = download_info.get('progress', 0)
                    current_status = download_info.get('status', 'downloading')
                else:
                    saved_state = download_state_manager.get_download_state(track_id)
                    if saved_state:
                        current_progress = saved_state.get('progress', 0)
                        current_status = saved_state['status']
                    else:
                        no_data_count += 1
                
                if current_progress != last_progress or current_status != 'unknown':
                    if current_status != 'unknown':
                        yield f"data: {json.dumps({'progress': current_progress, 'track_id': track_id, 'status': current_status})}\n\n"
                        last_progress = current_progress
                        no_data_count = 0
                    
                    if current_progress >= 100 or current_status == 'completed':
                        yield f"data: {json.dumps({'progress': 100, 'track_id': track_id, 'status': 'completed'})}\n\n"
                        return
                    
                    if current_status == 'failed':
                        yield f"data: {json.dumps({'progress': 0, 'track_id': track_id, 'status': 'failed'})}\n\n"
                        return
                
                if no_data_count >= max_no_data:
                    yield f"data: {json.dumps({'progress': 0, 'track_id': track_id, 'status': 'not_found'})}\n\n"
                    return
                
                await asyncio.sleep(0.5)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_error(f"Progress stream error for track {track_id}: {e}")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/download/track")
async def download_track_server_side(
    request: DownloadTrackRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(require_auth)
):
    try:
        # Check if download is already in progress
        if request.track_id in active_downloads:
            current_status = active_downloads[request.track_id].get('status')
            if current_status in ['starting', 'downloading', 'transcoding']:
                log_warning(f"Download already in progress for track {request.track_id}")
                return {
                    "status": "downloading",
                    "filename": "In progress",
                    "message": "Download already in progress"
                }
        
        # Check download state manager
        saved_state = download_state_manager.get_download_state(request.track_id)
        if saved_state:
            if saved_state['status'] == 'downloading':
                log_warning(f"Download in state manager for track {request.track_id}")
                # Re-register in active_downloads
                active_downloads[request.track_id] = {
                    'progress': saved_state.get('progress', 0),
                    'status': 'downloading'
                }
                return {
                    "status": "downloading",
                    "filename": "In progress",
                    "message": "Download already in progress"
                }
            elif saved_state['status'] == 'completed':
                log_warning(f"Track {request.track_id} already completed")
                return {
                    "status": "exists",
                    "filename": saved_state.get('metadata', {}).get('title', 'Completed'),
                    "message": "Download already completed"
                }
        
        print(f"\n{'='*60}")
        print(f"Download Request:")
        print(f"  Track ID: {request.track_id}")
        print(f"  Artist: {request.artist}")
        print(f"  Title: {request.title}")
        print(f"  Quality: {request.quality}")
        print(f"{'='*60}\n")
        
        requested_quality = request.quality.upper() if request.quality else "LOSSLESS"
        
        # Mark as starting immediately
        active_downloads[request.track_id] = {
            'progress': 0,
            'status': 'starting'
        }
        
        log_step("1/4", "Getting track metadata...")
        
        is_mp3_request = requested_quality in MP3_QUALITY_MAP
        is_opus_request = requested_quality in OPUS_QUALITY_MAP
        source_quality = 'LOSSLESS' if is_mp3_request or is_opus_request else requested_quality
        
        track_info = tidal_client.get_track(request.track_id, source_quality)
        if not track_info:
            del active_downloads[request.track_id]
            raise HTTPException(status_code=404, detail="Track not found")
        
        metadata = {
            'quality': requested_quality,
            'source_quality': source_quality
        }
        
        if is_mp3_request:
            metadata['target_format'] = 'mp3'
            metadata['bitrate_kbps'] = MP3_QUALITY_MAP[requested_quality]
            metadata['quality_label'] = requested_quality
        elif is_opus_request:
            metadata['target_format'] = 'opus'
            metadata['bitrate_kbps'] = OPUS_QUALITY_MAP[requested_quality]
            metadata['quality_label'] = requested_quality
        
        if isinstance(track_info, list) and len(track_info) > 0:
            track_data = track_info[0]
        else:
            track_data = track_info
        
        if isinstance(track_data, dict):
            metadata['title'] = track_data.get('title', request.title)
            metadata['track_number'] = track_data.get('trackNumber')
            metadata['disc_number'] = track_data.get('volumeNumber')
            metadata['date'] = track_data.get('streamStartDate', '').split('T')[0] if track_data.get('streamStartDate') else None
            metadata['duration'] = track_data.get('duration')
            
            artist_data = track_data.get('artist', {})
            if isinstance(artist_data, dict):
                metadata['artist'] = artist_data.get('name', request.artist)
                metadata['musicbrainz_artistid'] = artist_data.get('mixes')
            else:
                metadata['artist'] = request.artist
            
            album_data = track_data.get('album', {})
            if isinstance(album_data, dict):
                metadata['album'] = album_data.get('title')
                metadata['album_artist'] = album_data.get('artist', {}).get('name') if isinstance(album_data.get('artist'), dict) else None
                metadata['total_tracks'] = album_data.get('numberOfTracks')
                metadata['total_discs'] = album_data.get('numberOfVolumes')
                
                cover_id = album_data.get('cover')
                if cover_id:
                    cover_id_str = str(cover_id).replace('-', '/')
                    metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
        
        log_success(f"Track metadata: {metadata.get('artist')} - {metadata.get('title')}")
        if metadata.get('album'):
            log_info(f"Album: {metadata.get('album')}")
        
        log_step("2/4", f"Getting stream URL ({source_quality})...")
        stream_url = extract_stream_url(track_info)
        if not stream_url:
            del active_downloads[request.track_id]
            raise HTTPException(status_code=404, detail="Stream URL not found")
        
        log_success(f"Stream URL: {stream_url[:60]}...")
        
        download_ext = '.m4a' if source_quality in ['LOW', 'HIGH'] else '.flac'
        if is_mp3_request:
            final_ext = '.mp3'
        elif is_opus_request:
            final_ext = '.opus'
        else:
            final_ext = download_ext
        metadata['file_ext'] = final_ext
        metadata['download_ext'] = download_ext
        
        temp_download_name = f"{request.artist} - {request.title}{download_ext}"
        temp_download_name = re.sub(r'[<>:"/\\|?*]', '_', temp_download_name)
        temp_filepath = DOWNLOAD_DIR / temp_download_name
        
        artist = metadata.get('album_artist') or metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        title = metadata.get('title', request.title)
        track_number = metadata.get('track_number')
        
        artist_folder = sanitize_path_component(artist)
        album_folder = sanitize_path_component(album)
        
        if track_number:
            track_str = str(track_number).zfill(2)
            final_filename = f"{track_str} - {sanitize_path_component(title)}{final_ext}"
        else:
            final_filename = f"{sanitize_path_component(title)}{final_ext}"
        
        final_filepath = DOWNLOAD_DIR / artist_folder / album_folder / final_filename
        
        log_step("3/4", f"Target file: {final_filepath}")
        
        if final_filepath.exists():
            log_warning("File already exists, skipping download")
            del active_downloads[request.track_id]
            download_state_manager.set_completed(request.track_id, final_filename, metadata)
            return {
                "status": "exists",
                "filename": final_filename,
                "path": str(final_filepath),
                "message": f"File already exists: {artist_folder}/{album_folder}/{final_filename}"
            }
        
        active_downloads[request.track_id] = {
            'progress': 0,
            'status': 'downloading'
        }
        
        background_tasks.add_task(
            download_file_async,
            request.track_id,
            stream_url,
            temp_filepath,
            final_filename,
            metadata
        )
        
        return {
            "status": "downloading",
            "filename": final_filename,
            "path": str(final_filepath),
            "message": f"Download started: {artist_folder}/{album_folder}/{final_filename}"
        }
        
    except HTTPException:
        if request.track_id in active_downloads:
            del active_downloads[request.track_id]
        raise
    except Exception as e:
        log_error(f"Download error: {e}")
        traceback.print_exc()
        
        if request.track_id in active_downloads:
            del active_downloads[request.track_id]
        
        raise HTTPException(status_code=500, detail=str(e))

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        
        raise HTTPException(status_code=404, detail="Frontend not built")
else:
    log_warning("Frontend dist folder not found. Run 'npm run build' in frontend directory.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)