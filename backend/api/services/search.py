from api.utils.text import fix_unicode, romanize_japanese
from api.utils.logging import log_info, log_success, log_error
from api.utils.extraction import extract_items
from api.clients import tidal_client

async def search_track_with_fallback(artist: str, title: str, track_obj) -> bool:
    artist_fixed = fix_unicode(artist)
    title_fixed = fix_unicode(title)
    
    log_info(f"Searching: {artist_fixed} - {title_fixed}")
    
    query = f"{artist_fixed} {title_fixed}"
    result = tidal_client.search_tracks(query)
    
    if result:
        tidal_tracks = extract_items(result, 'tracks')
        if tidal_tracks and len(tidal_tracks) > 0:
            first_track = tidal_tracks[0]
            track_obj.tidal_id = first_track.get('id')
            track_obj.tidal_artist_id = first_track.get('artist', {}).get('id')
            album_data = first_track.get('album', {})
            track_obj.tidal_album_id = album_data.get('id') if isinstance(album_data, dict) else None
            track_obj.tidal_exists = True
            
            track_obj.album = album_data.get('title') if isinstance(album_data, dict) else None
            
            log_success(f"Found on Tidal - ID: {track_obj.tidal_id}")
            return True
    
    romanized_title = romanize_japanese(title_fixed)
    romanized_artist = romanize_japanese(artist_fixed)
    
    if romanized_title or romanized_artist:
        search_artist = romanized_artist if romanized_artist else artist_fixed
        search_title = romanized_title if romanized_title else title_fixed
        
        log_info(f"Trying romanized: {search_artist} - {search_title}")
        
        query_romanized = f"{search_artist} {search_title}"
        result = tidal_client.search_tracks(query_romanized)
        
        if result:
            tidal_tracks = extract_items(result, 'tracks')
            if tidal_tracks and len(tidal_tracks) > 0:
                first_track = tidal_tracks[0]
                track_obj.tidal_id = first_track.get('id')
                track_obj.tidal_artist_id = first_track.get('artist', {}).get('id')
                album_data = first_track.get('album', {})
                track_obj.tidal_album_id = album_data.get('id') if isinstance(album_data, dict) else None
                track_obj.tidal_exists = True
                
                track_obj.album = album_data.get('title') if isinstance(album_data, dict) else None
                
                log_success(f"Found via romanization - ID: {track_obj.tidal_id}")
                return True
    
    log_error("Not found on Tidal")
    return False
