"""
Global Queue Manager for Universal Download Queue

This module manages a shared download queue across all clients.
It provides thread-safe operations and persists state to disk.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock

from api.utils.logging import log_info, log_error, log_warning, log_step


# Configuration from environment
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
QUEUE_AUTO_PROCESS = os.getenv("QUEUE_AUTO_PROCESS", "true").lower() == "true"

# State file path
STATE_FILE = Path(__file__).parent / "queue_state.json"


@dataclass
class QueueItem:
    """Represents a track in the download queue"""
    track_id: int
    title: str
    artist: str
    album: str = ""
    album_id: Optional[int] = None
    track_number: Optional[int] = None
    cover: Optional[str] = None
    quality: str = "HIGH"
    added_at: str = ""
    added_at: str = ""
    added_by: str = "unknown"  # Could track which client added it
    
    # Tidal IDs (for precise metadata)
    tidal_track_id: Optional[str] = None
    tidal_artist_id: Optional[str] = None
    tidal_album_id: Optional[str] = None
    tidal_artist_id: Optional[str] = None
    tidal_album_id: Optional[str] = None
    
    # Context
    album_artist: Optional[str] = None # Capture Album Artist context from Frontend
    
    # Request metadata for download
    target_format: Optional[str] = None
    bitrate_kbps: Optional[int] = None
    run_beets: bool = False
    embed_lyrics: bool = False
    organization_template: str = "{Artist}/{Album}/{TrackNumber} - {Title}"
    group_compilations: bool = True
    
    def __post_init__(self):
        if not self.added_at:
            self.added_at = datetime.now().isoformat()


class QueueManager:
    """
    Singleton manager for the global download queue.
    
    Provides:
    - Thread-safe queue operations
    - Persistence to disk
    - Auto-processing with configurable concurrency
    - Manual start/stop mode option
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._queue: List[QueueItem] = []
        self._active: Dict[int, Dict[str, Any]] = {}  # track_id -> {progress, status, item}
        self._completed: List[Dict[str, Any]] = []
        self._failed: List[Dict[str, Any]] = []
        
        self._processing = False
        self._process_task: Optional[asyncio.Task] = None
        self._queue_lock = asyncio.Lock()
        
        # Load persisted state
        self._load_state()
        
        log_info(f"Queue Manager initialized: max_concurrent={MAX_CONCURRENT_DOWNLOADS}, auto_process={QUEUE_AUTO_PROCESS}")
    
    def _load_state(self):
        """Load queue state from disk"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                
                # Restore queue
                self._queue = [QueueItem(**item) for item in data.get('queue', [])]
                
                # Restore completed/failed (active downloads are reset on restart)
                self._completed = data.get('completed', [])[-100:]  # Keep last 100
                self._failed = data.get('failed', [])
                
                log_info(f"Loaded queue state: {len(self._queue)} queued, {len(self._completed)} completed, {len(self._failed)} failed")
            except Exception as e:
                log_error(f"Failed to load queue state: {e}")
    
    def _save_state(self):
        """Persist queue state to disk"""
        try:
            data = {
                'queue': [asdict(item) for item in self._queue],
                'completed': self._completed[-100:],  # Keep last 100
                'failed': self._failed
            }
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log_error(f"Failed to save queue state: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current queue state for API response"""
        return {
            'queue': [asdict(item) for item in self._queue],
            'active': [
                {
                    'track_id': tid,
                    'progress': info.get('progress', 0),
                    'status': info.get('status', 'downloading'),
                    **asdict(info.get('item', QueueItem(track_id=tid, title='', artist='')))
                }
                for tid, info in self._active.items()
            ],
            'completed': self._completed[-50:],  # Return last 50
            'failed': self._failed,
            'settings': {
                'max_concurrent': MAX_CONCURRENT_DOWNLOADS,
                'auto_process': QUEUE_AUTO_PROCESS,
                'is_processing': self._processing
            }
        }
    
    async def add_to_queue(self, item: QueueItem) -> bool:
        """Add a track to the queue"""
        async with self._queue_lock:
            # Check if already in queue or active
            if any(q.track_id == item.track_id for q in self._queue):
                log_warning(f"Track {item.track_id} already in queue")
                return False
            
            if item.track_id in self._active:
                log_warning(f"Track {item.track_id} already downloading")
                return False
            
            self._queue.append(item)
            self._save_state()
            log_info(f"Added to queue: {item.title} by {item.artist}")
            
            # Auto-trigger processing if enabled
            if QUEUE_AUTO_PROCESS and not self._processing:
                asyncio.create_task(self.start_processing())
            
            return True
    
    async def add_many_to_queue(self, items: List[QueueItem]) -> Dict[str, Any]:
        """Add multiple tracks to the queue"""
        added = 0
        skipped = 0
        
        for item in items:
            if await self.add_to_queue(item):
                added += 1
            else:
                skipped += 1
        
        return {'added': added, 'skipped': skipped}
    
    async def remove_from_queue(self, track_id: int) -> bool:
        """Remove a track from the queue"""
        async with self._queue_lock:
            before = len(self._queue)
            self._queue = [q for q in self._queue if q.track_id != track_id]
            
            if len(self._queue) < before:
                self._save_state()
                return True
            return False
    
    async def clear_queue(self) -> int:
        """Clear all queued items (not active)"""
        async with self._queue_lock:
            count = len(self._queue)
            self._queue.clear()
            self._save_state()
            return count
    
    async def clear_completed(self) -> int:
        """Clear completed items"""
        count = len(self._completed)
        self._completed.clear()
        self._save_state()
        return count
    
    async def clear_failed(self) -> int:
        """Clear failed items"""
        count = len(self._failed)
        self._failed.clear()
        self._save_state()
        return count
    
    async def retry_failed(self) -> int:
        """Move all failed items back to queue"""
        count = 0
        async with self._queue_lock:
            for failed_item in self._failed:
                try:
                    item = QueueItem(
                        track_id=failed_item['track_id'],
                        title=failed_item.get('title', ''),
                        artist=failed_item.get('artist', ''),
                        album=failed_item.get('album', ''),
                        album_id=failed_item.get('album_id'),
                        track_number=failed_item.get('track_number'),
                        cover=failed_item.get('cover'),
                        quality=failed_item.get('quality', 'HIGH'),
                        target_format=failed_item.get('target_format'),
                        bitrate_kbps=failed_item.get('bitrate_kbps'),
                        run_beets=failed_item.get('run_beets', False),
                        embed_lyrics=failed_item.get('embed_lyrics', False),
                    )
                    self._queue.append(item)
                    count += 1
                except Exception as e:
                    log_error(f"Failed to retry item: {e}")
            
            self._failed.clear()
            self._save_state()
        
        # Trigger processing if auto mode
        if count > 0 and QUEUE_AUTO_PROCESS and not self._processing:
            asyncio.create_task(self.start_processing())
        
        return count
    
    async def retry_single(self, track_id: int) -> bool:
        """Retry a single failed item"""
        async with self._queue_lock:
            for i, failed_item in enumerate(self._failed):
                if failed_item.get('track_id') == track_id:
                    try:
                        item = QueueItem(
                            track_id=failed_item['track_id'],
                            title=failed_item.get('title', ''),
                            artist=failed_item.get('artist', ''),
                            album=failed_item.get('album', ''),
                            quality=failed_item.get('quality', 'HIGH'),
                        )
                        self._queue.append(item)
                        self._failed.pop(i)
                        self._save_state()
                        
                        if QUEUE_AUTO_PROCESS and not self._processing:
                            asyncio.create_task(self.start_processing())
                        
                        return True
                    except Exception as e:
                        log_error(f"Failed to retry item {track_id}: {e}")
                        return False
            return False
    
    def update_active_progress(self, track_id: int, progress: int, status: str = 'downloading'):
        """Update progress of an active download"""
        if track_id in self._active:
            self._active[track_id]['progress'] = progress
            self._active[track_id]['status'] = status
    
    def mark_completed(self, track_id: int, filename: str, metadata: Dict = None):
        """Mark a download as completed"""
        if track_id in self._active:
            item = self._active[track_id].get('item')
            self._completed.append({
                'track_id': track_id,
                'title': item.title if item else '',
                'artist': item.artist if item else '',
                'album': item.album if item else '',
                'filename': filename,
                'completed_at': datetime.now().isoformat(),
                'metadata': metadata or {}
            })
            del self._active[track_id]
            self._save_state()
    
    def mark_failed(self, track_id: int, error: str):
        """Mark a download as failed"""
        if track_id in self._active:
            item = self._active[track_id].get('item')
            self._failed.append({
                'track_id': track_id,
                'title': item.title if item else '',
                'artist': item.artist if item else '',
                'album': item.album if item else '',
                'error': error,
                'failed_at': datetime.now().isoformat(),
                # Preserve download settings for retry
                'quality': item.quality if item else 'HIGH',
                'target_format': item.target_format if item else None,
                'bitrate_kbps': item.bitrate_kbps if item else None,
                'run_beets': item.run_beets if item else False,
                'embed_lyrics': item.embed_lyrics if item else False,
            })
            del self._active[track_id]
            self._save_state()
    
    async def start_processing(self):
        """Start the queue processing loop"""
        if self._processing:
            log_info("Queue already processing")
            return
        
        self._processing = True
        log_info("Starting queue processing...")
        
        try:
            while self._processing and (self._queue or self._active):
                # Fill up to max concurrent
                async with self._queue_lock:
                    while len(self._active) < MAX_CONCURRENT_DOWNLOADS and self._queue:
                        item = self._queue.pop(0)
                        self._active[item.track_id] = {
                            'progress': 0,
                            'status': 'starting',
                            'item': item
                        }
                        self._save_state()
                        
                        # Start download task
                        asyncio.create_task(self._process_item(item))
                
                # Wait a bit before checking again
                await asyncio.sleep(1)
        except Exception as e:
            log_error(f"Queue processing error: {e}")
        finally:
            self._processing = False
            log_info("Queue processing stopped")
    
    async def stop_processing(self):
        """Stop the queue processing loop (won't cancel active downloads)"""
        self._processing = False
        log_info("Queue processing stop requested")
    
    async def _process_item(self, item: QueueItem):
        """Process a single queue item - actual download logic"""
        # This will be called from the downloads router
        # The actual download is handled by the existing download_file_async
        # We just need to import and call it with the right parameters
        
        from api.routers.downloads import process_queue_item
        
        try:
            await process_queue_item(item)
        except Exception as e:
            log_error(f"Failed to process queue item {item.track_id}: {e}")
            self.mark_failed(item.track_id, str(e))


# Global singleton instance
queue_manager = QueueManager()
