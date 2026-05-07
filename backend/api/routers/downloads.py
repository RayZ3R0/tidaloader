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
from api.clients import tidal_client
from api.utils.logging import log_info, log_error, log_warning, log_success, log_step
from api.utils.extraction import extract_stream_url, extract_stream_url_with_qobuz_fallback
from api.services.files import sanitize_path_component
from api.services.download import download_file_async
from queue_manager import queue_manager, QueueItem, QUEUE_AUTO_PROCESS, MAX_CONCURRENT_DOWNLOADS
import database as db

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
    """Get download states from queue manager (replaces download_state_manager)"""
    state = queue_manager.get_state()
    return {
        "active": {str(item['track_id']): item for item in state.get('active', [])},
        "completed": {str(item['track_id']): item for item in state.get('completed', [])},
        "failed": {str(item['track_id']): item for item in state.get('failed', [])}
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
        
        # Check queue manager for current state
        active_info = queue_manager._active.get(track_id)
        if active_info:
            progress = active_info.get('progress', 0)
            status = active_info.get('status', 'downloading')
            yield f"data: {json.dumps({'progress': progress, 'track_id': track_id, 'status': status})}\n\n"
        
        try:
            while True:
                current_progress = -1
                current_status = 'unknown'
                
                # Check in-memory active downloads
                if track_id in queue_manager._active:
                    info = queue_manager._active[track_id]
                    current_progress = info.get('progress', 0)
                    current_status = info.get('status', 'downloading')
                else:
                    # Check DB for completed/failed
                    queue_items = db.get_queue_items()
                    for item in queue_items:
                        if item['track_id'] == track_id:
                            if item['status'] == 'completed':
                                current_status = 'completed'
                                current_progress = 100
                            elif item['status'] == 'failed':
                                current_status = 'failed'
                                current_progress = 0
                            break
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
        # Check if already active in queue manager
        if request.track_id in queue_manager._active:
            current_status = queue_manager._active[request.track_id].get('status')
            if current_status in ['starting', 'downloading', 'transcoding']:
                log_warning(f"Download already in progress for track {request.track_id}")
                return {
                    "status": "downloading",
                    "filename": "In progress",
                    "message": "Download already in progress"
                }
        
        # Check DB for recently completed
        completed_items = db.get_queue_items("completed")
        for item in completed_items:
            if item['track_id'] == request.track_id:
                saved_path = None
                if item.get('metadata_json'):
                    try:
                        meta = json.loads(item['metadata_json'])
                        saved_path = meta.get('final_path')
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                file_still_exists = saved_path and Path(saved_path).exists()
                
                if file_still_exists:
                    log_warning(f"Track {request.track_id} already completed")
                    return {
                        "status": "exists",
                        "filename": item.get('filename', 'Completed'),
                        "message": "Download already completed"
                    }
                else:
                    log_info(f"Track {request.track_id} was completed but file not found, allowing re-download")
                    break

        requested_quality = request.quality.upper() if request.quality else "LOSSLESS"
        
        # Mark as starting in queue manager
        queue_manager._active[request.track_id] = {
            'progress': 0,
            'status': 'starting'
        }
        
        log_step("1/4", "Getting track metadata...")
        
        is_mp3_request = requested_quality in MP3_QUALITY_MAP
        is_opus_request = requested_quality in OPUS_QUALITY_MAP
        source_quality = 'LOSSLESS' if is_mp3_request or is_opus_request else requested_quality
        
        track_info = tidal_client.get_track(request.track_id, source_quality)
        if not track_info:
            if request.track_id in queue_manager._active:
                del queue_manager._active[request.track_id]
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
            
            # Fallback for date if streamStartDate is missing (Issue #38)
            if not metadata['date'] and isinstance(album_data, dict):
                 metadata['date'] = album_data.get('releaseDate') or str(album_data.get('releaseYear') or '')
            
            # Second fallback: Fetch extended metadata (Issue #38 persistent)
            if not metadata['date']:
                 log_info(f"Date missing, fetching extended metadata for track {request.track_id}...")
                 try:
                     extended_data = tidal_client.get_track_metadata(request.track_id)
                     if extended_data:
                         if extended_data.get('streamStartDate'):
                             metadata['date'] = extended_data.get('streamStartDate').split('T')[0]
                         
                         if not metadata['date']:
                             ext_album = extended_data.get('album', {})
                             if isinstance(ext_album, dict):
                                 metadata['date'] = ext_album.get('releaseDate') or str(ext_album.get('releaseYear') or '')
                 except Exception as e:
                     log_warning(f"Failed to fetch extended metadata: {e}")
            if isinstance(album_data, dict) and album_data.get('title'):
                metadata['album'] = album_data.get('title')
                metadata['album_artist'] = album_data.get('artist', {}).get('name') if isinstance(album_data.get('artist'), dict) else None
                metadata['total_tracks'] = album_data.get('numberOfTracks')
                metadata['total_discs'] = album_data.get('numberOfVolumes')
                
                # Store Tidal IDs in metadata for DB recording (NOT for file embedding)
                metadata['tidal_track_id'] = str(track_data.get('id', ''))
                metadata['tidal_artist_id'] = str(artist_data.get('id', ''))
                metadata['tidal_album_id'] = str(album_data.get('id', ''))
                
                cover_id = album_data.get('cover')
                if cover_id:
                    cover_id_str = str(cover_id).replace('-', '/')
                    metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
                

                album_artist = metadata.get('album_artist') or ''
                if album_data.get('type') == 'COMPILATION' or (album_artist and album_artist.lower() in ['various artists', 'various']):
                    metadata['compilation'] = True
            else:

                metadata['album'] = request.album
                if request.cover:
                    cover_id_str = str(request.cover).replace('-', '/')
                    metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
        else:

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
        stream_result = extract_stream_url_with_qobuz_fallback(track_info, source_quality)
        stream_url = stream_result.get('url')
        stream_source = stream_result.get('source', 'unknown')
        
        if not stream_url:
            if request.track_id in queue_manager._active:
                del queue_manager._active[request.track_id]
            raise HTTPException(status_code=404, detail="Stream URL not found")
        
        if stream_source == 'qobuz':
            log_success(f"Stream URL (Qobuz): {stream_url[:60]}...")
        else:
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
            if request.track_id in queue_manager._active:
                del queue_manager._active[request.track_id]
            # Record in DB even if file exists already
            queue_manager.mark_completed(request.track_id, final_filename, metadata)
            return {
                "status": "exists",
                "filename": final_filename,
                "path": str(final_filepath),
                "message": f"File already exists: {artist_folder}/{album_folder}/{final_filename}"
            }
        
        queue_manager._active[request.track_id] = {
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
        if request.track_id in queue_manager._active:
            del queue_manager._active[request.track_id]
        raise
    except Exception as e:
        log_error(f"Download error: {e}")
        traceback.print_exc()
        
        if request.track_id in queue_manager._active:
            del queue_manager._active[request.track_id]
        
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# QUEUE API ENDPOINTS
# ============================================================================

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
    use_musicbrainz: bool = True


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
            album_artist=track.album_artist or "",
            album_id=track.album_id,
            track_number=track.track_number,
            cover=track.cover,
            quality=track.quality or "HIGH",
            tidal_track_id=track.tidal_track_id,
            tidal_artist_id=track.tidal_artist_id,
            tidal_album_id=track.tidal_album_id,
            target_format=track.target_format,
            bitrate_kbps=track.bitrate_kbps,
            run_beets=track.run_beets,
            embed_lyrics=track.embed_lyrics,
            organization_template=track.organization_template,
            group_compilations=track.group_compilations,
            use_musicbrainz=track.use_musicbrainz,
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


@router.get("/api/queue/completed")
async def get_completed_tracks(
    limit: int = 50,
    offset: int = 0,
    order: str = 'desc',
    username: str = Depends(require_auth)
):
    """Get paginated completed tracks for infinite scroll.
    
    Args:
        limit: Number of items per page (default 50)
        offset: Starting position (default 0)
        order: Sort order 'asc' or 'desc' (default 'desc' for newest first)
    """
    total = db.get_queue_items_count("completed")
    items = db.get_queue_items("completed", limit=limit, offset=offset, order=order)
    
    return {
        "items": [queue_manager._db_row_to_result_dict(row) for row in items],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + len(items)) < total
    }


# ============================================================================
# QUEUE ITEM PROCESSOR
# ============================================================================

import aiohttp

async def validate_stream_url(stream_url: str) -> bool:
    """
    Validate that a stream URL returns audio content (not XML error).
    Uses a HEAD request to check content-type before downloading.
    """
    if not stream_url:
        return False
    
    try:
        timeout = aiohttp.ClientTimeout(total=15, connect=10)
        async with aiohttp.ClientSession() as session:
            async with session.head(stream_url, timeout=timeout, allow_redirects=True) as response:
                if response.status != 200:
                    return False
                content_type = response.headers.get('content-type', '').lower()
                # Valid audio content types
                if any(t in content_type for t in ['audio/', 'application/octet-stream', 'binary']):
                    return True
                # XML or text = error response
                if 'xml' in content_type or 'text' in content_type:
                    return False
                # Unknown content type - assume valid if not explicitly bad
                return True
    except Exception:
        # If HEAD fails, try anyway (some servers don't support HEAD)
        return True

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
        
        is_mp3_request = requested_quality in MP3_QUALITY_MAP
        is_opus_request = requested_quality in OPUS_QUALITY_MAP
        source_quality = 'LOSSLESS' if is_mp3_request or is_opus_request else requested_quality
        
        # Pre-fetch track metadata to get ISRC before attempting playback info.
        # This lets us fall back to Qobuz if all Tidal endpoints fail.
        track_metadata = None
        track_isrc = None
        try:
            track_metadata = tidal_client.get_track_metadata(track_id)
            if track_metadata:
                track_isrc = track_metadata.get('isrc')
        except Exception as e:
            log_warning(f"[Queue] Could not pre-fetch metadata for {track_id}: {e}")

        track_info = tidal_client.get_track(track_id, source_quality)

        if not track_info and track_isrc:
            log_info(f"[Queue] Tidal unavailable, trying Qobuz (ISRC: {track_isrc})...")
            qobuz_result = tidal_client.get_qobuz_stream_url(track_isrc, source_quality)
            if qobuz_result and qobuz_result.get('url'):
                track_info = [
                    {
                        'duration': track_metadata.get('duration', 0) if track_metadata else 0,
                        'id': track_id,
                        'isrc': track_isrc,
                        'title': track_metadata.get('title', item.title) if track_metadata else item.title,
                    },
                    {
                        'OriginalTrackUrl': qobuz_result['url'],
                        'trackId': track_id,
                        'audioQuality': source_quality,
                        'source': 'qobuz',
                        'endpoint': qobuz_result.get('endpoint'),
                    },
                ]
                if qobuz_result.get('rgInfo'):
                    track_info[1]['replayGain'] = qobuz_result['rgInfo']
                log_success(f"[Queue] Qobuz stream via {qobuz_result.get('endpoint')}")
        
        if not track_info:
            raise Exception("Track not found (Playback Info)")

        if isinstance(track_info, list) and len(track_info) > 0:
            track_data = track_info[0]
        else:
            track_data = track_info 

        # Get stream URL with quality fallback for HI_RES/HI_RES_LOSSLESS
        stream_result = extract_stream_url_with_qobuz_fallback(track_info, source_quality)
        stream_url = stream_result.get('url')
        stream_source = stream_result.get('source', 'unknown')
        
        # Validate the stream URL returns actual audio content (not XML error)
        if stream_url and source_quality in ('HI_RES', 'HI_RES_LOSSLESS') and stream_source == 'tidal':
            is_valid = await validate_stream_url(stream_url)
            if not is_valid:
                log_warning(f"[Queue] {source_quality} stream returns invalid content for {item.title}, falling back to LOSSLESS")
                stream_url = None
        
        # Fallback: If HI_RES or HI_RES_LOSSLESS requested but no stream URL found, try LOSSLESS
        if not stream_url and source_quality in ('HI_RES', 'HI_RES_LOSSLESS'):
            log_warning(f"[Queue] {source_quality} not available for {item.title}, falling back to LOSSLESS")
            source_quality = 'LOSSLESS'
            track_info = tidal_client.get_track(track_id, source_quality)
            if track_info:
                if isinstance(track_info, list) and len(track_info) > 0:
                    track_data = track_info[0]
                else:
                    track_data = track_info
                stream_result = extract_stream_url_with_qobuz_fallback(track_info, source_quality)
                stream_url = stream_result.get('url')
                stream_source = stream_result.get('source', 'unknown')

        metadata = {
            'quality': requested_quality,
            'source_quality': source_quality,
            'title': item.title,
            'artist': item.artist,
            'tidal_track_id': item.tidal_track_id or str(track_id),
            'tidal_artist_id': item.tidal_artist_id,
            'tidal_album_id': item.tidal_album_id,
        }
        
        # Extract actual album/track info from Tidal API response
        if isinstance(track_data, dict):
            album_data = track_data.get('album', {})
            if isinstance(album_data, dict) and album_data.get('title'):
                metadata['album'] = album_data.get('title')
                metadata['album_artist'] = album_data.get('artist', {}).get('name') if isinstance(album_data.get('artist'), dict) else None
                metadata['total_tracks'] = album_data.get('numberOfTracks')
                metadata['total_discs'] = album_data.get('numberOfVolumes')
                # Update tidal_album_id from actual track data
                if album_data.get('id'):
                    metadata['tidal_album_id'] = str(album_data.get('id'))
                
                # Check for compilation
                album_artist = metadata.get('album_artist') or ''
                if album_data.get('type') == 'COMPILATION' or (album_artist and album_artist.lower() in ['various artists', 'various']):
                    metadata['compilation'] = True
            else:
                metadata['album'] = item.album
                metadata['album_artist'] = item.album_artist or item.artist
            
            metadata['track_number'] = track_data.get('trackNumber') or item.track_number
            metadata['disc_number'] = track_data.get('volumeNumber')
            metadata['date'] = track_data.get('streamStartDate', '').split('T')[0] if track_data.get('streamStartDate') else None
            
            # Fallback for date if streamStartDate is missing (Issue #38)
            if not metadata['date'] and isinstance(album_data, dict):
                 metadata['date'] = album_data.get('releaseDate') or str(album_data.get('releaseYear') or '')

            # Second fallback: Fetch extended metadata (Issue #38 persistent)
            if not metadata['date']:
                 try:
                     extended_data = tidal_client.get_track_metadata(track_id)
                     if extended_data:
                         if extended_data.get('streamStartDate'):
                             metadata['date'] = extended_data.get('streamStartDate').split('T')[0]
                         
                         if not metadata['date']:
                             ext_album = extended_data.get('album', {})
                             if isinstance(ext_album, dict):
                                 metadata['date'] = ext_album.get('releaseDate') or str(ext_album.get('releaseYear') or '')
                 except Exception:
                     pass
            
            # Update artist ID from track data if available
            artist_data = track_data.get('artist', {})
            if isinstance(artist_data, dict) and artist_data.get('id'):
                metadata['tidal_artist_id'] = str(artist_data.get('id'))
        else:
            # Fallback to queue item data
            metadata['album'] = item.album
            metadata['album_artist'] = item.album_artist or item.artist
            metadata['track_number'] = item.track_number
        
        if is_mp3_request:
            metadata['target_format'] = 'mp3'
            metadata['bitrate_kbps'] = MP3_QUALITY_MAP[requested_quality]
        elif is_opus_request:
            metadata['target_format'] = 'opus'
            metadata['bitrate_kbps'] = OPUS_QUALITY_MAP[requested_quality]
        
        # Add cover URL from queue item
        if item.cover:
            cover_id_str = str(item.cover).replace('-', '/')
            metadata['cover_url'] = f"https://resources.tidal.com/images/{cover_id_str}/640x640.jpg"
            

        log_info(f"[Queue] Extracted IDs for {item.title}:")
        log_info(f"  Track ID: {metadata.get('tidal_track_id')}")
        log_info(f"  Artist ID: {metadata.get('tidal_artist_id')}")
        log_info(f"  Album ID: {metadata.get('tidal_album_id')}")
        log_info(f"  From Queue Item: {bool(item.tidal_artist_id)}")
        
        # Verify stream URL was found (after potential fallback)
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
        
        # Use shared logic for consistent path resolution
        from api.services.files import get_output_relative_path as calc_rel_path
        
        path_metadata = {
            'artist': artist,
            'album': album,
            'title': title,
            'track_number': track_number,
            'album_artist': metadata.get('album_artist'),
            'compilation': metadata.get('compilation'),
            'file_ext': final_ext,
            'date': metadata.get('date')
        }
        
        rel_path = calc_rel_path(
            path_metadata, 
            template=item.organization_template, 
            group_compilations=item.group_compilations
        )
        final_filepath = DOWNLOAD_DIR / rel_path
        final_filename = final_filepath.name
        
        log_info(f"[Queue] Calculated target path: {rel_path}")
        
        # Check if file already exists
        if final_filepath.exists():
            log_warning(f"[Queue] File exists: {final_filename}")
            queue_manager.mark_completed(track_id, final_filename, metadata)
            return
        
        # Update status and start download
        queue_manager.update_active_progress(track_id, 0, 'downloading')
        

        await download_file_async(
            track_id,
            stream_url,
            temp_filepath,
            final_filename,
            metadata,
            item.organization_template,
            item.group_compilations,
            item.run_beets,
            item.embed_lyrics,
            item.use_musicbrainz
        )
        
    except Exception as e:
        log_error(f"[Queue] Failed to process {item.track_id}: {e}")
        traceback.print_exc()
        queue_manager.mark_failed(item.track_id, str(e))
