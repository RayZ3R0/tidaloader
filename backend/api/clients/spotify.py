import httpx
import re
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SpotifyTrack:
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    spotify_id: Optional[str] = None

class SpotifyClient:
    """
    Client for accessing Spotify playlist data without user credentials.
    Uses the 'Embed' page to extract a guest access token, then uses the official API.
    """
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            timeout=30.0,
            follow_redirects=True
        )
        self.access_token = None

    async def close(self):
        await self.client.aclose()

    async def _get_guest_token(self, playlist_id: str) -> Optional[str]:
        """Fetch the embed page and extract the guest access token from __NEXT_DATA__"""
        embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
        logger.info(f"Fetching guest token from {embed_url}")
        
        try:
            response = await self.client.get(embed_url)
            response.raise_for_status()
            html = response.text
            
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">\s*(.*?)\s*</script>', html, re.DOTALL)
            if not match:
                logger.error("Could not find __NEXT_DATA__ in Spotify embed page")
                return None
            
            data = json.loads(match.group(1))
            
            # Navigate path to token: props.pageProps.state.settings.session.accessToken
            try:
                token = data['props']['pageProps']['state']['settings']['session']['accessToken']
                logger.info("Successfully extracted Spotify guest access token")
                return token
            except KeyError as e:
                logger.error(f"Failed to extract token from JSON structure: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching guest token: {e}")
            return None

    async def get_playlist_tracks(self, playlist_id: str) -> List[SpotifyTrack]:
        """Fetch all tracks from a playlist using guest token and API"""
        
        # 1. Get Token
        token = await self._get_guest_token(playlist_id)
        if not token:
            logger.warning("Could not get guest token, falling back to scraped embed data (limit 100 tracks)")
            return await self._scrape_embed_tracks_fallback(playlist_id)
            
        return await self._fetch_tracks_from_api(playlist_id, token)

    async def _fetch_tracks_from_api(self, playlist_id: str, token: str) -> List[SpotifyTrack]:
        """Use official API with guest token to get all tracks"""
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = {"Authorization": f"Bearer {token}"}
        
        all_tracks = []
        offset = 0
        limit = 100
        
        try:
            while True:
                logger.info(f"Fetching Spotify tracks offset={offset}...")
                params = {
                    "offset": offset,
                    "limit": limit,
                    "additional_types": "track"
                }
                
                response = await self.client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                
                items = data.get("items", [])
                if not items:
                    break
                    
                for item in items:
                    track_obj = item.get("track")
                    # Handle local files or null tracks
                    if not track_obj or track_obj.get("is_local"):
                        continue
                        
                    artists = [a["name"] for a in track_obj.get("artists", [])]
                    artist_str = ", ".join(artists) if artists else "Unknown Artist"
                    
                    all_tracks.append(SpotifyTrack(
                        title=track_obj.get("name", "Unknown Title"),
                        artist=artist_str,
                        album=track_obj.get("album", {}).get("name"),
                        duration_ms=track_obj.get("duration_ms"),
                        spotify_id=track_obj.get("id")
                    ))
                
                if not data.get("next"):
                    break
                    
                offset += limit
                
            logger.info(f"Fetched {len(all_tracks)} tracks from Spotify API")
            return all_tracks
            
        except Exception as e:
            logger.error(f"Error fetching tracks from API: {e}")
            logger.warning("Falling back to embed scraping")
            return await self._scrape_embed_tracks_fallback(playlist_id)

    async def _scrape_embed_tracks_fallback(self, playlist_id: str) -> List[SpotifyTrack]:
        """Fallback: Parse tracks directly from the embed JSON (limit 100)"""
        embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
        try:
            response = await self.client.get(embed_url)
            response.raise_for_status()
            html = response.text
            
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">\s*(.*?)\s*</script>', html, re.DOTALL)
            if not match:
                return []
            
            data = json.loads(match.group(1))
            
            # Try to find track list
            # Path: props.pageProps.state.data.entity.trackList
            items = []
            try:
                items = data['props']['pageProps']['state']['data']['entity']['trackList']
            except KeyError:
                logger.error("Could not find trackList in fallback data")
                return []
                
            tracks = []
            for item in items:
                # Structure: {'title': '...', 'subtitle': '...', ...}
                # Title = Title, Subtitle = Artist
                title = item.get('title')
                artist = item.get('subtitle')
                
                if title and artist:
                    tracks.append(SpotifyTrack(
                        title=title,
                        artist=artist,
                        album=None, # Album missing in this view
                        duration_ms=item.get('duration'),
                        spotify_id=item.get('uid') # UID is not spotify ID strictly but usable
                    ))
            
            logger.info(f"Scraped {len(tracks)} tracks from embed data (fallback)")
            return tracks
            
        except Exception as e:
            logger.error(f"Error in fallback scraping: {e}")
            return []
