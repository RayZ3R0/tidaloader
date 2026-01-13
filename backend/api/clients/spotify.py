import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass
from itertools import chain
import asyncio
from concurrent.futures import ThreadPoolExecutor

from spotapi import Public

logger = logging.getLogger(__name__)

@dataclass
class SpotifyTrack:
    title: str
    artist: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    spotify_id: Optional[str] = None

@dataclass
class SpotifyPlaylist:
    id: str
    name: str
    owner: str
    image: Optional[str] = None
    track_count: int = 0

class SpotifyClient:
    """
    Client for accessing Spotify playlist data without user credentials.
    Uses SpotAPI library which accesses Spotify's partner API for full playlist access.
    """
    
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def close(self):
        self._executor.shutdown(wait=False)

    def _fetch_playlist_sync(self, playlist_id: str) -> List[SpotifyTrack]:
        """
        Synchronous method to fetch all tracks using SpotAPI.
        SpotAPI uses the partner API which has no 100 track limit.
        """
        tracks = []
        
        try:
            # Get all chunks from SpotAPI (handles pagination internally, up to 343 per chunk)
            chunks = list(Public.playlist_info(playlist_id))
            all_items = list(chain.from_iterable([chunk['items'] for chunk in chunks]))
            
            for item in all_items:
                track_data = item.get('itemV2', {}).get('data', {})
                typename = track_data.get('__typename')
                
                # Skip non-track items (LocalTrack, RestrictedContent, NotFound, Episode)
                if typename != 'Track':
                    continue
                
                # Extract track info
                name = track_data.get('name', 'Unknown Title')
                
                # Get artists
                artists_data = track_data.get('artists', {}).get('items', [])
                if artists_data:
                    artist_names = [a.get('profile', {}).get('name', '') for a in artists_data]
                    artist_str = ", ".join(filter(None, artist_names)) or "Unknown Artist"
                else:
                    artist_str = "Unknown Artist"
                
                # Get album
                album_data = track_data.get('albumOfTrack', {})
                album_name = album_data.get('name')
                
                # Get duration
                duration_data = track_data.get('trackDuration', {})
                duration_ms = duration_data.get('totalMilliseconds')
                if duration_ms:
                    duration_ms = int(duration_ms)
                
                # Get Spotify ID from URI (format: spotify:track:XXXXX)
                uri = track_data.get('uri', '')
                spotify_id = uri.split(':')[-1] if uri.startswith('spotify:track:') else None
                
                tracks.append(SpotifyTrack(
                    title=name,
                    artist=artist_str,
                    album=album_name,
                    duration_ms=duration_ms,
                    spotify_id=spotify_id
                ))
                
            logger.info(f"Fetched {len(tracks)} tracks from Spotify via SpotAPI")
            return tracks
            
        except Exception as e:
            logger.error(f"Error fetching playlist with SpotAPI: {e}")
            raise

    async def get_playlist_tracks(self, playlist_id: str) -> Tuple[List[SpotifyTrack], bool]:
        """
        Fetch all tracks from a playlist using SpotAPI.
        Returns: (tracks, is_limited)
        is_limited is always False with SpotAPI as it has no practical limit.
        """
        loop = asyncio.get_event_loop()
        
        try:
            tracks = await loop.run_in_executor(
                self._executor,
                self._fetch_playlist_sync,
                playlist_id
            )
            return tracks, False
        except Exception as e:
            logger.error(f"Failed to fetch playlist: {e}")
            return [], False

    def _fetch_playlist_count(self, playlist_id: str) -> int:
        """
        Fetch just the track count for a playlist using playlist_info.
        """
        try:
            # Import here to avoid circular imports or context issues
            from spotapi import Public
            iterator = Public.playlist_info(playlist_id)
            first_chunk = next(iterator)
            return first_chunk.get('totalCount', 0)
        except Exception:
            return 0

    def _search_playlists_sync(self, query: str, limit: int = 10) -> List[SpotifyPlaylist]:
        """
        Synchronous method to search for playlists.
        Uses spotapi.song.Song.query_songs manually to extract playlist results.
        Then fetches track counts in parallel.
        """
        try:
            # Import internals here to avoid top-level issues if layout changes
            from spotapi.public import client_pool
            from spotapi.song import Song
            
            client = client_pool.get()
            playlists = []
            
            try:
                song_api = Song(client=client)
                # query_songs returns the raw response dict
                response = song_api.query_songs(query, limit=limit)
                
                if "data" in response and "searchV2" in response["data"]:
                    data = response["data"]["searchV2"]
                    if "playlists" in data and "items" in data["playlists"]:
                        items = data["playlists"]["items"]
                        for item in items:
                            p_data = item.get("data", {})
                            uri = p_data.get("uri", "")
                            
                            # Extract ID from spotify:playlist:ID
                            p_id = uri.split(":")[-1] if uri else ""
                            
                            # Extract image
                            images = p_data.get("images", {}).get("items", [])
                            image_url = None
                            if images:
                                # Prioritize 300x300 or similar, mostly sources[0] is best
                                sources = images[0].get("sources", [])
                                if sources:
                                    image_url = sources[0].get("url")
                                    
                            # Owner
                            owner_data = p_data.get("ownerV2", {}).get("data", {})
                            owner_name = owner_data.get("name", "Unknown")
                            
                            playlists.append(SpotifyPlaylist(
                                id=p_id,
                                name=p_data.get("name", "Unknown"),
                                owner=owner_name,
                                image=image_url,
                                track_count=0 # Placeholder, will fetch below
                            ))
                            
            finally:
                client_pool.put(client)

            # Fetch track counts in parallel
            if playlists:
                with ThreadPoolExecutor(max_workers=min(len(playlists), 10)) as executor:
                    # Create a map of future -> playlist
                    future_to_playlist = {
                        executor.submit(self._fetch_playlist_count, p.id): p 
                        for p in playlists
                    }
                    
                    for future in future_to_playlist:
                        p = future_to_playlist[future]
                        try:
                            count = future.result()
                            p.track_count = count
                        except Exception as e:
                            logger.warn(f"Failed to fetch count for playlist {p.id}: {e}")
                            
            return playlists
                
        except Exception as e:
            logger.error(f"Error searching spotify playlists: {e}")
            return []

    async def search_playlists(self, query: str) -> List[SpotifyPlaylist]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._search_playlists_sync,
            query
        )

    def _get_playlist_metadata_sync(self, playlist_id: str) -> Optional[SpotifyPlaylist]:
        """
        Fetch metadata for a specific playlist by mocking a search for its ID.
        This allows retrieving the cover image.
        """
        try:
            # Import internals
            from spotapi.public import client_pool
            from spotapi.song import Song
            
            client = client_pool.get()
            try:
                song_api = Song(client=client)
                query = f"spotify:playlist:{playlist_id}"
                response = song_api.query_songs(query, limit=1)
                
                if "data" in response and "searchV2" in response["data"]:
                    data = response["data"]["searchV2"]
                    if "playlists" in data and "items" in data["playlists"]:
                        items = data["playlists"]["items"]
                        if items:
                            p_data = items[0].get("data", {})
                            uri = p_data.get("uri", "")
                            p_id = uri.split(":")[-1] if uri else ""
                            
                            # Verify ID matches (search usually exact for URI)
                            if p_id != playlist_id:
                                logger.warning(f"Search for {playlist_id} returned different ID {p_id}")
                                
                            # Image
                            images = p_data.get("images", {}).get("items", [])
                            image_url = None
                            if images:
                                sources = images[0].get("sources", [])
                                if sources:
                                    image_url = sources[0].get("url")
                                    
                            owner_data = p_data.get("ownerV2", {}).get("data", {})
                            
                            return SpotifyPlaylist(
                                id=p_id,
                                name=p_data.get("name", "Unknown"),
                                owner=owner_data.get("name", "Unknown"),
                                image=image_url
                            )
            finally:
                client_pool.put(client)
            return None
        except Exception as e:
            logger.error(f"Error fetching spotify metadata: {e}")
            return None

    async def get_playlist_metadata(self, playlist_id: str) -> Optional[SpotifyPlaylist]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._get_playlist_metadata_sync,
            playlist_id
        )
