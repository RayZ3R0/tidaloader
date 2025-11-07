from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import sys
from pathlib import Path
import time
import aiofiles
import re
import requests
import asyncio
from contextlib import asynccontextmanager
import json
import aiohttp

sys.path.append(str(Path(__file__).parent.parent))

from tidal_client import TidalAPIClient
from troi_integration import TroiIntegration, TroiTrack

app = FastAPI(title="Troi Tidal Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tidal_client = TidalAPIClient()

class TroiGenerateRequest(BaseModel):
    username: str
    playlist_type: str = "periodic-jams"

class TrackSearchResult(BaseModel):
    id: int
    title: str
    artist: str
    album: Optional[str] = None
    duration: Optional[int] = None
    cover: Optional[str] = None
    quality: Optional[str] = None

class TroiTrackResponse(BaseModel):
    title: str
    artist: str
    mbid: Optional[str]
    tidal_id: Optional[int]
    tidal_exists: bool
    album: Optional[str]

class DownloadTrackRequest(BaseModel):
    track_id: int
    artist: str
    title: str
    quality: str = "LOSSLESS"

DOWNLOAD_DIR = Path(__file__).parent.parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

active_downloads = {}

def extract_items(result, key: str) -> List:
    if not result:
        return []
    
    if isinstance(result, list):
        if len(result) > 0 and isinstance(result[0], dict):
            first_elem = result[0]
            if key in first_elem:
                nested = first_elem[key]
                if isinstance(nested, dict) and 'items' in nested:
                    return nested['items']
                elif isinstance(nested, list):
                    return nested
        return result
    
    if isinstance(result, dict):
        if key in result and isinstance(result[key], dict):
            return result[key].get('items', [])
        
        if 'items' in result:
            return result['items']
    
    return []

def extract_track_data(track_response) -> List:
    if not track_response:
        return []
    
    if isinstance(track_response, list):
        for item in track_response:
            if isinstance(item, dict) and 'items' in item:
                return item['items']
        return []
    
    if isinstance(track_response, dict):
        return track_response.get('items', [])
    
    return []

def extract_stream_url(track_data) -> Optional[str]:
    if isinstance(track_data, list):
        entries = track_data
    else:
        entries = [track_data]
    
    for entry in entries:
        if isinstance(entry, dict) and 'OriginalTrackUrl' in entry:
            return entry['OriginalTrackUrl']
    
    for entry in entries:
        if isinstance(entry, dict) and 'manifest' in entry:
            manifest = entry['manifest']
            try:
                import base64
                decoded = base64.b64decode(manifest).decode('utf-8')
                
                try:
                    import json
                    manifest_json = json.loads(decoded)
                    if 'urls' in manifest_json and manifest_json['urls']:
                        return manifest_json['urls'][0]
                except json.JSONDecodeError:
                    pass
                
                import re
                url_match = re.search(r'https?://[^\s"]+', decoded)
                if url_match:
                    return url_match.group(0)
            except Exception as e:
                print(f"Failed to decode manifest: {e}")
    
    return None

async def download_file_async(track_id: int, stream_url: str, filepath: Path, filename: str):
    try:
        print(f"[3/3] Downloading {filename}...")
        
        if track_id not in active_downloads:
            active_downloads[track_id] = {'progress': 0, 'status': 'downloading'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    print(f"✗ Download failed: {error_msg}")
                    if track_id in active_downloads:
                        active_downloads[track_id] = {'progress': 0, 'status': 'failed'}
                        await asyncio.sleep(2)
                        del active_downloads[track_id]
                    return
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                active_downloads[track_id] = {
                                    'progress': progress,
                                    'status': 'downloading'
                                }
                                print(f"  Progress: {progress}%", end='\r')
                            
                            await asyncio.sleep(0.01)
        
        active_downloads[track_id] = {
            'progress': 100,
            'status': 'completed'
        }
        
        file_size_mb = filepath.stat().st_size / 1024 / 1024
        print(f"\n✓ Downloaded: {filename} ({file_size_mb:.2f} MB)")
        print(f"  Location: {filepath}")
        print(f"{'='*60}\n")
        
        await asyncio.sleep(2)
        
        if track_id in active_downloads:
            del active_downloads[track_id]
        
    except Exception as e:
        print(f"✗ Download error: {e}")
        import traceback
        traceback.print_exc()
        
        if track_id in active_downloads:
            active_downloads[track_id] = {'progress': 0, 'status': 'failed'}
            await asyncio.sleep(2)
            del active_downloads[track_id]
        
        if filepath.exists():
            try:
                filepath.unlink()
                print(f"  Cleaned up partial file: {filename}")
            except Exception:
                pass

@app.get("/api")
async def api_root():
    return {"status": "ok", "message": "Troi Tidal Downloader API"}

@app.post("/api/troi/generate")
async def generate_troi_playlist(request: TroiGenerateRequest):
    try:
        print(f"Generating Troi playlist for {request.username}...")
        tracks = TroiIntegration.generate_playlist(
            request.username,
            request.playlist_type
        )
        print(f"Generated {len(tracks)} tracks from Troi")
        
        validated_tracks = []
        for i, track in enumerate(tracks, 1):
            print(f"[{i}/{len(tracks)}] Validating: {track.artist} - {track.title}")
            
            query = f"{track.artist} {track.title}"
            result = tidal_client.search_tracks(query)
            
            if result:
                tidal_tracks = extract_items(result, 'tracks')
                
                if tidal_tracks and len(tidal_tracks) > 0:
                    first_track = tidal_tracks[0]
                    track.tidal_id = first_track.get('id')
                    track.tidal_exists = True
                    
                    album_data = first_track.get('album', {})
                    track.album = album_data.get('title') if isinstance(album_data, dict) else None
                    
                    print(f"  ✓ Found on Tidal - ID: {track.tidal_id}")
                else:
                    print(f"  ✗ Not found on Tidal")
            else:
                print(f"  ✗ API returned None")
            
            validated_tracks.append(TroiTrackResponse(
                title=track.title,
                artist=track.artist,
                mbid=track.mbid,
                tidal_id=track.tidal_id,
                tidal_exists=track.tidal_exists,
                album=track.album
            ))
            
            time.sleep(0.1)
        
        found_count = sum(1 for t in validated_tracks if t.tidal_exists)
        print(f"\nValidation complete: {found_count}/{len(validated_tracks)} found on Tidal")
        
        return {
            "tracks": validated_tracks,
            "count": len(validated_tracks),
            "found_on_tidal": found_count
        }
        
    except Exception as e:
        print(f"Error generating playlist: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/tracks")
async def search_tracks(q: str):
    try:
        result = tidal_client.search_tracks(q)
        
        if not result:
            return {"items": []}
        
        tracks = extract_items(result, 'tracks')
        
        return {
            "items": [
                TrackSearchResult(
                    id=track['id'],
                    title=track['title'],
                    artist=track.get('artist', {}).get('name', 'Unknown'),
                    album=track.get('album', {}).get('title'),
                    duration=track.get('duration'),
                    cover=track.get('album', {}).get('cover'),
                    quality=track.get('audioQuality')
                )
                for track in tracks
            ]
        }
    except Exception as e:
        print(f"Error searching tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/albums")
async def search_albums(q: str):
    try:
        result = tidal_client.search_albums(q)
        
        if not result:
            return {"items": []}
        
        albums = extract_items(result, 'albums')
        
        return {"items": albums}
    except Exception as e:
        print(f"Error searching albums: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search/artists")
async def search_artists(q: str):
    try:
        print(f"Searching for artist: {q}")
        result = tidal_client.search_artists(q)
        
        if not result:
            print("No results from API")
            return {"items": []}
        
        print(f"API response type: {type(result)}")
        
        artists = extract_items(result, 'artists')
        
        print(f"Found {len(artists)} artists")
        if artists:
            print(f"First artist: {artists[0].get('name', 'Unknown')} (ID: {artists[0].get('id')})")
        
        return {"items": artists}
    except Exception as e:
        print(f"Error searching artists: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/album/{album_id}/tracks")
async def get_album_tracks(album_id: int):
    try:
        print(f"Fetching tracks for album {album_id}...")
        result = tidal_client.get_album(album_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Album not found")
        
        print(f"Album API response type: {type(result)}")
        
        album_metadata = None
        raw_items = []
        
        if isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], dict):
                if 'title' in result[0] and 'id' in result[0]:
                    album_metadata = result[0]
            
            for item in result:
                if isinstance(item, dict) and 'items' in item:
                    raw_items = item['items']
                    break
        elif isinstance(result, dict):
            if 'items' in result:
                raw_items = result['items']
            if 'title' in result and 'id' in result:
                album_metadata = result
        
        print(f"Found album metadata: {album_metadata is not None}")
        print(f"Found {len(raw_items)} raw items")
        
        tracks = []
        for raw_item in raw_items:
            if not raw_item or not isinstance(raw_item, dict):
                continue
            
            track_data = raw_item.get('item', raw_item)
            
            if not isinstance(track_data, dict):
                continue
            
            if album_metadata:
                if 'album' not in track_data or not track_data['album']:
                    track_data['album'] = album_metadata
                elif isinstance(track_data.get('album'), dict):
                    track_data['album'] = {
                        **album_metadata,
                        **track_data['album']
                    }
            
            tracks.append(track_data)
        
        print(f"Extracted {len(tracks)} tracks")
        
        track_results = []
        for track in tracks:
            try:
                track_id = track.get('id')
                if not track_id:
                    print(f"Warning: Track missing ID: {track.get('title', 'Unknown')}")
                    continue
                
                artist_name = "Unknown"
                if 'artist' in track:
                    if isinstance(track['artist'], dict):
                        artist_name = track['artist'].get('name', 'Unknown')
                    elif isinstance(track['artist'], str):
                        artist_name = track['artist']
                elif 'artists' in track and track['artists']:
                    first_artist = track['artists'][0]
                    if isinstance(first_artist, dict):
                        artist_name = first_artist.get('name', 'Unknown')
                
                album_dict = track.get('album')
                if isinstance(album_dict, dict):
                    album_title = album_dict.get('title')
                    album_cover = album_dict.get('cover')
                else:
                    album_title = None
                    album_cover = None
                
                track_results.append(TrackSearchResult(
                    id=track_id,
                    title=track.get('title', 'Unknown'),
                    artist=artist_name,
                    album=album_title,
                    duration=track.get('duration'),
                    cover=album_cover or track.get('cover'),
                    quality=track.get('audioQuality')
                ))
            except Exception as e:
                print(f"Error processing track: {e}")
                continue
        
        print(f"Successfully processed {len(track_results)} tracks")
        
        response_data = {"items": track_results}
        
        if album_metadata:
            response_data["album"] = {
                "id": album_metadata.get('id'),
                "title": album_metadata.get('title'),
                "cover": album_metadata.get('cover'),
                "artist": album_metadata.get('artist'),
                "releaseDate": album_metadata.get('releaseDate'),
                "numberOfTracks": album_metadata.get('numberOfTracks'),
                "numberOfVolumes": album_metadata.get('numberOfVolumes'),
            }
            print(f"Including album metadata: {album_metadata.get('title')}")
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting album tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/artist/{artist_id}")
async def get_artist(artist_id: int):
    try:
        print(f"Fetching artist {artist_id}...")
        result = tidal_client.get_artist(artist_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Artist not found")
        
        print(f"Artist API response type: {type(result)}")
        
        artist_data = None
        tracks = []
        albums = []
        visited = set()
        
        def is_track_like(obj):
            if not isinstance(obj, dict):
                return False
            return all(key in obj for key in ['id', 'title', 'duration']) and 'album' in obj
        
        def is_album_like(obj):
            if not isinstance(obj, dict):
                return False
            return all(key in obj for key in ['id', 'title', 'cover'])
        
        def is_artist_like(obj):
            if not isinstance(obj, dict):
                return False
            return all(key in obj for key in ['id', 'name', 'type'])
        
        def scan_value(value, depth=0):
            if depth > 10:
                return
            
            if not value:
                return
            
            if isinstance(value, list):
                for item in value:
                    scan_value(item, depth + 1)
                return
            
            if not isinstance(value, dict):
                return
            
            obj_id = id(value)
            if obj_id in visited:
                return
            visited.add(obj_id)
            
            if is_artist_like(value):
                nonlocal artist_data
                if not artist_data:
                    artist_data = value
            
            if 'items' in value and isinstance(value['items'], list):
                for item in value['items']:
                    if not isinstance(item, dict):
                        continue
                    
                    actual_item = item.get('item', item)
                    
                    if is_track_like(actual_item):
                        tracks.append(actual_item)
                    elif is_album_like(actual_item):
                        albums.append(actual_item)
            
            if 'modules' in value and isinstance(value['modules'], list):
                for module in value['modules']:
                    if isinstance(module, dict):
                        if 'pagedList' in module:
                            paged_list = module['pagedList']
                            if isinstance(paged_list, dict):
                                scan_value(paged_list, depth + 1)
                        
                        scan_value(module, depth + 1)
            
            for nested_value in value.values():
                scan_value(nested_value, depth + 1)
        
        scan_value(result)
        
        if not artist_data:
            if tracks and 'artist' in tracks[0]:
                artist_obj = tracks[0]['artist']
                if isinstance(artist_obj, dict):
                    artist_data = artist_obj
            
            elif albums and 'artist' in albums[0]:
                artist_obj = albums[0]['artist']
                if isinstance(artist_obj, dict):
                    artist_data = artist_obj
        
        if not artist_data:
            artist_data = {
                'id': artist_id,
                'name': 'Unknown Artist'
            }
        
        tracks_sorted = sorted(
            tracks,
            key=lambda t: t.get('popularity', 0),
            reverse=True
        )[:50]
        
        def get_album_timestamp(album):
            release_date = album.get('releaseDate')
            if not release_date:
                return 0
            try:
                from datetime import datetime
                return datetime.fromisoformat(release_date.replace('Z', '+00:00')).timestamp()
            except:
                return 0
        
        albums_sorted = sorted(
            albums,
            key=get_album_timestamp,
            reverse=True
        )
        
        print(f"Found: {len(tracks_sorted)} tracks, {len(albums_sorted)} albums")
        if tracks_sorted:
            print(f"Sample track: {tracks_sorted[0].get('title', 'Unknown')}")
        if albums_sorted:
            print(f"Sample album: {albums_sorted[0].get('title', 'Unknown')}")
        
        return {
            "artist": artist_data,
            "tracks": tracks_sorted,
            "albums": albums_sorted
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting artist: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/start")
async def start_download(background_tasks: BackgroundTasks):
    return {"status": "started"}

@app.get("/api/download/stream/{track_id}")
async def get_stream_url(track_id: int, quality: str = "LOSSLESS"):
    try:
        print(f"Getting stream URL for track {track_id} at {quality} quality...")
        
        track_data = tidal_client.get_track(track_id, quality)
        
        if not track_data:
            raise HTTPException(status_code=404, detail="Track not found")
        
        stream_url = extract_stream_url(track_data)
        
        if not stream_url:
            raise HTTPException(status_code=404, detail="Stream URL not found")
        
        print(f"Found stream URL: {stream_url[:50]}...")
        
        return {
            "stream_url": stream_url,
            "track_id": track_id,
            "quality": quality
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting stream URL: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/progress/{track_id}")
async def download_progress_stream(track_id: int):
    async def event_generator():
        last_progress = -1
        no_data_count = 0
        max_no_data = 10
        
        while True:
            if track_id in active_downloads:
                download_info = active_downloads[track_id]
                progress = download_info.get('progress', 0)
                status = download_info.get('status', 'downloading')
                
                if progress != last_progress:
                    yield f"data: {json.dumps({'progress': progress, 'track_id': track_id, 'status': status})}\n\n"
                    last_progress = progress
                    no_data_count = 0
                
                if progress >= 100 or status == 'completed':
                    yield f"data: {json.dumps({'progress': 100, 'track_id': track_id, 'status': 'completed'})}\n\n"
                    break
            else:
                no_data_count += 1
                
                if no_data_count >= max_no_data:
                    yield f"data: {json.dumps({'progress': 0, 'track_id': track_id, 'status': 'not_found'})}\n\n"
                    break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/download/track")
async def download_track_server_side(
    request: DownloadTrackRequest,
    background_tasks: BackgroundTasks
):
    try:
        print(f"\n{'='*60}")
        print(f"Download Request:")
        print(f"  Track ID: {request.track_id}")
        print(f"  Artist: {request.artist}")
        print(f"  Title: {request.title}")
        print(f"  Quality: {request.quality}")
        print(f"{'='*60}\n")
        
        active_downloads[request.track_id] = {
            'progress': 0,
            'status': 'starting'
        }
        
        print(f"[1/3] Getting stream URL...")
        track_data = tidal_client.get_track(request.track_id, request.quality)
        if not track_data:
            del active_downloads[request.track_id]
            raise HTTPException(status_code=404, detail="Track not found")
        
        stream_url = extract_stream_url(track_data)
        if not stream_url:
            del active_downloads[request.track_id]
            raise HTTPException(status_code=404, detail="Stream URL not found")
        
        print(f"✓ Stream URL: {stream_url[:60]}...")
        
        filename = f"{request.artist} - {request.title}.flac"
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filepath = DOWNLOAD_DIR / filename
        
        print(f"\n[2/3] Target file: {filepath}")
        
        if filepath.exists():
            print(f"⚠️  File already exists, skipping download")
            del active_downloads[request.track_id]
            return {
                "status": "exists",
                "filename": filename,
                "path": str(filepath),
                "message": f"File already exists: {filename}"
            }
        
        active_downloads[request.track_id] = {
            'progress': 0,
            'status': 'downloading'
        }
        
        background_tasks.add_task(
            download_file_async,
            request.track_id,
            stream_url,
            filepath,
            filename
        )
        
        return {
            "status": "downloading",
            "filename": filename,
            "path": str(filepath),
            "message": f"Download started: {filename}"
        }
        
    except HTTPException:
        if request.track_id in active_downloads:
            del active_downloads[request.track_id]
        raise
    except Exception as e:
        print(f"✗ Download error: {e}")
        import traceback
        traceback.print_exc()
        
        if request.track_id in active_downloads:
            del active_downloads[request.track_id]
        
        raise HTTPException(status_code=500, detail=str(e))

frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        
        raise HTTPException(status_code=404, detail="Frontend not built")
else:
    print("Warning: Frontend dist folder not found. Run 'npm run build' in frontend directory.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)