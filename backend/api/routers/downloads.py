import re
import asyncio
import json
import traceback
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.auth import require_auth
from api.models import DownloadTrackRequest
from api.settings import DOWNLOAD_DIR, MP3_QUALITY_MAP, OPUS_QUALITY_MAP
from api.state import active_downloads
from api.clients import tidal_client
from download_state import download_state_manager
from api.utils.logging import log_info, log_error, log_warning, log_success, log_step
from api.utils.extraction import extract_stream_url
from api.services.files import sanitize_path_component
from api.services.download import download_file_async
from queue_manager import queue_manager, QueueItem, QUEUE_AUTO_PROCESS, MAX_CONCURRENT_DOWNLOADS

router = APIRouter()

@router.post("/api/download/start")
async def start_download(
    background_tasks: BackgroundTasks,
    username: str = Depends(require_auth)
):
    return {"status": "started"}

@router.get("/api/download/stream/{track_id}")
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

@router.get("/api/download/state")
async def get_download_states(username: str = Depends(require_auth)):
    return {
        "active": download_state_manager.get_all_active(),
        "completed": download_state_manager.get_all_completed(),
        "failed": download_state_manager.get_all_failed()
    }

@router.get("/api/download/progress/{track_id}")
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

@router.post("/api/download/track")
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
                # Check if the file still exists at the stored path
                saved_path = saved_state.get('metadata', {}).get('final_path')
                saved_filename = saved_state.get('metadata', {}).get('title', '')
                file_still_exists = False
                
                if saved_path:
                    file_still_exists = Path(saved_path).exists()
                elif saved_state.get('filename'):
                    # Fallback: check if filename exists anywhere in DOWNLOAD_DIR (quick check)
                    for ext in ['.m4a', '.flac', '.mp3', '.opus']:
                        potential_path = DOWNLOAD_DIR / f"{saved_state.get('filename')}"
                        if potential_path.exists():
                            file_still_exists = True
                            break
                
                if file_still_exists:
                    log_warning(f"Track {request.track_id} already completed")
                    return {
                        "status": "exists",
                        "filename": saved_filename or 'Completed',
                        "message": "Download already completed"
                    }
                else:
                    # File was deleted, clear the completed state and allow re-download
                    log_info(f"Track {request.track_id} was in completed state but file not found, allowing re-download")
                    download_state_manager.clear_download(request.track_id)
        
        print(f"\n{'='*60}")
        print(f"Download Request:")
        print(f"  Track ID: {request.track_id}")
        print(f"  Artist: {request.artist}")
        print(f"  Title: {request.title}")
        print(f"  Album: {request.album}")
        print(f"  Track#: {request.track_number}")
        print(f"  Cover: {request.cover}")
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
            metadata['title'] = track_data.get('title') or request.title
            metadata['track_number'] = track_data.get('trackNumber') or request.track_number
            metadata['disc_number'] = track_data.get('volumeNumber')
            metadata['date'] = track_data.get('streamStartDate', '').split('T')[0] if track_data.get('streamStartDate') else None
            metadata['duration'] = track_data.get('duration')
            
            artist_data = track_data.get('artist', {})
            if isinstance(artist_data, dict) and artist_data.get('name'):
                metadata['artist'] = artist_data.get('name')
                metadata['musicbrainz_artistid'] = artist_data.get('mixes')
            else:
                metadata['artist'] = request.artist
            
            album_data = track_data.get('album', {})
            if isinstance(album_data, dict) and album_data.get('title'):
                metadata['album'] = album_data.get('title')
                metadata['album_artist'] = album_data.get('artist', {}).get('name') if isinstance(album_data.get('artist'), dict) else None
                metadata['total_tracks'] = album_data.get('numberOfTracks')
                metadata['total_discs'] = album_data.get('numberOfVolumes')
                
                # Add Tidal IDs for precise matching
                metadata['tidal_track_id'] = str(track_data.get('id', ''))
                metadata['tidal_artist_id'] = str(artist_data.get('id', ''))
                metadata['tidal_album_id'] = str(album_data.get('id', ''))
                
                cover_id = album_data.get('cover')
                if cover_id:
                    cover_id_str = str(cover_id).replace('-', '/')
                    metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
                
                # Check for compilation flag
                album_artist = metadata.get('album_artist') or ''
                if album_data.get('type') == 'COMPILATION' or (album_artist and album_artist.lower() in ['various artists', 'various']):
                    metadata['compilation'] = True
            else:
                # Use album info from request if API didn't provide it
                metadata['album'] = request.album
                if request.cover:
                    cover_id_str = str(request.cover).replace('-', '/')
                    metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
        else:
            # Fallback to request data
            metadata['title'] = request.title
            metadata['artist'] = request.artist
            metadata['album'] = request.album
            metadata['track_number'] = request.track_number
            if request.cover:
                cover_id_str = str(request.cover).replace('-', '/')
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
            metadata,
            request.organization_template,
            request.group_compilations,
            request.run_beets,
            request.embed_lyrics
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


# ============================================================================
# QUEUE API ENDPOINTS
# ============================================================================

class QueueAddRequest:
    """Request model for adding tracks to queue"""
    def __init__(self, tracks: List[dict]):
        self.tracks = tracks

from pydantic import BaseModel

class QueueTrackItem(BaseModel):
    track_id: int
    title: str
    artist: str
    album: Optional[str] = ""
    album_artist: Optional[str] = "" 
    album_id: Optional[int] = None
    track_number: Optional[int] = None
    cover: Optional[str] = None
    
    # Tidal IDs
    tidal_track_id: Optional[str] = None
    tidal_artist_id: Optional[str] = None
    tidal_album_id: Optional[str] = None
    quality: str = "HIGH"
    target_format: Optional[str] = None
    bitrate_kbps: Optional[int] = None
    run_beets: bool = False
    embed_lyrics: bool = False
    organization_template: str = "{Artist}/{Album}/{TrackNumber} - {Title}"
    group_compilations: bool = True


class QueueAddRequestModel(BaseModel):
    tracks: List[QueueTrackItem]


@router.get("/api/queue")
async def get_queue_state(username: str = Depends(require_auth)):
    """Get current queue state including queue, active, completed, and failed items"""
    return queue_manager.get_state()


@router.post("/api/queue/add")
async def add_to_queue(
    request: QueueAddRequestModel,
    username: str = Depends(require_auth)
):
    """Add tracks to the download queue"""
    if request.tracks:
        first = request.tracks[0]
        log_info(f"[API] Queue Add Request: {len(request.tracks)} items. First Item: {first.title} ({first.artist})")
        log_info(f"[API] Incoming IDs for first item: Track={first.tidal_track_id}, Artist={first.tidal_artist_id}, Album={first.tidal_album_id}")

    items = []
    for track in request.tracks:
        item = QueueItem(
            track_id=track.track_id,
            title=track.title,
            artist=track.artist,
            album=track.album or "",
            album_artist=track.album_artist or "",  # Capture Album Artist
            album_id=track.album_id,
            track_number=track.track_number,
            cover=track.cover,
            quality=track.quality or "HIGH", # Default to HIGH if not specified
            tidal_track_id=track.tidal_track_id,
            tidal_artist_id=track.tidal_artist_id,
            tidal_album_id=track.tidal_album_id,
            target_format=track.target_format,
            bitrate_kbps=track.bitrate_kbps,
            run_beets=track.run_beets,
            embed_lyrics=track.embed_lyrics,
            organization_template=track.organization_template,
            group_compilations=track.group_compilations,
            added_by=username
        )
        items.append(item)
    
    if len(items) == 1:
        success = await queue_manager.add_to_queue(items[0])
        return {"added": 1 if success else 0, "skipped": 0 if success else 1}
    else:
        result = await queue_manager.add_many_to_queue(items)
        return result


@router.delete("/api/queue/{track_id}")
async def remove_from_queue(
    track_id: int,
    username: str = Depends(require_auth)
):
    """Remove a track from the queue"""
    success = await queue_manager.remove_from_queue(track_id)
    return {"success": success}


@router.post("/api/queue/clear")
async def clear_queue(username: str = Depends(require_auth)):
    """Clear all queued items (not active downloads)"""
    count = await queue_manager.clear_queue()
    return {"cleared": count}


@router.post("/api/queue/clear-completed")
async def clear_completed(username: str = Depends(require_auth)):
    """Clear all completed items"""
    count = await queue_manager.clear_completed()
    return {"cleared": count}


@router.post("/api/queue/clear-failed")
async def clear_failed(username: str = Depends(require_auth)):
    """Clear all failed items"""
    count = await queue_manager.clear_failed()
    return {"cleared": count}


@router.post("/api/queue/retry-failed")
async def retry_all_failed(username: str = Depends(require_auth)):
    """Retry all failed downloads"""
    count = await queue_manager.retry_failed()
    return {"retried": count}


@router.post("/api/queue/retry/{track_id}")
async def retry_single_failed(
    track_id: int,
    username: str = Depends(require_auth)
):
    """Retry a single failed download"""
    success = await queue_manager.retry_single(track_id)
    return {"success": success}


@router.post("/api/queue/start")
async def start_queue_processing(username: str = Depends(require_auth)):
    """Manually start queue processing (for non-auto mode)"""
    if QUEUE_AUTO_PROCESS:
        return {"message": "Auto-processing is enabled, queue processes automatically"}
    
    asyncio.create_task(queue_manager.start_processing())
    return {"status": "started"}


@router.post("/api/queue/stop")
async def stop_queue_processing(username: str = Depends(require_auth)):
    """Stop queue processing (won't cancel active downloads)"""
    await queue_manager.stop_processing()
    return {"status": "stopped"}


@router.get("/api/queue/settings")
async def get_queue_settings(username: str = Depends(require_auth)):
    """Get queue settings"""
    return {
        "max_concurrent": MAX_CONCURRENT_DOWNLOADS,
        "auto_process": QUEUE_AUTO_PROCESS
    }


# ============================================================================
# QUEUE ITEM PROCESSOR
# ============================================================================

async def process_queue_item(item: QueueItem):
    """
    Process a single queue item by downloading the track.
    Called by the queue manager's background processing loop.
    """
    try:
        track_id = item.track_id
        requested_quality = item.quality.upper() if item.quality else "LOSSLESS"
        
        log_step("1/4", f"[Queue] Processing: {item.artist} - {item.title}")
        
        # Mark as starting
        queue_manager.update_active_progress(track_id, 0, 'starting')
        active_downloads[track_id] = {'progress': 0, 'status': 'starting'}
        
        is_mp3_request = requested_quality in MP3_QUALITY_MAP
        is_opus_request = requested_quality in OPUS_QUALITY_MAP
        source_quality = 'LOSSLESS' if is_mp3_request or is_opus_request else requested_quality
        
        # Get track playback info (stream URL, manifest) from API
        track_info = tidal_client.get_track(track_id, source_quality)
        if not track_info:
            raise Exception("Track not found (Playback Info)")

        if isinstance(track_info, list) and len(track_info) > 0:
            track_data = track_info[0]
        else:
            track_data = track_info 

        # Build metadata - use queue item data (passed from frontend)
        # Frontend components now correctly pass cover and track_number
        metadata = {
            'quality': requested_quality,
            'source_quality': source_quality,
            'title': item.title,
            'artist': item.artist,
            'album': item.album,
            'album_artist': item.album_artist or item.artist, # Use passed album_artist or fallback to artist
            'track_number': item.track_number,
            'tidal_track_id': item.tidal_track_id or str(track_id),
            'tidal_artist_id': item.tidal_artist_id,
            'tidal_album_id': item.tidal_album_id,
        }
        
        if is_mp3_request:
            metadata['target_format'] = 'mp3'
            metadata['bitrate_kbps'] = MP3_QUALITY_MAP[requested_quality]
        elif is_opus_request:
            metadata['target_format'] = 'opus'
            metadata['bitrate_kbps'] = OPUS_QUALITY_MAP[requested_quality]
        
        # Add cover URL from queue item (frontend passes this now)
        if item.cover:
            cover_id_str = str(item.cover).replace('-', '/')
            metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
            
        # DEBUG LOGGING
        log_info(f"[Queue] Extracted IDs for {item.title}:")
        log_info(f"  Track ID: {metadata.get('tidal_track_id')}")
        log_info(f"  Artist ID: {metadata.get('tidal_artist_id')}")
        log_info(f"  Album ID: {metadata.get('tidal_album_id')}")
        # DEBUG LOGGING
        log_info(f"[Queue] Extracted IDs for {item.title}:")
        log_info(f"  Track ID: {metadata.get('tidal_track_id')}")
        log_info(f"  Artist ID: {metadata.get('tidal_artist_id')}")
        log_info(f"  Album ID: {metadata.get('tidal_album_id')}")
        log_info(f"  From Queue Item: {bool(item.tidal_artist_id)}")
        
        # Get stream URL
        stream_url = extract_stream_url(track_info)
        if not stream_url:
            raise Exception("Stream URL not found")
        
        # Prepare file paths
        download_ext = '.m4a' if source_quality in ['LOW', 'HIGH'] else '.flac'
        if is_mp3_request:
            final_ext = '.mp3'
        elif is_opus_request:
            final_ext = '.opus'
        else:
            final_ext = download_ext
        metadata['file_ext'] = final_ext
        metadata['download_ext'] = download_ext
        
        temp_download_name = f"{item.artist} - {item.title}{download_ext}"
        temp_download_name = re.sub(r'[<>:"/\\|?*]', '_', temp_download_name)
        temp_filepath = DOWNLOAD_DIR / temp_download_name
        
        artist = metadata.get('album_artist') or metadata.get('artist', 'Unknown Artist')
        album = metadata.get('album', 'Unknown Album')
        title = metadata.get('title', item.title)
        track_number = metadata.get('track_number')
        
        artist_folder = sanitize_path_component(artist)
        album_folder = sanitize_path_component(album)
        
        if track_number:
            track_str = str(track_number).zfill(2)
            final_filename = f"{track_str} - {sanitize_path_component(title)}{final_ext}"
        else:
            final_filename = f"{sanitize_path_component(title)}{final_ext}"
        
        final_filepath = DOWNLOAD_DIR / artist_folder / album_folder / final_filename
        
        # Check if file already exists
        if final_filepath.exists():
            log_warning(f"[Queue] File exists: {final_filename}")
            queue_manager.mark_completed(track_id, final_filename, metadata)
            if track_id in active_downloads:
                del active_downloads[track_id]
            return
        
        # Update status and start download
        queue_manager.update_active_progress(track_id, 0, 'downloading')
        active_downloads[track_id] = {'progress': 0, 'status': 'downloading'}
        
        # Call the existing download function
        await download_file_async(
            track_id,
            stream_url,
            temp_filepath,
            final_filename,
            metadata,
            item.organization_template,
            item.group_compilations,
            item.run_beets,
            item.embed_lyrics
        )
        
        # Mark as completed in queue manager
        queue_manager.mark_completed(track_id, final_filename, metadata)
        
    except Exception as e:
        log_error(f"[Queue] Failed to process {item.track_id}: {e}")
        traceback.print_exc()
        queue_manager.mark_failed(item.track_id, str(e))
        
        if item.track_id in active_downloads:
            del active_downloads[item.track_id]
