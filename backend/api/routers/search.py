from fastapi import APIRouter, Depends, HTTPException
from api.auth import require_auth
from api.clients import tidal_client
from api.utils.logging import log_info, log_error
from api.utils.extraction import extract_items
from api.models import TrackSearchResult, TroiTrackResponse, PlaylistSearchResult

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
                    trackNumber=track.get('trackNumber'),
                    albumArtist=track.get('album', {}).get('artist', {}).get('name') if track.get('album', {}).get('artist') else track.get('artist', {}).get('name', 'Unknown'),
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

@router.get("/api/search/playlists")
async def search_playlists(q: str, username: str = Depends(require_auth)):
    try:
        log_info(f"Searching playlists: {q}")
        result = tidal_client.search_playlists(q)
        
        if not result:
            log_info("No PLAYLIST results from API")
            return {"items": []}
        
        playlists = extract_items(result, 'playlists')
        included = result.get('included', []) if isinstance(result, dict) else []
        log_info(f"Found {len(playlists)} playlists")
        
        def get_cover_id(pl):
            # Prefer squareImage (thumb) > image > cover/picture/imageId
            priority_keys = ['squareImage', 'image', 'cover', 'picture', 'imageId']

            # Attributes (JSON:API style)
            attrs = pl.get('attributes', {}) if isinstance(pl, dict) else {}
            for key in priority_keys:
                val = attrs.get(key)
                if val:
                    return str(val).strip()

            # Legacy/root keys
            for key in priority_keys:
                if key in pl and pl.get(key):
                    return str(pl.get(key)).strip()

            # Fallback: resolve via relationships.coverArt and the top-level "included" array
            try:
                rel = pl.get('relationships', {}) if isinstance(pl, dict) else {}
                cover_rel = rel.get('coverArt') or rel.get('coverart') or rel.get('thumbnailArt')
                cover_data = cover_rel.get('data') if isinstance(cover_rel, dict) else None
                cover_id = None
                if isinstance(cover_data, dict):
                    cover_id = cover_data.get('id')
                elif isinstance(cover_data, list) and cover_data:
                    cover_id = cover_data[0].get('id')

                if cover_id:
                    for inc in included:
                        if str(inc.get('id')) == str(cover_id):
                            attrs_inc = inc.get('attributes', {}) if isinstance(inc, dict) else {}
                            files = attrs_inc.get('files') or []
                            for file in files:
                                href = file.get('href')
                                if href:
                                    return href
                            return cover_id
                    return cover_id
            except Exception:
                pass
            return None
        
        return {
            "items": [
                PlaylistSearchResult(
                    id=str(pl.get('uuid') or pl.get('id')),
                    title=pl.get('title') or pl.get('name') or "Untitled Playlist",
                    creator=(pl.get('creator', {}) or {}).get('name') if isinstance(pl.get('creator'), dict) else pl.get('creator'),
                    description=pl.get('description'),
                    numberOfTracks=pl.get('numberOfTracks') or pl.get('numberOfItems'),
                    cover=get_cover_id(pl)
                )
                for pl in playlists
                if pl.get('uuid') or pl.get('id')
            ]
        }
    except Exception as e:
        log_error(f"Error searching playlists: {e}")
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
                track_number = track.get('trackNumber') or track.get('track_number')
                if not track_number and isinstance(item, dict):
                    track_number = item.get('index')
                if not track_number:
                    track_number = len(tracks) + 1

                track_copy = track.copy()
                track_copy['track_number'] = track_number
                tracks.append(track_copy)
        
        log_info(f"Found {len(tracks)} tracks in album")
        
        # Convert to same format as search results
        return {
            "items": [
                TrackSearchResult(
                    id=track['id'],
                    title=track.get('title', 'Unknown'),
                    artist=track.get('artist', {}).get('name', 'Unknown') if isinstance(track.get('artist'), dict) else (track.get('artists', [{}])[0].get('name', 'Unknown') if track.get('artists') else 'Unknown'),
                    album=track.get('album', {}).get('title') if isinstance(track.get('album'), dict) else None,
                    track_number=track.get('track_number'),
                    duration=track.get('duration'),
                    cover=track.get('album', {}).get('cover') if isinstance(track.get('album'), dict) else None,
                    quality=track.get('audioQuality'),
                    trackNumber=track.get('trackNumber'),
                    albumArtist=track.get('album', {}).get('artist', {}).get('name') if track.get('album', {}).get('artist') else (track.get('artist', {}).get('name', 'Unknown') if isinstance(track.get('artist'), dict) else 'Unknown'),
                    tidal_artist_id=track.get('artist', {}).get('id') if isinstance(track.get('artist'), dict) else (track.get('artists', [{}])[0].get('id') if track.get('artists') else None),
                    tidal_album_id=track.get('album', {}).get('id') if isinstance(track.get('album'), dict) else album_id
                )
                for track in tracks
            ]
        }
    except Exception as e:
        log_error(f"Error getting album tracks: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/playlist/{playlist_id}")
async def get_playlist_tracks(playlist_id: str, username: str = Depends(require_auth)):
    try:
        log_info(f"Getting tracks for playlist: {playlist_id}")
        result = tidal_client.get_playlist_tracks(playlist_id)
        
        if not result:
            return {"items": [], "playlist": None}
        
        # Unwrap v2 wrapper if present
        if isinstance(result, dict) and 'data' in result and 'version' in result:
            result = result['data']
        
        playlist_info = None
        included = result.get('included', []) if isinstance(result, dict) else []
        raw_items = []
        
        if isinstance(result, dict):
            playlist_info = result.get('playlist') or result.get('info')

            # JSON:API style response (data + included)
            if not playlist_info and isinstance(result.get('data'), list) and result.get('data'):
                playlist_info = result['data'][0]

            # Build a normalized playlist_info dict with priority on squareImage
            if playlist_info:
                attrs = playlist_info.get('attributes', {}) if isinstance(playlist_info, dict) else {}
                rels = playlist_info.get('relationships', {}) if isinstance(playlist_info, dict) else {}
                priority_keys = ['squareImage', 'image', 'cover', 'picture', 'imageId']
                cover_val = None
                for key in priority_keys:
                    if key in attrs and attrs.get(key):
                        cover_val = attrs.get(key)
                        break
                if not cover_val:
                    for key in priority_keys:
                        if key in playlist_info and playlist_info.get(key):
                            cover_val = playlist_info.get(key)
                            break

                playlist_info = {
                    "id": playlist_info.get('uuid') or playlist_info.get('id') or playlist_id,
                    "title": attrs.get('name') or playlist_info.get('title') or playlist_info.get('name'),
                    "description": attrs.get('description') or playlist_info.get('description'),
                    "numberOfTracks": attrs.get('numberOfItems') or playlist_info.get('numberOfTracks') or playlist_info.get('numberOfItems'),
                    "cover": str(cover_val).strip() if cover_val else None,
                    "relationships": rels
                }
            else:
                priority_keys = ['squareImage', 'image', 'cover', 'picture', 'imageId']
                cover_val = None
                for key in priority_keys:
                    if key in result and result.get(key):
                        cover_val = result.get(key)
                        break

                playlist_info = {
                    "id": result.get('uuid') or playlist_id,
                    "title": result.get('title') or result.get('name'),
                    "description": result.get('description'),
                    "numberOfTracks": result.get('numberOfTracks') or result.get('numberOfItems'),
                    "cover": str(cover_val).strip() if cover_val else None,
                    "relationships": result.get('relationships', {})
                }
            
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
        
        # If cover still missing, try relationships.coverArt via included list
        if playlist_info and not playlist_info.get('cover'):
            try:
                rel = result.get('relationships', {}) if isinstance(result, dict) else {}
                cover_rel = rel.get('coverArt') or rel.get('coverart') or rel.get('thumbnailArt')
                cover_data = cover_rel.get('data') if isinstance(cover_rel, dict) else None
                if isinstance(cover_data, list) and cover_data:
                    cover_id = cover_data[0].get('id')
                    for inc in included:
                        if str(inc.get('id')) == str(cover_id):
                            attrs = inc.get('attributes', {}) if isinstance(inc, dict) else {}
                            files = attrs.get('files') or []
                            for file in files:
                                href = file.get('href')
                                if href:
                                    playlist_info['cover'] = href
                                    break
                            if not playlist_info.get('cover'):
                                playlist_info['cover'] = cover_id
                            break
            except Exception:
                pass
        
        tracks = []
        for idx, item in enumerate(raw_items):
            track = item.get('item', item) if isinstance(item, dict) else item
            if not isinstance(track, dict) or 'id' not in track:
                continue
            
            album_data = track.get('album', {}) if isinstance(track.get('album'), dict) else {}
            artist_data = track.get('artist', {}) if isinstance(track.get('artist'), dict) else (track.get('artists', [{}])[0] if track.get('artists') else {})
            
            track_number = track.get('trackNumber') or track.get('track_number') or (item.get('index') if isinstance(item, dict) else None)
            if not track_number:
                track_number = idx + 1
            
            tracks.append(TrackSearchResult(
                id=track['id'],
                title=track.get('title', 'Unknown'),
                artist=artist_data.get('name', 'Unknown'),
                album=album_data.get('title') if album_data else None,
                track_number=track_number,
                duration=track.get('duration'),
                cover=album_data.get('cover') if album_data else (track.get('cover') if isinstance(track.get('cover'), str) else None),
                quality=track.get('audioQuality')
            ))
        
        log_info(f"Found {len(tracks)} tracks in playlist")
        
        return {
            "playlist": playlist_info,
            "items": tracks
        }
    except Exception as e:
        log_error(f"Error getting playlist tracks: {e}")
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
