import logging
from typing import List, Optional, Literal, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from api.auth import require_auth
from api.clients import tidal_client
from playlist_manager import playlist_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# Models
class MonitorPlaylistRequest(BaseModel):
    uuid: str
    name: str # Name to be used for the playlist file/display
    frequency: Literal["manual", "daily", "weekly", "monthly", "yearly"] = "manual"
    quality: Literal["LOW", "HIGH", "LOSSLESS", "HI_RES"] = "LOSSLESS"
    source: Literal["tidal", "listenbrainz"] = "tidal"
    extra_config: Optional[Dict[str, Any]] = None
    use_playlist_folder: bool = False

class DeleteFilesRequest(BaseModel):
    files: List[str]

# Endpoints
@router.get("/api/playlists/search")
async def search_playlists_proxy(
    query: str,
    limit: int = 10,
    offset: int = 0,
    user: str = Depends(require_auth)
):
    """Proxy to Tidal search for playlists"""
    try:
        # Using tidal_client native search method
        results = tidal_client.search_playlists(query) 
        return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/playlists/monitored")
async def get_monitored_playlists(user: str = Depends(require_auth)):
    return playlist_manager.get_monitored_playlists()

@router.post("/api/playlists/monitor")
async def monitor_playlist(
    request: MonitorPlaylistRequest,
    background_tasks: BackgroundTasks,
    user: str = Depends(require_auth)
):
    """Add a playlist to monitoring and start initial sync"""
    try:
        playlist, created = playlist_manager.add_monitored_playlist(
            request.uuid, 
            request.name, 
            request.frequency, 
            request.quality,
            request.source,
            request.extra_config,
            request.use_playlist_folder
        )
        
        # Start initial sync in background only if new
        if created:
            logger.info(f"New playlist monitored {request.uuid}, triggering initial sync.")
            background_tasks.add_task(playlist_manager.sync_playlist, request.uuid)
        else:
            logger.info(f"Playlist {request.uuid} updated, skipping auto-sync.")
        
        return {"status": "success", "playlist": playlist}
    except Exception as e:
        logger.error(f"Failed to monitor playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/playlists/{uuid}")
async def stop_monitoring(uuid: str, user: str = Depends(require_auth)):
    playlist_manager.remove_monitored_playlist(uuid)
    return {"status": "success"}

@router.post("/api/playlists/{uuid}/sync")
async def sync_playlist_manual(
    uuid: str, 
    background_tasks: BackgroundTasks,
    user: str = Depends(require_auth)
):
    """Trigger a manual sync/download"""
    try:
        # Check existence
        if not playlist_manager.get_playlist(uuid):
            raise HTTPException(status_code=404, detail="Playlist not monitored")
            
        # Run synchronously for manual trigger to provide feedback
        result = await playlist_manager.sync_playlist(uuid)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/playlists/{uuid}/files")
async def get_playlist_files_endpoint(uuid: str, user: str = Depends(require_auth)):
    try:
        files = playlist_manager.get_playlist_files(uuid)
        return {"status": "success", "files": files}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get playlist files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/playlists/{uuid}/delete-files")
async def delete_playlist_files_endpoint(
    uuid: str, 
    request: DeleteFilesRequest,
    user: str = Depends(require_auth)
):
    try:
        result = playlist_manager.delete_playlist_files(uuid, request.files)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete playlist files: {e}")
        raise HTTPException(status_code=500, detail=str(e))
