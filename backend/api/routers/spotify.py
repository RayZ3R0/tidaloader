import uuid
import json
import asyncio
import re
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.models import SpotifyGenerateRequest
from api.auth import require_auth, require_auth_stream
from api.state import lb_progress_queues
from api.services.spotify import process_spotify_playlist

router = APIRouter()

def extract_spotify_id(url: str) -> str:
    # Match playlist ID from various formats
    # https://open.spotify.com/playlist/37i9dQZF1DX5Ejj077clxu
    # spotify:playlist:37i9dQZF1DX5Ejj077clxu
    
    # Try Regex
    match = re.search(r'playlist[:/]([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    
    # If it looks like a clean ID (22 chars alphanumeric usually)
    if re.match(r'^[a-zA-Z0-9]{22}$', url):
        return url
        
    return url.split('/')[-1].split('?')[0] # Fallback basic split

@router.post("/api/spotify/generate")
async def generate_spotify_playlist(
    request: SpotifyGenerateRequest,
    background_tasks: BackgroundTasks,
    username: str = Depends(require_auth)
):
    playlist_id = extract_spotify_id(request.playlist_url)
    if not playlist_id:
         raise HTTPException(status_code=400, detail="Invalid Spotify Playlist URL")

    progress_id = str(uuid.uuid4())
    
    background_tasks.add_task(
        process_spotify_playlist,
        playlist_id,
        progress_id
    )
    
    return {"progress_id": progress_id}

@router.get("/api/spotify/progress/{progress_id}")
async def spotify_progress_stream(
    progress_id: str,
    username: str = Depends(require_auth_stream)
):
    async def event_generator():
        if progress_id not in lb_progress_queues:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid progress ID'})}\n\n"
            return
        
        queue = lb_progress_queues[progress_id]
        
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
            if progress_id in lb_progress_queues:
                del lb_progress_queues[progress_id]
    
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
