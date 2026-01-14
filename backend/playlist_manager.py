
import json
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import aiofiles

from api.constants import SyncFrequency, PlaylistSource, AudioQuality

from api.settings import settings, DOWNLOAD_DIR, PLAYLISTS_DIR
from api.clients import tidal_client
from api.clients.jellyfin_client import jellyfin_client
from api.services.listenbrainz import fetch_and_validate_listenbrainz_playlist
from api.services.files import get_output_relative_path, sanitize_path_component
# from api.utils.logging import log_info, log_error, log_warning (Using standard logger instead)
from queue_manager import queue_manager, QueueItem

logger = logging.getLogger(__name__)

from api.state import import_cache, import_states

# Persistence file - Store in PLAYLISTS_DIR to survive container rebuilds
MONITORED_PLAYLISTS_FILE = PLAYLISTS_DIR / "monitored_playlists.json"

@dataclass
class MonitoredPlaylist:
    uuid: str
    name: str
    path: str  # Relative path to m3u8 in PLAYLISTS_DIR (e.g. "My Playlist.m3u8")
    sync_frequency: str  # "manual", "daily", "weekly"
    last_sync: Optional[str] = None
    auto_download_tracks: bool = True
    quality: str = "LOSSLESS"
    track_count: int = 0
    source: str = "tidal" # "tidal" or "listenbrainz"
    extra_config: Dict[str, Any] = None # e.g. { "lb_username": "...", "lb_type": "..." }
    use_playlist_folder: bool = False

class PlaylistManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._playlists: List[MonitoredPlaylist] = []
        self._load_state()

    def _load_state(self):
        if MONITORED_PLAYLISTS_FILE.exists():
            try:
                with open(MONITORED_PLAYLISTS_FILE, 'r') as f:
                    data = json.load(f)
                    self._playlists = [MonitoredPlaylist(**item) for item in data.get('playlists', [])]
            except Exception as e:
                logger.error(f"Failed to load monitored playlists: {e}")

    def _save_state(self):
        try:
            logger.info(f"Saving state to {MONITORED_PLAYLISTS_FILE}")
            data = {'playlists': [asdict(p) for p in self._playlists]}
            with open(MONITORED_PLAYLISTS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"State saved successfully. {len(self._playlists)} playlists.")
        except Exception as e:
            logger.error(f"Failed to save monitored playlists: {e}")

    def get_monitored_playlists(self) -> List[Dict]:
        return [asdict(p) for p in self._playlists]
    
    def get_playlist(self, uuid: str) -> Optional[MonitoredPlaylist]:
        return next((p for p in self._playlists if p.uuid == uuid), None)

    def add_monitored_playlist(self, uuid: str, name: str, frequency: str = SyncFrequency.MANUAL, quality: str = AudioQuality.LOSSLESS, source: str = PlaylistSource.TIDAL, extra_config: Dict = None, use_playlist_folder: bool = False) -> tuple[MonitoredPlaylist, bool]:
        logger.info(f"Adding/Updating playlist: {uuid} - {name} (Freq: {frequency}, Qual: {quality}, Source: {source}, Folder: {use_playlist_folder})")
        
        # Enforce Strict Frequency Rules for ListenBrainz
        if source == PlaylistSource.LISTENBRAINZ and extra_config:
            lb_type = extra_config.get('lb_type')
            if lb_type in ['weekly-jams', 'weekly-exploration']:
                if frequency != SyncFrequency.WEEKLY:
                    logger.info(f"Enforcing STRICT rule: {name} ({lb_type}) must be WEEKLY.")
                    frequency = SyncFrequency.WEEKLY
            elif lb_type in ['year-in-review-discoveries', 'year-in-review-missed']:
                 if frequency != SyncFrequency.MANUAL:
                     logger.info(f"Enforcing STRICT rule: {name} ({lb_type}) must be MANUAL.")
                     frequency = SyncFrequency.MANUAL

        # Check if exists
        existing = self.get_playlist(uuid)
        if existing:
            logger.info(f"Found existing playlist {uuid}. Updating settings.")
            existing.sync_frequency = frequency
            existing.quality = quality
            existing.source = source
            existing.extra_config = extra_config
            existing.use_playlist_folder = use_playlist_folder
            # Start sync immediately? No, caller decides.
            self._save_state()
            logger.info(f"Playlist {uuid} updated. Current list size: {len(self._playlists)}")
            return existing, False

        logger.info(f"Playlist {uuid} not found. Creating new.")
        # Sanitize name for filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_name}.m3u8"
        
        playlist = MonitoredPlaylist(
            uuid=uuid,
            name=name,
            path=filename,
            sync_frequency=frequency,
            quality=quality,
            source=source,
            extra_config=extra_config,
            use_playlist_folder=use_playlist_folder
        )
        self._playlists.append(playlist)
        self._save_state()
        logger.info(f"Playlist {uuid} created. Current list size: {len(self._playlists)}")
        return playlist, True

    def remove_monitored_playlist(self, uuid: str):
        playlist = self.get_playlist(uuid)
        if not playlist:
            logger.warning(f"Attempted to remove non-existent playlist {uuid}")
            return
            
        self._playlists = [p for p in self._playlists if p.uuid != uuid]
        self._save_state()
        
        # Delete m3u8 file and cover (or entire folder if using new strategy)
        try:
            file_path = PLAYLISTS_DIR / playlist.path
            
            # Check if using Folder Strategy (Path contains a parent directory relative to PLAYLISTS_DIR)
            # playlist.path like "Name/Name.m3u8"
            if len(Path(playlist.path).parts) > 1:
                # It's in a subfolder, remove the parent folder
                parent_folder = file_path.parent
                if parent_folder.exists() and parent_folder != PLAYLISTS_DIR:
                    import shutil
                    shutil.rmtree(parent_folder)
                    logger.info(f"Deleted playlist folder: {parent_folder}")
            else:
                # Legacy: Flat file
                base_name = str(Path(playlist.path).stem)
                cover_path = PLAYLISTS_DIR / f"{base_name}.jpg"
                
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted playlist file: {file_path}")
                
                if cover_path.exists():
                    cover_path.unlink()
                    logger.info(f"Deleted playlist cover: {cover_path}")
                
        except Exception as e:
            logger.error(f"Failed to delete playlist file/cover: {e}")

    async def sync_playlist(self, uuid: str, progress_id: Optional[str] = None, skip_download: bool = False) -> Dict[str, Any]:
        playlist = self.get_playlist(uuid)
        if not playlist:
            raise ValueError("Playlist not found")

        logger.info(f"Syncing playlist: {playlist.name} ({playlist.uuid}) [Source: {playlist.source}]")
        
        # DEBUG CACHE
        # DEBUG CACHE
        logger.info(f"DEBUG: sync_playlist called with progress_id={progress_id}, skip_download={skip_download}")
        logger.info(f"DEBUG: Cache keys: {list(import_cache.keys())}")
        if progress_id:
            logger.info(f"DEBUG: Is {progress_id} in cache? {progress_id in import_cache}")

        # Helper to emit progress
        # Helper to emit progress (Queue + State)
        async def emit_progress(msg_type: str, message: str, **kwargs):
            if progress_id:
                from api.state import lb_progress_queues, import_states
                
                payload = {"type": msg_type, "message": message, **kwargs}
                
                # 1. Legacy Queue (SSE) - Keep for backward compat or just remove later
                if progress_id in lb_progress_queues:
                    await lb_progress_queues[progress_id].put(payload)
                
                # 2. Update Direct State (Polling)
                if progress_id not in import_states:
                    import_states[progress_id] = {
                        "status": "active",
                        "messages": [],
                        "current": 0,
                        "total": 0,
                        "matches": 0
                    }
                
                state = import_states[progress_id]
                
                # Append log message
                state["messages"].append({
                    "text": message,
                    "type": msg_type,
                    "timestamp": payload.get("timestamp", 0) # Service should add timestamp? No, lets add current
                })
                # Keep logs manageable
                if len(state["messages"]) > 50:
                    state["messages"] = state["messages"][-50:]
                    
                # Update counters
                if "progress" in kwargs:
                    state["current"] = kwargs["progress"]
                if "total" in kwargs:
                    state["total"] = kwargs["total"]
                if "matches_found" in kwargs:
                    state["matches"] = kwargs["matches_found"]
                
                # Update Status
                if msg_type == "complete" or msg_type == "analysis_complete":
                    state["status"] = "waiting_confirmation" if skip_download else "complete"
                elif msg_type == "error":
                    state["status"] = "error"

        try:
            await emit_progress("info", f"Starting analysis for {playlist.name}...")
            
            raw_items = []
            
            # 1. Fetch tracks based on source
            # Optimization: Check cache first if confirming
            
            # If we are provided a progress_id and we are NOT skipping download, 
            # it might be a confirmation of a previous analysis.
            if progress_id and not skip_download and progress_id in import_cache:
                logger.info(f"Using cached analysis results for {progress_id}")
                raw_items = import_cache[progress_id]
                
                # Restore matches count
                match_count = len([x for x in raw_items if x.get('tidal_exists') or (isinstance(x.get('item'), dict) and x['item'].get('id'))])
                
                # Initialize state if needed (it should exist if we are polling, but might be fresh)
                if progress_id not in import_states:
                     import_states[progress_id] = {
                        "status": "active",
                        "messages": [],
                        "current": 0,
                        "total": len(raw_items),
                        "matches": match_count
                    }
                else:
                    import_states[progress_id]["matches"] = match_count
                    import_states[progress_id]["total"] = len(raw_items)

                await emit_progress("info", f"Using cached analysis ({len(raw_items)} items)...", matches_found=match_count)
            else:
                # Normal Fetch / Analysis
                if playlist.source == PlaylistSource.LISTENBRAINZ:
                    raw_items = await self._fetch_listenbrainz_items(playlist)
                elif playlist.source == PlaylistSource.SPOTIFY:
                    raw_items = await self._fetch_spotify_items(playlist, progress_id)
                else:
                    raw_items = await self._fetch_tidal_items(playlist)
                
                # If this was an analysis run, cache the results
                if progress_id and skip_download:
                     import_cache[progress_id] = raw_items
                     logger.info(f"Cached {len(raw_items)} items for progress_id {progress_id}")
                
            logger.info(f"Fetched {len(raw_items)} items for playlist {playlist.uuid}")
            
            if not raw_items:
                logger.warning(f"No tracks found for playlist {playlist.name}")
                await emit_progress("info", "No tracks found.")
            
            # CHECKPOINT: If this is an analyze-only run (Manual Import flow), stop here.
            if skip_download:
                logger.info("Skip download requested. Finishing analysis.")
                await emit_progress("complete", "Analysis complete. Waiting for confirmation.", matches_found=len([x for x in raw_items if x.get('tidal_exists')]))
                return {"status": "analysis_complete", "count": len(raw_items)}

            await emit_progress("info", f"Processing {len(raw_items)} tracks...")

            # 2. Process tracks & M3U8 content
            result = await self._process_playlist_items(playlist, raw_items)
            
            # Emit completion if we have details
            if isinstance(result, dict) and 'queued' in result:
                msg = "Sync complete."
                if result['queued'] > 0:
                    msg += f" Queued {result['queued']} downloads."
                await emit_progress("complete", msg)
            
            return result
        
        except Exception as e:
            await emit_progress("error", f"Sync failed: {e}")
            raise e
        finally:
            # Signal end of stream
            if progress_id:
                from api.state import lb_progress_queues
                if progress_id in lb_progress_queues:
                     await lb_progress_queues[progress_id].put(None)

    async def _fetch_tidal_items(self, playlist: MonitoredPlaylist) -> List[Dict]:
        try:
            result = tidal_client.get_playlist_tracks(playlist.uuid)
        except Exception as e:
            logger.error(f"Failed to fetch tracks for playlist {playlist.uuid}: {e}")
            return []
        
        # Unwrap v2 wrapper if present
        if isinstance(result, dict) and 'data' in result and 'version' in result:
            result = result['data']
            
        raw_items = []
        if isinstance(result, dict):
            if 'items' in result:
                raw_items = result.get('items', [])
            elif 'tracks' in result and isinstance(result['tracks'], dict):
                raw_items = result['tracks'].get('items', [])
            elif isinstance(result.get('tracks'), list):
                raw_items = result.get('tracks', [])
            elif isinstance(result.get('data'), list):
                raw_items = result.get('data')
        elif isinstance(result, list):
            raw_items = result
            
        return raw_items

    async def _fetch_listenbrainz_items(self, playlist: MonitoredPlaylist) -> List[Dict]:
        if not playlist.extra_config:
            logger.error(f"Missing extra_config for ListenBrainz playlist {playlist.name}")
            return []
            
        username = playlist.extra_config.get('lb_username')
        pl_type = playlist.extra_config.get('lb_type')
        
        if not username or not pl_type:
            logger.error("Invalid ListenBrainz config")
            return []
            
        try:
            # Helper to log progress for background tasks
            async def progress_logger(data):
                if data.get('type') in ['info', 'complete']:
                    logger.info(f"[LB-Sync] {data.get('message')}")
            
            tracks = await fetch_and_validate_listenbrainz_playlist(
                username=username, 
                playlist_type=pl_type, 
                progress_callback=progress_logger, 
                validate=True
            )
            
            # Normalize to match "Tidal Item" structure roughly
            normalized = []
            for t in tracks:
                if not t.get('tidal_exists') or not t.get('tidal_id'):
                    continue
                    
                # Construct item resembling Tidal API response
                normalized.append({
                    'item': {
                        'id': int(t['tidal_id']) if str(t['tidal_id']).isdigit() else t['tidal_id'],
                        'title': t['title'],
                        'artist': {'name': t['artist'], 'id': t.get('tidal_artist_id')},
                        'album': {'title': t.get('album', 'Unknown Album'), 'id': t.get('tidal_album_id'), 'cover': t.get('cover')},
                        'trackNumber': t.get('track_number'),
                        'duration': -1 # We don't have duration from simple valid result
                    }
                })
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to fetch ListenBrainz tracks: {e}")
            return []

    async def _fetch_spotify_items(self, playlist: MonitoredPlaylist, progress_id: Optional[str] = None) -> List[Dict]:
        """
        Fetch items from Spotify using the Spotify Service.
        """
        try:
            from api.services.spotify import fetch_and_validate_spotify_playlist
            
            # Helper to log progress for background tasks
            async def progress_logger(data):
                if data.get('type') in ['info', 'complete']:
                    logger.info(f"[Spotify-Sync] {data.get('message')}")
                 
                # Forward to progress queue if active
                if progress_id:
                    from api.state import lb_progress_queues, import_states
                    
                    # Reverted to debug for production
                    logger.debug(f"DEBUG: progress_logger called for {progress_id}. Data keys: {list(data.keys())}")
                    
                    # 1. Backward Compat: Queue
                    if progress_id in lb_progress_queues:
                        await lb_progress_queues[progress_id].put(data)
                        
                    # 2. Modern: Polling State
                    if progress_id in import_states:
                        state = import_states[progress_id]
                        
                        # Update counters if present
                        
                        # Update counters if present
                        if "progress" in data:
                            state["current"] = data["progress"]
                        if "total" in data:
                            state["total"] = data["total"]
                        if "matches_found" in data:
                            state["matches"] = data["matches_found"]
                        
                        # Append message
                        if data.get("message"):
                            msg_entry = {
                                "text": data["message"],
                                "type": data.get("type", "info"),
                                "timestamp": data.get("timestamp", 0)
                            }
                            state["messages"].append(msg_entry)
                            # Keep logs manageable
                            if len(state["messages"]) > 50:
                                state["messages"] = state["messages"][-50:]

            # 'extra_config' should contain 'spotify_id' or we use playlist.uuid if that's where we stored it
            # The MonitorPlaylistRequest uses 'uuid' for the Spotify ID usually?
            # Let's assume playlist.uuid IS the Spotify ID for now, or check extra_config
            spotify_id = playlist.uuid
            if playlist.extra_config and 'spotify_id' in playlist.extra_config:
                spotify_id = playlist.extra_config['spotify_id']
            
            tracks = await fetch_and_validate_spotify_playlist(
                spotify_id=spotify_id,
                progress_callback=progress_logger,
                validate=True
            )
            
            # Normalize to match "Tidal Item" structure
            normalized = []
            for t in tracks:
                if not t.get('tidal_exists') or not t.get('tidal_id'):
                    continue
                    
                normalized.append({
                    'tidal_exists': True, # Required for match counting downstream
                    'item': {
                        'id': int(t['tidal_id']) if str(t['tidal_id']).isdigit() else t['tidal_id'],
                        'title': t['title'],
                        'artist': {'name': t['artist'], 'id': t.get('tidal_artist_id')},
                        'album': {'title': t.get('album', 'Unknown Album'), 'id': t.get('tidal_album_id'), 'cover': t.get('cover')},
                        'trackNumber': t.get('track_number'),
                        'duration': -1
                    }
                })
            
            logger.info(f"Spotify Sync: Normalized {len(normalized)} tracks (Matched)")
            return normalized

        except Exception as e:
            logger.error(f"Failed to fetch Spotify tracks: {e}")
            return []

    async def _process_playlist_items(self, playlist: MonitoredPlaylist, raw_items: List[Dict]) -> Dict[str, Any]:
        m3u8_lines = ["#EXTM3U", f"# Source: {playlist.source}"]
        items_to_download = []
        
        org_template = settings.organization_template
        group_compilations = settings.group_compilations
        
        if playlist.use_playlist_folder:
            safe_pl_name = sanitize_path_component(playlist.name)
            # Use 'tidaloader_playlists' explicitly to match PLAYLISTS_DIR logic
            # This makes the path relative to DOWNLOAD_DIR be: tidaloader_playlists/PlaylistName/Track - Title
            org_template = f"tidaloader_playlists/{safe_pl_name}/{{TrackNumber}} - {{Title}}"
            group_compilations = False
        
        for i, item in enumerate(raw_items):
            # Robust extraction logic mirrored from search.py
            track = item.get('item', item) if isinstance(item, dict) else item
            if not isinstance(track, dict) or 'id' not in track:
                continue

            album_data = track.get('album', {}) if isinstance(track.get('album'), dict) else {}
            artist_data = track.get('artist', {}) if isinstance(track.get('artist'), dict) else (track.get('artists', [{}])[0] if track.get('artists') else {})
            
            # Extract fields
            artist_name = artist_data.get('name', 'Unknown Artist')
            album_name = album_data.get('title', 'Unknown Album')
            title = track.get('title', 'Unknown Title')
            
            track_num = track.get('trackNumber') or track.get('track_number')
            if not track_num and isinstance(item, dict):
                 track_num = item.get('index')
            
            # Simple check for compilation
            album_artist_data = album_data.get('artist', {}) if isinstance(album_data, dict) else {} # Album artist might be inside album
            if not album_artist_data and isinstance(track.get('artists'), list):
                 # Fallback? No, album artist is usually specific
                 pass
            
            album_artist = album_artist_data.get('name')
            
            is_compilation = False
            if isinstance(album_data, dict):
                is_compilation = album_data.get('type') == 'COMPILATION'
            
            # Metadata structure expected by get_output_relative_path
            metadata = {
                'artist': artist_name,
                'album': album_name,
                'title': title,
                'track_number': track_num,
                'album_artist': album_artist,
                'compilation': is_compilation
            }
            
            found_rel_path = None
            
            # Check FLAC (Common default for lossless)
            metadata['file_ext'] = '.flac'
            rel_flac = get_output_relative_path(metadata, template=org_template, group_compilations=group_compilations)
            if (DOWNLOAD_DIR / rel_flac).exists():
                logger.info(f"Found existing file (FLAC): {rel_flac}")
                found_rel_path = rel_flac
            else:
                # logger.debug(f"File not found at: {DOWNLOAD_DIR / rel_flac}")
                # Check M4A
                metadata['file_ext'] = '.m4a'
                rel_m4a = get_output_relative_path(metadata, template=org_template, group_compilations=group_compilations)
                if (DOWNLOAD_DIR / rel_m4a).exists():
                    logger.info(f"Found existing file (M4A): {rel_m4a}")
                    found_rel_path = rel_m4a
                else:
                    # Check MP3
                    metadata['file_ext'] = '.mp3'
                    rel_mp3 = get_output_relative_path(metadata, template=org_template, group_compilations=group_compilations)
                    if (DOWNLOAD_DIR / rel_mp3).exists():
                        logger.info(f"Found existing file (MP3): {rel_mp3}")
                        found_rel_path = rel_mp3
                    # Check OPUS
                    else:
                        metadata['file_ext'] = '.opus'
                        rel_opus = get_output_relative_path(metadata, template=org_template, group_compilations=group_compilations)
                        if (DOWNLOAD_DIR / rel_opus).exists():
                            logger.info(f"Found existing file (OPUS): {rel_opus}")
                            found_rel_path = rel_opus

            if found_rel_path:
                duration = track.get('duration', -1)
                m3u8_lines.append(f"#EXTINF:{duration},{artist_name} - {title}")
                # Use ../../ because m3u8 is now in tidaloader_playlists/{PlaylistName}/
                m3u8_lines.append(f"../../{found_rel_path}")
            else:
                # File missing
                if playlist.auto_download_tracks:
                    item_id = track.get('id')
                    if not item_id:
                        logger.warning(f"Track missing ID at index {i}: {title}")
                        continue
                        
                    items_to_download.append(QueueItem(
                        track_id=item_id,
                        title=title,
                        artist=artist_name,
                        album=album_name,
                        album_artist=album_artist,
                        track_number=track_num,
                        cover=album_data.get('cover') if album_data else (track.get('cover') if isinstance(track.get('cover'), str) else None),
                        quality=playlist.quality,
                        tidal_track_id=str(item_id),
                        tidal_artist_id=str(artist_data.get('id')) if artist_data.get('id') else None,
                        tidal_album_id=str(album_data.get('id')) if album_data.get('id') else None,
                        auto_clean=True,
                        organization_template=org_template,
                        group_compilations=group_compilations,
                        run_beets=settings.run_beets,
                        embed_lyrics=settings.embed_lyrics
                    ))
                    
                    target_ext = '.flac'
                    if playlist.quality in ['LOW', 'HIGH']:
                        target_ext = '.m4a'
                    
                    metadata['file_ext'] = target_ext
                    predicted_path = get_output_relative_path(metadata, template=org_template, group_compilations=group_compilations)
                    
                    duration = track.get('duration', -1)
                    m3u8_lines.append(f"#EXTINF:{duration},{artist_name} - {title}")
                    m3u8_lines.append(f"../../{predicted_path}")

        # 3. Queue downloads
        queued_count = 0
        if items_to_download:
            logger.info(f"Adding {len(items_to_download)} missing tracks to queue")
            try:
                res = await queue_manager.add_many_to_queue(items_to_download)
                queued_count = res.get('added', 0)
                logger.info(f"Successfully queued {queued_count} tracks")
            except Exception as e:
                logger.error(f"Failed to queue tracks: {e}")
        else:
            logger.info("No missing tracks to download.")

        # 4. Write M3U8
        # Folder Strategy: Create folder for playlist
        safe_name = sanitize_path_component(playlist.name)
        playlist_folder = PLAYLISTS_DIR / safe_name
        playlist_folder.mkdir(parents=True, exist_ok=True)
        
        # New M3U8 Path: {Name}/{Name}.m3u8
        m3u8_filename = f"{safe_name}.m3u8"
        playlist_file = playlist_folder / m3u8_filename
        
        try:
            async with aiofiles.open(playlist_file, 'w', encoding='utf-8') as f:
                await f.write("\n".join(m3u8_lines))
            logger.info(f"M3U8 written to {playlist_file}")
            
            # Update path in playlist object (Relative to PLAYLISTS_DIR)
            # Must use forward slash for consistency
            playlist.path = f"{safe_name}/{m3u8_filename}"
            
        except Exception as e:
            logger.error(f"Failed to write M3U8: {e}")
            
        # 5. Download playlist cover (for Media Servers)
        try:
           await self._ensure_playlist_cover(playlist, playlist_folder, safe_name)
        except Exception as e:
           logger.warning(f"Failed to ensure playlist cover: {e}")

        # 6. Jellyfin Sync (Refresh & Upload Cover)
        if settings.jellyfin_url and settings.jellyfin_api_key:
            try:
                # Trigger Scan so Jellyfin sees the new m3u8
                jellyfin_client.refresh_library()
                
                # Attempt upload with extended wait (for scan to finish)
                cover_path = playlist_folder / f"{safe_name}.jpg"
                if cover_path.exists():
                    await self._sync_cover_to_jellyfin(playlist.name, cover_path, scan_wait=True)
            except Exception as e:
                logger.error(f"Jellyfin Sync Sequence Failed: {e}")

        # Update last sync
        playlist.last_sync = datetime.now().isoformat()
        playlist.track_count = len(raw_items)
        self._save_state()
        
        return {'status': 'success', 'queued': queued_count, 'total_tracks': len(raw_items)}

    async def _sync_cover_to_jellyfin(self, playlist_name: str, image_path: Path, scan_wait: bool = False):
        """
        Tries to find the playlist in Jellyfin and upload the cover art.
        """
        if not settings.jellyfin_url or not settings.jellyfin_api_key:
            return

        try:
            # 1. Find Playlist ID with Retries
            # Jellyfin might take a moment to index the new m3u8 file
            playlist_id = None
            max_retries = 3
            retry_delay = 4 # seconds
            
            if scan_wait:
                # If we just triggered a scan, wait longer and retry more
                max_retries = 10
                retry_delay = 5 # Total wait approx 50s which covers most library scan times
            
            for attempt in range(max_retries):
                playlist_id = jellyfin_client.find_playlist_id(playlist_name)
                if playlist_id:
                    break
                
                if attempt < max_retries - 1:
                    logger.info(f"Playlist '{playlist_name}' not found yet. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(retry_delay)
            
            if not playlist_id:
                logger.warning(f"Playlist '{playlist_name}' not found in Jellyfin after {max_retries} attempts. Skipping cover sync.")
                return

            # 2. Read Image
            file_size = image_path.stat().st_size
            if file_size == 0:
                logger.warning(f"Cover file for '{playlist_name}' is empty (0 bytes). Skipping upload.")
                return

            async with aiofiles.open(image_path, 'rb') as f:
                data = await f.read()

            if len(data) == 0:
                 logger.warning(f"Read 0 bytes from '{playlist_name}'. Skipping upload.")
                 return

            # Validate Magic Numbers (Prevent uploading HTML/Garbage)
            is_valid_image = False
            if data.startswith(b'\xff\xd8\xff'): # JPEG
                is_valid_image = True
            elif data.startswith(b'\x89PNG\r\n\x1a\n'): # PNG
                is_valid_image = True
            elif data.startswith(b'RIFF') and data[8:12] == b'WEBP': # WEBP
                is_valid_image = True
            
            if not is_valid_image:
                # Peek at first 50 chars to see if it's text/html
                preview = data[:50]
                logger.warning(f"Invalid image file for '{playlist_name}'. Header: {preview}. Deleting and skipping upload.")
                # We can try to delete it so it redownloads next time
                try:
                    image_path.unlink()
                    logger.info("Deleted invalid cover file.")
                except Exception as e:
                    logger.error(f"Failed to delete invalid file: {e}")
                return
                
            # 3. Upload
            if jellyfin_client.upload_image(playlist_id, data):
                logger.info(f"Successfully uploaded cover for '{playlist_name}' to Jellyfin")
            else:
                logger.warning(f"Failed to upload cover for '{playlist_name}' to Jellyfin")
                
        except Exception as e:
            logger.error(f"Jellyfin Cover Sync Error: {e}")
        except Exception as e:
            logger.error(f"Jellyfin Cover Sync Error: {e}")

    async def force_sync_covers(self) -> Dict[str, Any]:
        """
        Iterates over all monitored playlists and forces an update of the cover art to Jellyfin.
        Only attempts upload if the local cover file exists.
        """
        if not settings.jellyfin_url or not settings.jellyfin_api_key:
            return {"status": "error", "message": "Jellyfin is not configured"}
            
        logger.info("Starting global Jellyfin cover sync...")
        success_count = 0
        skipped_count = 0
        
        for uuid, playlist in self.playlists.items():
            try:
                safe_name = sanitize_path_component(playlist.name)
                # Logic matches _process_playlist_items: m3u8 and cover are constantly in PLAYLISTS_DIR/{safe_name}
                playlist_folder = PLAYLISTS_DIR / safe_name
                cover_path = playlist_folder / f"{safe_name}.jpg"
                
                if cover_path.exists():
                    logger.info(f"Syncing cover for '{playlist.name}'...")
                    # We await strictly here to avoid flooding Jellyfin API if we have 50 playlists
                    await self._sync_cover_to_jellyfin(playlist.name, cover_path)
                    success_count += 1
                else:
                    logger.debug(f"No cover found for '{playlist.name}', skipping.")
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error syncing cover for {playlist.name}: {e}")
                
        logger.info(f"Global Cover Sync Complete: {success_count} synced, {skipped_count} skipped.")
        return {
            "status": "success",
            "synced": success_count,
            "skipped": skipped_count
        }

    async def _ensure_playlist_cover(self, playlist: MonitoredPlaylist, folder_path: Path, safe_name: str):
        """Downloads the playlist cover image to {PlaylistFolder}/{safe_name}.jpg if missing"""
        # Target filename: {safe_name}.jpg (Same basename as m3u8)
        cover_path = folder_path / f"{safe_name}.jpg"
        
        if cover_path.exists():
            # Even if exists locally, we might want to ensure it's in Jellyfin?
            # Let's try to sync to Jellyfin if configured (NON-BLOCKING)
            asyncio.create_task(self._sync_cover_to_jellyfin(playlist.name, cover_path))
            return

        # ... (Download logic remains similar but needs source adaptation)
        
        image_url = None
        
        if playlist.source == 'listenbrainz':
             # Generate Dynamic Cover for LB Playlists
             try:
                 from api.services.cover_generator import CoverArtGenerator
                 # Use backend/assets
                 assets_dir = Path(__file__).parent / "assets"
                 generator = CoverArtGenerator(assets_dir)
                 
                 # Determine Title & Subtitle
                 # Title: Playlist Name (e.g. "Weekly Jams")
                 # Subtitle: User's Name/Initials from playlist name or config
                 
                 # Typically playlist.name is something like "User - Weekly Jams"
                 #   Title: Weekly Jams
                 #   Subtitle: User
                 parts = playlist.name.split(' - ')
                 if len(parts) > 1:
                     title = " - ".join(parts[1:])
                     subtitle = parts[0] # "User"
                 
                 if " - " in playlist.name:
                     parts = playlist.name.split(" - ", 1)
                     subtitle = parts[0] # e.g. "User"
                     title = parts[1]    # e.g. "Weekly Jams"
                 
                 logger.info(f"Generating cover for LB playlist: '{title}' (User: {subtitle})")
                 
                 cover_bytes = generator.generate_cover(title, subtitle)
                 
                 if cover_bytes:
                     async with aiofiles.open(cover_path, 'wb') as f:
                         await f.write(cover_bytes)
                     logger.info(f"Generated & Saved cover: {cover_path}")
                     
                     # Sync deferred to main process
                 else:
                     logger.warning("Failed to generate cover bytes (returned None)")

             except Exception as e:
                 logger.error(f"Error generating LB cover: {e}")
             except Exception as e:
                 logger.error(f"Error generating LB cover: {e}")
        elif playlist.source == 'spotify':
            # Spotify Logic
            logger.info(f"Downloading cover for Spotify playlist {playlist.name}...")
            
            # 1. Try to get image from extra_config (passed from frontend search)
            image_url = None
            if playlist.extra_config and 'image_url' in playlist.extra_config:
                image_url = playlist.extra_config['image_url']
                logger.info(f"Using provided Spotify cover URL: {image_url}")
            
            # 2. If not provided, try to fetch metadata
            if not image_url:
                try:
                    from api.clients.spotify import SpotifyClient
                    client = SpotifyClient()
                    
                    spotify_id = playlist.uuid
                    if playlist.extra_config and 'spotify_id' in playlist.extra_config:
                        spotify_id = playlist.extra_config['spotify_id']

                    pl_info = await client.get_playlist_metadata(spotify_id)
                    await client.close()
                    
                    if pl_info and pl_info.image:
                        image_url = pl_info.image
                        logger.info(f"Resolved Spotify cover URL: {image_url}")
                    else:
                        logger.warning(f"No cover image found for Spotify playlist {playlist.name}")

                except Exception as e:
                    logger.error(f"Error resolving Spotify cover: {e}")
        else:
             # Tidal Logic
            logger.info(f"Downloading cover for playlist {playlist.name}...")
            
            try:
                pl_info = tidal_client.get_playlist(playlist.uuid)
                if not pl_info:
                    logger.warning(f"No playlist info returned for {playlist.name}")
                    return
                
                # Wrapper unwrapping logic
                if 'data' in pl_info:
                    pl_info = pl_info['data']
                
                if 'item' in pl_info:
                    pl_info = pl_info['item']
                elif 'playlist' in pl_info:
                    pl_info = pl_info['playlist']

                # Robust ID extraction (like search.py)
                priority_keys = ['squareImage', 'image', 'cover', 'picture', 'imageId']
                image_guid = None
                for key in priority_keys:
                    if val := pl_info.get(key):
                        image_guid = str(val).strip()
                        break
                
                if image_guid:
                     # Construct URL (Tidal Resource URL)
                    image_path_url = image_guid.replace('-', '/')
                    image_url = f"https://resources.tidal.com/images/{image_path_url}/640x640.jpg"
            except Exception as e:
                logger.error(f"Error resolving Tidal cover: {e}")

        if image_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            async with aiofiles.open(cover_path, 'wb') as f:
                                await f.write(await resp.read())
                            logger.info(f"Cover saved: {cover_path}")
                            
                            # Sync to Jellyfin (NON-BLOCKING)
                            asyncio.create_task(self._sync_cover_to_jellyfin(playlist.name, cover_path, scan_wait=True))
                        else:
                            logger.warning(f"Failed cover download: {resp.status} from {image_url}")
            except Exception as e:
                 logger.error(f"Error downloading cover: {e}")

    def get_playlist_files(self, uuid: str) -> List[str]:
        """
        Parses the .m3u8 file and returns a list of file paths relative to DOWNLOAD_DIR.
        """
        playlist = self.get_playlist(uuid)
        if not playlist:
            raise ValueError("Playlist not found")
            
        m3u8_path = PLAYLISTS_DIR / playlist.path
        if not m3u8_path.exists():
            return []
            
        files = []
        try:
            with open(m3u8_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Line is a relative path like "../../Artist/Album/Song.flac"
                # We need to resolve this to be relative to DOWNLOAD_DIR
                # m3u8 is at PLAYLISTS_DIR / {PlaylistName} / {PlaylistName}.m3u8
                # So we resolve it relative to m3u8_path.parent
                
                try:
                    full_path = (m3u8_path.parent / line).resolve()
                    
                    # Security check: Must be within DOWNLOAD_DIR
                    if not str(full_path).startswith(str(DOWNLOAD_DIR.resolve())):
                        logger.warning(f"Security: Path {full_path} outside music dir")
                        continue
                        
                    if full_path.exists() and full_path.is_file():
                        # Return path relative to DOWNLOAD_DIR for display
                        rel_path = full_path.relative_to(DOWNLOAD_DIR)
                        files.append(str(rel_path))
                        
                except Exception as e:
                    logger.warning(f"Failed to resolve path {line}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to read playlist file: {e}")
            raise
            
        return sorted(files)

    def delete_playlist_files(self, uuid: str, files_to_delete: List[str]) -> Dict[str, Any]:
        """
        Deletes the specified files associated with the playlist.
        files_to_delete: List of paths relative to DOWNLOAD_DIR
        """
        playlist = self.get_playlist(uuid)
        if not playlist:
            raise ValueError("Playlist not found")

        deleted_count = 0
        errors = []
        
        for file_rel_path in files_to_delete:
            try:
                # Sanitize path - Prevent directory traversal
                if '..' in file_rel_path or file_rel_path.startswith('/'):
                    errors.append(f"Invalid path: {file_rel_path}")
                    continue
                    
                full_path = (DOWNLOAD_DIR / file_rel_path).resolve()
                
                # Security Double Check
                if not str(full_path).startswith(str(DOWNLOAD_DIR.resolve())):
                    errors.append(f"Path outside music directory: {file_rel_path}")
                    continue
                
                if full_path.exists() and full_path.is_file():
                    full_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted file: {full_path}")
                else:
                    errors.append(f"File not found: {file_rel_path}")
                    
            except Exception as e:
                logger.error(f"Failed to delete {file_rel_path}: {e}")
                errors.append(f"Error deleting {file_rel_path}: {str(e)}")
                
        return {
            "status": "success" if not errors else "partial_success",
            "deleted_count": deleted_count,
            "errors": errors
        }

playlist_manager = PlaylistManager()
