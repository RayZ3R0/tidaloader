from pathlib import Path
import json
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from api.settings import settings, DOWNLOAD_DIR
from scheduler import PlaylistScheduler

from typing import Optional
from api.clients.jellyfin_client import jellyfin_client

router = APIRouter()

CONFIG_FILE = DOWNLOAD_DIR / "config.json"

class SystemSettings(BaseModel):
    sync_time: str
    organization_template: str = "{Artist}/{Album}/{TrackNumber} - {Title}"
    active_downloads: int = 3
    use_musicbrainz: bool = True
    run_beets: bool = False
    embed_lyrics: bool = False
    
    jellyfin_url: Optional[str] = None
    jellyfin_api_key: Optional[str] = None

def load_persistent_settings():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                if 'sync_time' in data:
                    settings.sync_time = data['sync_time']
                elif 'sync_hour' in data:
                    settings.sync_time = f"{data['sync_hour']:02d}:00"
                
                settings.organization_template = data.get('organization_template', settings.organization_template)
                settings.active_downloads = data.get('active_downloads', settings.active_downloads)
                settings.use_musicbrainz = data.get('use_musicbrainz', settings.use_musicbrainz)
                settings.run_beets = data.get('run_beets', settings.run_beets)
                settings.embed_lyrics = data.get('embed_lyrics', settings.embed_lyrics)
                settings.jellyfin_url = data.get('jellyfin_url', settings.jellyfin_url)
                settings.jellyfin_api_key = data.get('jellyfin_api_key', settings.jellyfin_api_key)
        except Exception:
            pass

# Load on module import (or startup)
load_persistent_settings()

@router.get("/api")
async def api_root():
    return {"status": "ok", "message": "Tidaloader API"}

@router.get("/api/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/api/system/settings")
async def get_settings():
    return {
        "sync_time": settings.sync_time,
        "organization_template": settings.organization_template,
        "active_downloads": settings.active_downloads,
        "use_musicbrainz": settings.use_musicbrainz,
        "run_beets": settings.run_beets,
        "embed_lyrics": settings.embed_lyrics,
        "jellyfin_url": settings.jellyfin_url,
        "jellyfin_api_key": settings.jellyfin_api_key
    }

@router.post("/api/system/settings")
async def update_settings(new_settings: SystemSettings):
    settings.sync_time = new_settings.sync_time
    settings.organization_template = new_settings.organization_template
    settings.active_downloads = new_settings.active_downloads
    settings.use_musicbrainz = new_settings.use_musicbrainz
    settings.run_beets = new_settings.run_beets
    settings.embed_lyrics = new_settings.embed_lyrics
    settings.jellyfin_url = new_settings.jellyfin_url
    settings.jellyfin_api_key = new_settings.jellyfin_api_key
    
    # Persist
    try:
        data = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
        
        data['sync_time'] = new_settings.sync_time
        data['organization_template'] = new_settings.organization_template
        data['active_downloads'] = new_settings.active_downloads
        data['use_musicbrainz'] = new_settings.use_musicbrainz
        data['run_beets'] = new_settings.run_beets
        data['embed_lyrics'] = new_settings.embed_lyrics
        data['jellyfin_url'] = new_settings.jellyfin_url
        data['jellyfin_api_key'] = new_settings.jellyfin_api_key
        
        # Cleanup old key if exists
        if 'sync_hour' in data:
             del data['sync_hour']
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Update scheduler
        scheduler = PlaylistScheduler()
        scheduler.reschedule_job(new_settings.sync_time)
        
        # Verify Jellyfin automatically if creds provided?
        # No, let explicit test handle it.
        
    except Exception as e:
        return {"status": "error", "message": str(e)}
        
    return {"status": "updated", "settings": new_settings.dict()}

class TestConnectionRequest(BaseModel):
    url: Optional[str] = None
    api_key: Optional[str] = None

@router.post("/api/system/jellyfin/test")
async def test_jellyfin_connection(request: TestConnectionRequest = None):
    try:
        # Use provided values from request body, or default to stored settings if empty
        url = request.url if request and request.url else None
        api_key = request.api_key if request and request.api_key else None
        
        info = jellyfin_client.get_system_info(url=url, api_key=api_key)
        return {"status": "success", "info": info}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/system/jellyfin/users")
async def get_jellyfin_users():
    try:
        users = jellyfin_client.get_users()
        return {"status": "success", "users": users}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/system/jellyfin/users/{user_id}/image")
async def get_jellyfin_user_image(user_id: str):
    from fastapi.responses import Response
    try:
        image_data = jellyfin_client.get_user_image(user_id)
        if image_data:
            return Response(content=image_data, media_type="image/jpeg")
        # Return 404 or empty to trigger fallback on frontend
        return Response(status_code=404)
    except Exception as e:
        return Response(status_code=500)

@router.post("/api/system/jellyfin/sync-covers")
async def sync_jellyfin_covers(background_tasks: BackgroundTasks):
    # Late import to avoid circular dependency if system imported by scheduler/playlist_manager
    from api.playlist_manager import playlist_manager
    
    background_tasks.add_task(playlist_manager.force_sync_covers)
    return {"status": "started", "message": "Global cover sync started in background"}
