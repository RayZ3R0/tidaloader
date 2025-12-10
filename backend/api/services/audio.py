import platform
import asyncio
from pathlib import Path
import aiohttp

from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.easyid3 import EasyID3
from mutagen.oggopus import OggOpus

from api.utils.logging import log_info, log_success, log_warning
from api.services.lyrics import fetch_and_store_lyrics

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

async def write_metadata_tags(filepath: Path, metadata: dict):
    try:
        with open(filepath, 'rb') as f:
            header = f.read(12)
        
        is_flac = header[:4] == b'fLaC'
        is_m4a = header[4:8] == b'ftyp' or header[4:12] == b'ftypM4A '
        is_mp3 = header[:3] == b'ID3' or filepath.suffix.lower() == '.mp3' or metadata.get('target_format') == 'mp3'
        is_opus = header[:4] == b'OggS' or filepath.suffix.lower() == '.opus' or metadata.get('target_format') == 'opus'
        
        quality = metadata.get('quality', 'UNKNOWN')
        
        log_info(f"Writing metadata for {filepath.name}")
        log_info(f"  Tidal IDs present: Track={bool(metadata.get('tidal_track_id'))}, Album={bool(metadata.get('tidal_album_id'))}, Artist={bool(metadata.get('tidal_artist_id'))}")
        if metadata.get('tidal_track_id'):
             log_info(f"  Writing TIDAL_TRACK_ID: {metadata['tidal_track_id']}")

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

        # Custom Tidal Tags
        if metadata.get('tidal_track_id'):
            audio['TIDAL_TRACK_ID'] = metadata['tidal_track_id']
        if metadata.get('tidal_artist_id'):
            audio['TIDAL_ARTIST_ID'] = metadata['tidal_artist_id']
        if metadata.get('tidal_album_id'):
            audio['TIDAL_ALBUM_ID'] = metadata['tidal_album_id']
        
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

        # Custom Tidal Tags (Freeform)
        if metadata.get('tidal_track_id'):
            audio['----:com.apple.iTunes:TIDAL_TRACK_ID'] = metadata['tidal_track_id'].encode('utf-8')
        if metadata.get('tidal_artist_id'):
            audio['----:com.apple.iTunes:TIDAL_ARTIST_ID'] = metadata['tidal_artist_id'].encode('utf-8')
        if metadata.get('tidal_album_id'):
            audio['----:com.apple.iTunes:TIDAL_ALBUM_ID'] = metadata['tidal_album_id'].encode('utf-8')
        
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
            total_discs = metadata.get('total_discs', 0)
            tags['discnumber'] = f"{disc_num}/{total_discs}" if total_discs else str(disc_num)
        
        # Custom Tidal Tags (TXXX)
        if metadata.get('tidal_track_id'):
            tags['TXXX:TIDAL_TRACK_ID'] = metadata['tidal_track_id']
        if metadata.get('tidal_artist_id'):
            tags['TXXX:TIDAL_ARTIST_ID'] = metadata['tidal_artist_id']
        if metadata.get('tidal_album_id'):
            tags['TXXX:TIDAL_ALBUM_ID'] = metadata['tidal_album_id']
        
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

        # Custom Tidal Tags
        if metadata.get('tidal_track_id'):
            audio['TIDAL_TRACK_ID'] = metadata['tidal_track_id']
        if metadata.get('tidal_artist_id'):
            audio['TIDAL_ARTIST_ID'] = metadata['tidal_artist_id']
        if metadata.get('tidal_album_id'):
            audio['TIDAL_ALBUM_ID'] = metadata['tidal_album_id']
        
        await fetch_and_store_lyrics(filepath, metadata, audio)
        
        audio.save()
        log_success("Opus metadata tags written")
        
    except Exception as e:
        log_warning(f"Failed to write Opus metadata: {e}")
        raise
