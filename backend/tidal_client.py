import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
import requests

# Remote URL for endpoint configuration
ENDPOINTS_URL = "https://raw.githubusercontent.com/EduardPrigoana/hifi-instances/refs/heads/main/instances.json"

# Cache settings
CACHE_TTL = 3600  # 1 hour in seconds

logger = logging.getLogger(__name__)


class TidalAPIClient:
    
    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent / ".cache"
        
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "endpoints_cache.json"
        
        # In-memory cache
        self._endpoints_cache = None
        self._cache_timestamp = None
        
        self.endpoints = self._load_endpoints()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.success_history = {}
        self.download_status_cache = {}
    
    def _fetch_endpoints_from_remote(self) -> Optional[List[Dict]]:
        """Fetch endpoints from remote URL."""
        try:
            logger.info(f"Fetching endpoints from {ENDPOINTS_URL}")
            response = requests.get(ENDPOINTS_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            endpoints = self._parse_endpoints_json(data)
            logger.info(f"Successfully fetched {len(endpoints)} endpoints from remote")
            return endpoints
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch endpoints from remote: {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse remote endpoints JSON: {e}")
            return None
    
    def _parse_endpoints_json(self, data: Dict) -> List[Dict]:
        """Extract URLs from the 'api' section of the JSON."""
        endpoints = []
        priority = 1
        
        # Extract from 'api' section only (ignore 'ui' section)
        api_section = data.get('api', {})
        
        for provider_name, provider_data in api_section.items():
            urls = provider_data.get('urls', [])
            
            for url in urls:
                # Remove trailing slash if present
                url = url.rstrip('/')
                
                # Extract a name from the URL (e.g., "kraken.squid.wtf" -> "kraken")
                try:
                    hostname = url.replace('https://', '').replace('http://', '')
                    name = hostname.split('.')[0]
                except Exception:
                    name = f"endpoint_{len(endpoints)}"
                
                endpoints.append({
                    "name": name,
                    "url": url,
                    "priority": priority,
                    "provider": provider_name
                })
            
            # Increment priority for next provider (lower priority = tried first)
            priority += 1
        
        return endpoints
    
    def _load_cached_endpoints(self) -> Optional[List[Dict]]:
        """Load endpoints from disk cache."""
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
                
            # Check if cache is still valid
            cache_time = cache_data.get('timestamp', 0)
            if time.time() - cache_time < CACHE_TTL:
                endpoints = cache_data.get('endpoints', [])
                logger.info(f"Loaded {len(endpoints)} endpoints from disk cache")
                return endpoints
            else:
                logger.info("Disk cache expired")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to load cached endpoints: {e}")
            return None
    
    def _save_cached_endpoints(self, endpoints: List[Dict]):
        """Save endpoints to disk cache."""
        try:
            cache_data = {
                'timestamp': time.time(),
                'endpoints': endpoints
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Saved {len(endpoints)} endpoints to disk cache")
        except Exception as e:
            logger.warning(f"Failed to save endpoints to cache: {e}")
    
    def _is_cache_valid(self) -> bool:
        """Check if in-memory cache is still valid."""
        if self._endpoints_cache is None or self._cache_timestamp is None:
            return False
        return time.time() - self._cache_timestamp < CACHE_TTL
    
    def _get_fallback_endpoints(self) -> List[Dict]:
        """Emergency fallback endpoints if all else fails."""
        logger.warning("Using fallback endpoints")
        return [
            {"name": "california.monochrome.tf", "url": "https://california.monochrome.tf", "priority": 0},
            {"name": "kinoplus", "url": "http://tidal.kinoplus.online", "priority": 0},
            {"name": "wolf", "url": "https://wolf.qqdl.site", "priority": 1},
            {"name": "maus", "url": "https://maus.qqdl.site", "priority": 1},
            {"name": "vogel", "url": "https://vogel.qqdl.site", "priority": 1},
            {"name": "katze", "url": "https://katze.qqdl.site", "priority": 1},
            {"name": "hund", "url": "https://hund.qqdl.site", "priority": 1},
        ]
    
    def _ensure_mandatory_endpoints(self, endpoints: List[Dict]):
        """Ensure mandatory endpoints like kinoplus are present."""
        kinoplus_exists = any(ep.get('url') == "http://tidal.kinoplus.online" for ep in endpoints)
        if not kinoplus_exists:
            endpoints.insert(0, {
                "name": "kinoplus", 
                "url": "http://tidal.kinoplus.online", 
                "priority": 0, 
                "provider": "manual_mandatory"
            })

    def _load_endpoints(self) -> List[Dict]:
        """Load endpoints with caching strategy."""
        # 1. Check in-memory cache
        if self._is_cache_valid():
            logger.info("Using in-memory cached endpoints")
            return self._endpoints_cache
        
        endpoints = None
        
        # 2. Try to fetch from remote
        endpoints = self._fetch_endpoints_from_remote()
        
        # 3. Try disk cache if remote failed
        if not endpoints:
             endpoints = self._load_cached_endpoints()
        
        # 4. Use fallback endpoints if everything else failed
        if not endpoints:
            endpoints = self._get_fallback_endpoints()
            
        # Ensure mandatory endpoints are present
        if endpoints:
            self._ensure_mandatory_endpoints(endpoints)
            
            # Save to disk cache if we fetched from remote (and it's not just fallback)
            # Actually we should save whatever valid list we have if it's new
            # But let's stick to saving only if we fetched fresh or if we modified it meaningfully?
            # For simplicity, if we have endpoints and we are here (cache invalid or missing), save it.
            self._save_cached_endpoints(endpoints)
            
        self._endpoints_cache = endpoints
        self._cache_timestamp = time.time()
        return endpoints
    
    def _sort_endpoints_by_priority(self, operation: Optional[str] = None) -> List[Dict]:
        endpoints = self.endpoints.copy()
        
        if operation and operation in self.success_history:
            last_success = self.success_history[operation]
            for ep in endpoints:
                if ep['name'] == last_success['name']:
                    ep = ep.copy()
                    ep['priority'] = 0
        
        return sorted(endpoints, key=lambda x: (x.get('priority', 999), x['name']))
    
    def _record_success(self, endpoint: Dict, operation: str):
        self.success_history[operation] = {
            'name': endpoint['name'],
            'url': endpoint['url'],
            'timestamp': time.time()
        }
    
    def _make_request(self, path: str, params: Optional[Dict] = None, operation: Optional[str] = None) -> Optional[Dict]:
        sorted_endpoints = self._sort_endpoints_by_priority(operation)
        
        logger.info(f"Starting request for {operation or path} with params: {params}")
        logger.debug(f"Trying {len(sorted_endpoints)} endpoints in order: {[ep['name'] for ep in sorted_endpoints]}")
        
        for idx, endpoint in enumerate(sorted_endpoints, 1):
            url = f"{endpoint['url']}{path}"
            
            try:
                logger.debug(f"[{idx}/{len(sorted_endpoints)}] Attempting {endpoint['name']}: {url}")
                response = self.session.get(url, params=params, timeout=10)
                
                if response.status_code == 429:
                    logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} returned 429 (rate limited), sleeping 2s")
                    time.sleep(2)
                    continue
                
                if response.status_code in [500, 404]:
                    logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} returned {response.status_code}, trying next endpoint")
                    continue
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # Unwrap {'version': ..., 'data': ...} structure if present
                        # Some endpoints wrap the actual Tidal response in a 'data' field
                        if isinstance(data, dict) and 'data' in data and 'version' in data:
                             data = data['data']
                        
                        # specific check for search/track lists being empty
                        # The API can return items in two formats:
                        # 1. Nested: {'tracks': {'items': [...]}, 'albums': {...}, ...}
                        # 2. Direct: {'items': [...], 'limit': ..., 'offset': ...}
                        if isinstance(data, dict):
                            is_empty = False
                            
                            # First check if we have a direct 'items' key (format 2)
                            if 'items' in data and 'limit' in data:
                                # Direct format - check if items is empty
                                if not data.get('items'):
                                    is_empty = True
                            else:
                                # Nested format - check based on operation type
                                if operation == "search_albums":
                                    albums_data = data.get('albums', {})
                                    if isinstance(albums_data, dict) and not albums_data.get('items'):
                                        is_empty = True
                                elif operation == "search_tracks":
                                    tracks_data = data.get('tracks', {})
                                    if isinstance(tracks_data, dict) and not tracks_data.get('items'):
                                        is_empty = True
                                elif operation == "search_artists":
                                    artists_data = data.get('artists', {})
                                    if isinstance(artists_data, dict) and not artists_data.get('items'):
                                        is_empty = True
                                elif operation == "search_playlists":
                                    playlists_data = data.get('playlists', {})
                                    if isinstance(playlists_data, dict) and not playlists_data.get('items'):
                                        is_empty = True
                            # For other operations, don't apply the empty check
                            
                            if is_empty:
                                logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} returned 200 OK but empty content for {operation}. Trying next...")
                                continue
                                
                        logger.info(f"✓ Successfully got response from {endpoint['name']} ({endpoint['url']})")
                        self._record_success(endpoint, operation or path)
                        return data
                    except ValueError:
                        logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} returned invalid JSON, trying next endpoint")
                        continue
                else:
                    logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} returned unexpected status {response.status_code}")
            
            except requests.exceptions.Timeout:
                logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} timed out after 10s")
                continue
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} connection failed: {e}")
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"[{idx}/{len(sorted_endpoints)}] {endpoint['name']} request failed: {e}")
                continue
    
        logger.error(f"✗ All {len(sorted_endpoints)} endpoints failed for {operation or path}")
        return None
    
    def search_tracks(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"s": query}, operation="search_tracks")
    
    def search_albums(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"al": query}, operation="search_albums")
    
    def search_artists(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"a": query}, operation="search_artists")

    def search_playlists(self, query: str) -> Optional[Dict]:
        """Search playlists by name."""
        return self._make_request("/search/", {"p": query}, operation="search_playlists")
    
    def get_track(self, track_id: int, quality: str = "LOSSLESS") -> Optional[Dict]:
        """Get track playback info (stream URL, manifest, etc.)"""
        return self._make_request("/track/", {"id": track_id, "quality": quality}, operation="get_track")
    
    def get_track_metadata(self, track_id: int) -> Optional[Dict]:
        """Get full track metadata (trackNumber, album, artist, cover, etc.)
        This searches for the track and returns full metadata including:
        - trackNumber, volumeNumber
        - album (with cover, title, artist)
        - artist info
        - duration, isrc, etc.
        """
        # Search for this specific track to get full metadata
        result = self.search_tracks(str(track_id))
        if result and result.get('items'):
            for item in result.get('items', []):
                if item.get('id') == track_id:
                    return item
            # If exact match not found, return first result
            return result['items'][0] if result['items'] else None
        return None
    
    def get_album(self, album_id: int) -> Optional[Dict]:
        return self._make_request("/album/", {"id": album_id}, operation="get_album")
    
    def get_album_tracks(self, album_id: int) -> Optional[Dict]:
        # The /album/ endpoint returns tracks in the 'items' field
        return self._make_request("/album/", {"id": album_id}, operation="get_album_tracks")
    
    def get_artist(self, artist_id: int) -> Optional[Dict]:
        return self._make_request("/artist/", {"f": artist_id}, operation="get_artist")

    def get_playlist(self, playlist_id: str) -> Optional[Dict]:
        """Get playlist metadata and items."""
        return self._make_request("/playlist/", {"id": playlist_id}, operation="get_playlist")

    def get_playlist_tracks(self, playlist_id: str) -> Optional[Dict]:
        """Alias for get_playlist to keep naming consistent with album tracks."""
        return self._make_request("/playlist/", {"id": playlist_id}, operation="get_playlist_tracks")
    
    def get_download_status(self, track_id: int) -> Optional[Dict]:
        if track_id in self.download_status_cache:
            cached = self.download_status_cache[track_id]
            if time.time() - cached['timestamp'] < 300:
                return cached['status']
        return None
    
    def set_download_status(self, track_id: int, status: Dict):
        self.download_status_cache[track_id] = {
            'status': status,
            'timestamp': time.time()
        }
    
    def clear_download_status(self, track_id: int):
        if track_id in self.download_status_cache:
            del self.download_status_cache[track_id]
    
    def cleanup_old_status_cache(self):
        current_time = time.time()
        expired_keys = [
            track_id for track_id, data in self.download_status_cache.items()
            if current_time - data['timestamp'] > 300
        ]
        for track_id in expired_keys:
            del self.download_status_cache[track_id]