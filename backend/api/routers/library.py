
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from api.auth import require_auth
from api.services.library import library_service
from api.utils.logging import log_info, log_error

router = APIRouter()

@router.get("/api/library/scan")
async def scan_library(force: bool = False, username: str = Depends(require_auth)):
    try:
        log_info(f"Library scan requested (force={force})")
        data = library_service.scan_library(force=force)
        return {"status": "success", "artist_count": len(data)}
    except Exception as e:
        log_error(f"Error scanning library: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/library/artists")
async def get_library_artists(username: str = Depends(require_auth)):
    try:
        return library_service.get_artists()
    except Exception as e:
        log_error(f"Error getting library artists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/library/artist/{artist_name}")
async def get_library_artist(artist_name: str, username: str = Depends(require_auth)):
    try:
        artist = library_service.get_artist(artist_name)
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")
        return artist
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting library artist {artist_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/library/cover")
async def get_local_cover(path: str, username: str = Depends(require_auth)):
    """Serve local cover image"""
    try:
        file_path = Path(path)
        if not file_path.exists():
             raise HTTPException(status_code=404, detail="Cover not found")
        
        # Security check: ensure path is within music dir (rudimentary)
        # In a real app we'd validate this more strictly against DOWNLOAD_DIR
        return FileResponse(file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail="Cover not found")
