from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from api.clients import tidal_client
from api.utils.logging import log_info, log_error
from api.utils.extraction import extract_items
from api.models import TrackSearchResult, TroiTrackResponse

router = APIRouter()

@router.get("/api/search/tracks")
async def search_tracks(q: str, username: str = Depends(require_auth)):
    try:
        log_info(f"Search tracks request for query: {q}")
        result = tidal_client.search_tracks(q)
        
        if not result:
            return {"items": []}
        
        tracks = extract_items(result, 'tracks')
        log_info(f"Found {len(tracks)} tracks")
        if tracks:
            t0 = tracks[0]
            log_info(f"[Search Debug] First track raw artist: {t0.get('artist')}")
            log_info(f"[Search Debug] First track raw album: {t0.get('album')}")
        
        return {
            "items": [
                TrackSearchResult(
                    id=track['id'],
                    title=track['title'],
                    artist=track.get('artist', {}).get('name', 'Unknown'),
                    album=track.get('album', {}).get('title'),
                    duration=track.get('duration'),
                    cover=track.get('album', {}).get('cover'),
                    quality=track.get('audioQuality'),
                    tidal_artist_id=track.get('artist', {}).get('id'),
                    tidal_album_id=track.get('album', {}).get('id')
                )
                for track in tracks
            ]
        }
    except Exception as e:
        log_error(f"Error searching tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/search/albums")
async def search_albums(q: str, username: str = Depends(require_auth)):
    try:
        log_info(f"Searching albums: {q}")
        result = tidal_client.search_albums(q)
        
        if not result:
            log_info("No ALBUM results from API")
            return {"items": []}
        
        albums = extract_items(result, 'albums')
        log_info(f"Found {len(albums)} albums")
        
        return {"items": albums}
    except Exception as e:
        log_error(f"Error searching albums: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/search/artists")
async def search_artists(q: str, username: str = Depends(require_auth)):
    try:
        log_info(f"Searching for artist: {q}")
        result = tidal_client.search_artists(q)
        
        if not result:
            log_info("No results from API")
            return {"items": []}
        
        log_info(f"API response type: {type(result)}")
        
        artists = extract_items(result, 'artists')
        
        log_info(f"Found {len(artists)} artists")
        if artists:
            log_info(f"First artist: {artists[0].get('name', 'Unknown')} (ID: {artists[0].get('id')})")
        
        return {"items": artists}
    except Exception as e:
        log_error(f"Error searching artists: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/album/{album_id}/tracks")
async def get_album_tracks(album_id: int, username: str = Depends(require_auth)):
    try:
        log_info(f"Getting tracks for album: {album_id}")
        result = tidal_client.get_album_tracks(album_id)
        
        if not result:
            return {"items": []}
        
        # Handle v2 wrapper
        if isinstance(result, dict) and 'data' in result and 'version' in result:
            result = result['data']
        
        # The /album/ endpoint returns items directly (not under 'tracks' key)
        # Each item is wrapped: {"item": {...track...}, "type": "track"}
        raw_items = result.get('items', []) if isinstance(result, dict) else result
        
        tracks = []
        for item in raw_items:
            # Unwrap if nested in 'item' key
            track = item.get('item', item) if isinstance(item, dict) else item
            if isinstance(track, dict) and 'id' in track:
                tracks.append(track)
        
        log_info(f"Found {len(tracks)} tracks in album")
        
        # Convert to same format as search results
        return {
            "items": [
                TrackSearchResult(
                    id=track['id'],
                    title=track.get('title', 'Unknown'),
                    artist=track.get('artist', {}).get('name', 'Unknown') if isinstance(track.get('artist'), dict) else (track.get('artists', [{}])[0].get('name', 'Unknown') if track.get('artists') else 'Unknown'),
                    album=track.get('album', {}).get('title') if isinstance(track.get('album'), dict) else None,
                    duration=track.get('duration'),
                    cover=track.get('album', {}).get('cover') if isinstance(track.get('album'), dict) else None,
                    quality=track.get('audioQuality'),
                    tidal_artist_id=track.get('artist', {}).get('id') if isinstance(track.get('artist'), dict) else None,
                    tidal_album_id=track.get('album', {}).get('id') if isinstance(track.get('album'), dict) else None
                )
                for track in tracks
            ]
        }
    except Exception as e:
        log_error(f"Error getting album tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/artist/{artist_id}")
async def get_artist(artist_id: int, username: str = Depends(require_auth)):
    try:
        log_info(f"Getting info for artist: {artist_id}")
        
        artist_info = tidal_client.get_artist(artist_id)
        
        if not artist_info:
            return {"info": None, "top_tracks": [], "albums": []}
        
        top_tracks = []
        albums = []
        
        # Helper to check if something looks like an album
        def is_album_like(obj):
            # Relaxed check: just ID and Title are enough.
            return isinstance(obj, dict) and 'id' in obj and 'title' in obj
        
        # Helper to check if something looks like a track
        def is_track_like(obj):
            return isinstance(obj, dict) and 'id' in obj and 'title' in obj and 'duration' in obj
        
        # Extract albums - deeply nested: albums.rows[].modules[].pagedList.items[]
        albums_data = artist_info.get('albums', {})
        if isinstance(albums_data, dict):
            # Navigate: rows -> modules -> pagedList -> items
            rows = albums_data.get('rows', [])
            for row in rows:
                if isinstance(row, dict):
                    modules = row.get('modules', [])
                    for module in modules:
                        if isinstance(module, dict):
                            paged_list = module.get('pagedList', {})
                            if isinstance(paged_list, dict):
                                items = paged_list.get('items', [])
                                for item in items:
                                    if isinstance(item, list):
                                        continue
                                    
                                    album = item.get('item', item) if isinstance(item, dict) else item
                                    
                                    if is_album_like(album):
                                        albums.append({
                                            'id': album['id'],
                                            'title': album['title'],
                                            'year': album.get('releaseDate', '').split('-')[0] if album.get('releaseDate') else (album.get('year') or ''),
                                            'cover': album.get('cover'),
                                            'numberOfTracks': album.get('numberOfTracks')
                                        })
            
            # Fallback: try direct items or rows if modules structure wasn't found
            if not albums:
                album_list = albums_data.get('items', [])
                for item in album_list:
                    album = item.get('item', item) if isinstance(item, dict) else item
                    if is_album_like(album):
                        albums.append({
                            'id': album['id'],
                            'title': album['title'],
                            'year': album.get('releaseDate', '').split('-')[0] if album.get('releaseDate') else '',
                            'cover': album.get('cover'),
                            'numberOfTracks': album.get('numberOfTracks')
                        })
        
        # Extract tracks - they might be a direct list or in 'tracks.items'
        tracks_data = artist_info.get('tracks', [])
        if isinstance(tracks_data, list):
            track_list = tracks_data
        elif isinstance(tracks_data, dict):
            track_list = tracks_data.get('items', tracks_data.get('rows', []))
        else:
            track_list = []
        
        for item in track_list[:10]:  # Limit to top 10
            track = item.get('item', item) if isinstance(item, dict) else item
            if is_track_like(track):
                album_data = track.get('album', {}) if isinstance(track.get('album'), dict) else {}
                top_tracks.append({
                    'id': track['id'],
                    'title': track['title'],
                    'trackNumber': track.get('trackNumber'),
                    'album': {
                        'id': album_data.get('id'),
                        'title': album_data.get('title'),
                        'cover': album_data.get('cover'),
                    } if album_data else None,
                    'artist': track.get('artist', {}),
                    'duration': track['duration'],
                    'audioQuality': track.get('audioQuality', 'LOSSLESS'),
                })
        
        if not albums:
            log_info("No albums found in artist page, trying direct albums endpoint")
            direct_albums = tidal_client.get_artist_albums(artist_id)
            if direct_albums:
                # Direct endpoint usually returns {'items': [...]}
                raw_items = direct_albums.get('items', []) if isinstance(direct_albums, dict) else direct_albums
                for item in raw_items:
                    album = item.get('item', item) if isinstance(item, dict) else item
                    if is_album_like(album):
                        albums.append({
                            'id': album['id'],
                            'title': album['title'],
                            'year': album.get('releaseDate', '').split('-')[0] if album.get('releaseDate') else '',
                            'cover': album.get('cover'),
                            'numberOfTracks': album.get('numberOfTracks')
                        })
                log_info(f"Found {len(albums)} albums via direct endpoint")

        # Sort albums by year (newest first)
        def get_album_timestamp(album):
            year = album.get('year', '')
            if not year: return 0
            try: return int(year)
            except: return 0
        
        albums.sort(key=get_album_timestamp, reverse=True)
        
        # Extract artist info for frontend - the raw data is deeply nested
        # Artist picture may be in 'picture' or 'images' depending on API response
        # Helper to find artist object recursively
        # The API returns a "page" response for get_artist, so the artist details are hidden inside
        # the albums/tracks lists associated with the artist.
        def find_artist_object_recursive(data, target_id):
            if isinstance(data, dict):
                # Check if this dict is an artist object with matching ID
                # Must have id and name to be useful
                if 'id' in data and str(data.get('id')) == str(target_id) and 'name' in data:
                    return data
                
                # Recurse
                for v in data.values():
                    res = find_artist_object_recursive(v, target_id)
                    if res: return res
            
            elif isinstance(data, list):
                for item in data:
                    res = find_artist_object_recursive(item, target_id)
                    if res: return res
            return None
            
        artist_details = None
        artist_picture = None
        artist_name = artist_info.get('name') # Try direct name first
        
        # Try to find specific artist object if direct info is missing
        if not artist_name or not artist_info.get('picture'):
             found_obj = find_artist_object_recursive(artist_info, artist_id)
             if found_obj:
                 artist_details = found_obj
                 if not artist_name:
                     artist_name = found_obj.get('name')
                 artist_picture = found_obj.get('picture')

        # Fallback for picture if not in the found object (e.g. if we only found a partial object)
        if not artist_picture and isinstance(artist_info, dict):
            # Try direct picture field
            artist_picture = artist_info.get('picture')
            
            # Try images array
            if not artist_picture and 'images' in artist_info:
                images = artist_info.get('images', [])
                if images and isinstance(images, list) and len(images) > 0:
                    artist_picture = images[0].get('id') or images[0].get('url')
        
        log_info(f"Returning artist details with {len(albums)} albums and {len(top_tracks)} top tracks.")
        
        return {
            "artist": {
                "id": artist_id,
                "name": artist_name or f"Artist {artist_id}",
                "picture": artist_picture,
                "popularity": artist_info.get('popularity') if isinstance(artist_info, dict) else None,
            },
            "tracks": top_tracks,
            "albums": albums
        }
        
    except Exception as e:
        log_error(f"Error getting artist info: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
