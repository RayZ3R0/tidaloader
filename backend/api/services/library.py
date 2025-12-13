
import os
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4

from api.settings import DOWNLOAD_DIR

logger = logging.getLogger(__name__)

class LibraryService:
    def __init__(self):
        self.cache_file = Path(__file__).parent.parent / ".cache" / "library_cache.json"
        self.cache_file.parent.mkdir(exist_ok=True)
        self.library_data = self._load_cache()

    def _load_cache(self) -> Dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"artists": {}, "timestamp": 0}

    def _save_cache(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.library_data, f)
        except Exception as e:
            logger.error(f"Failed to save library cache: {e}")

    def _get_file_metadata(self, filepath: Path) -> Optional[Dict]:
        try:
            ext = filepath.suffix.lower()
            tags = {}
            
            if ext == '.mp3':
                try:
                    audio = EasyID3(filepath)
                    tags = audio
                except mutagen.id3.ID3NoHeaderError:
                    audio = mutagen.File(filepath, easy=True)
                    tags = audio or {}
            elif ext == '.flac':
                audio = FLAC(filepath)
                tags = audio
            elif ext == '.m4a':
                audio = MP4(filepath)
                # MP4 tags need mapping
                raw_tags = audio.tags or {}
                tags = {
                    'artist': raw_tags.get('\xa9ART', [None])[0],
                    'album': raw_tags.get('\xa9alb', [None])[0],
                    'title': raw_tags.get('\xa9nam', [None])[0],
                    'date': raw_tags.get('\xa9day', [None])[0],
                    'tracknumber': raw_tags.get('trkn', [(None, None)])[0][0],
                    'discnumber': raw_tags.get('disk', [(None, None)])[0][0],
                    'tidal_artist_id': (raw_tags.get('----:com.apple.iTunes:TIDAL_ARTIST_ID', [b''])[0]).decode('utf-8', errors='ignore') or None,
                    'tidal_album_id': (raw_tags.get('----:com.apple.iTunes:TIDAL_ALBUM_ID', [b''])[0]).decode('utf-8', errors='ignore') or None,
                    'tidal_track_id': (raw_tags.get('----:com.apple.iTunes:TIDAL_TRACK_ID', [b''])[0]).decode('utf-8', errors='ignore') or None,
                }
            elif ext == '.opus':
                audio = mutagen.File(filepath)
                tags = audio or {}
            
            # Normalize tags
            artist = tags.get('artist', ['Unknown Artist'])
            album = tags.get('album', ['Unknown Album'])
            title = tags.get('title', [filepath.stem])
            date = tags.get('date', [''])
            track_num = tags.get('tracknumber', [None])
            disc_num = tags.get('discnumber', [None])
            
            # Extract Tidal IDs (FLAC/Vorbis use uppercase, MP3/ID3 use TXXX)
            tidal_artist_id = tags.get('TIDAL_ARTIST_ID') or tags.get('TXXX:TIDAL_ARTIST_ID') or tags.get('tidal_artist_id')
            tidal_album_id = tags.get('TIDAL_ALBUM_ID') or tags.get('TXXX:TIDAL_ALBUM_ID') or tags.get('tidal_album_id')
            tidal_track_id = tags.get('TIDAL_TRACK_ID') or tags.get('TXXX:TIDAL_TRACK_ID') or tags.get('tidal_track_id')

            # Handle list returns from mutagen
            if isinstance(artist, list): artist = artist[0]
            if isinstance(album, list): album = album[0]
            if isinstance(title, list): title = title[0]
            if isinstance(date, list): date = date[0]
            if isinstance(track_num, list): track_num = track_num[0]
            if isinstance(track_num, list): track_num = track_num[0]
            if isinstance(disc_num, list): disc_num = disc_num[0]
            if isinstance(tidal_artist_id, list): tidal_artist_id = tidal_artist_id[0]
            if isinstance(tidal_album_id, list): tidal_album_id = tidal_album_id[0]
            if isinstance(tidal_track_id, list): tidal_track_id = tidal_track_id[0]
            
            # Clean up track numbers (e.g. "1/10")
            if track_num and isinstance(track_num, str) and '/' in track_num:
                track_num = track_num.split('/')[0]

            return {
                'artist': artist or "Unknown Artist",
                'album': album or "Unknown Album",
                'title': title or filepath.stem,
                'year': str(date)[:4] if date else "",
                'track_number': int(track_num) if track_num else 0,
                'disc_number': int(disc_num) if disc_num else 1,
                'path': str(filepath),
                'filename': filepath.name,
                'format': ext[1:],
                'duration': getattr(audio.info, 'length', 0),
                'tidal_artist_id': tidal_artist_id,
                'tidal_album_id': tidal_album_id,
                'tidal_track_id': tidal_track_id
            }
        except Exception as e:
            logger.warning(f"Error reading metadata for {filepath}: {e}")
            return None

    def scan_library(self, force: bool = False) -> Dict:
        """
        Scans the download directory for music files and builds the library.
        Returns the simplified library structure.
        """
        # Simple cache check: if scanned less than 5 minutes ago and not forced
        if not force and (time.time() - self.library_data.get('timestamp', 0) < 300):
             return self.library_data['artists']

        logger.info("Starting library scan...")
        artists_data = {}
        
        # Walk through the directory
        for root, _, files in os.walk(DOWNLOAD_DIR):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.m4a', '.opus')):
                    filepath = Path(root) / file
                    meta = self._get_file_metadata(filepath)
                    
                    if meta:
                        artist = meta['artist']
                        album = meta['album']
                        
                        # Initialize Artist
                        if artist not in artists_data:
                            # Try to recover metadata from old cache
                            old_data = self.library_data['artists'].get(artist, {})
                            
                            artists_data[artist] = {
                                "name": artist,
                                "albums": {},
                                "track_count": 0,
                                "tidal_id": meta.get('tidal_artist_id') or old_data.get('tidal_id'),
                                "picture": old_data.get('picture') # Preserve Tidal picture
                            }
                        elif not artists_data[artist].get("tidal_id") and meta.get('tidal_artist_id'):
                            # Update existing artist with ID if found later
                            artists_data[artist]["tidal_id"] = meta['tidal_artist_id']
                        
                        # Initialize Album
                        if album not in artists_data[artist]["albums"]:
                            artists_data[artist]["albums"][album] = {
                                "title": album,
                                "year": meta['year'],
                                "tracks": [],
                                "cover_path": None,
                                "tidal_id": meta.get('tidal_album_id')
                            }
                        elif not artists_data[artist]["albums"][album].get("tidal_id") and meta.get('tidal_album_id'):
                            artists_data[artist]["albums"][album]["tidal_id"] = meta['tidal_album_id']
                            # Try to find cover.jpg/png in the same folder
                            cover_candidates = [filepath.parent / "cover.jpg", filepath.parent / "cover.png", filepath.parent / "folder.jpg"]
                            for cand in cover_candidates:
                                if cand.exists():
                                    artists_data[artist]["albums"][album]["cover_path"] = str(cand)
                                    break

                        # Add Track
                        artists_data[artist]["albums"][album]["tracks"].append(meta)
                        artists_data[artist]["track_count"] += 1

        # Sort tracks by disc/track number
        for artist in artists_data.values():
            for album in artist["albums"].values():
                album["tracks"].sort(key=lambda x: (x.get('disc_number', 1), x.get('track_number', 0)))

        self.library_data = {
            "artists": artists_data,
            "timestamp": time.time()
        }
        self._save_cache()
        logger.info(f"Library scan complete. Found {len(artists_data)} artists.")
        return artists_data

    def invalidate_cache(self):
        """Forces the next scan to read from disk"""
        self.library_data['timestamp'] = 0
        self._save_cache()
        logger.info("Library cache invalidated.")

    def get_artists(self) -> List[Dict]:
        data = self.scan_library() # Will use cache if valid
        artists_list = []
        for name, data in data.items():
            # Pick a cover image from the first album that has one
            image = None
            for album in data["albums"].values():
                if album.get("cover_path"):
                    image = album["cover_path"]
                    break
            
            artists_list.append({
                "name": name,
                "album_count": len(data["albums"]),
                "track_count": data["track_count"],
                "image": image,
                "picture": data.get("picture"),
                "tidal_id": data.get("tidal_id")
            })
        
        return sorted(artists_list, key=lambda x: x["name"].lower())

    def get_artist(self, name: str) -> Optional[Dict]:
        data = self.scan_library()
        if name in data:
            # Return a copy to avoid modifying the cache structure
            artist_data = data[name].copy()
            # Convert albums dict to list for frontend
            artist_data['albums'] = list(artist_data['albums'].values())
            # Sort albums by year (newest first)
            artist_data['albums'].sort(key=lambda x: str(x.get('year', '0')), reverse=True)
            return artist_data
        return None

    def update_artist_metadata(self, name: str, picture: str = None):
        """Updates persistent metadata for an artist (e.g. Tidal Picture)"""
        if name in self.library_data['artists']:
            if picture:
                self.library_data['artists'][name]['picture'] = picture
                self._save_cache()
                logger.info(f"Updated metadata for artist {name}: picture={picture}")
            return True
        return False

library_service = LibraryService()
