import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


INSTANCES_FILE = Path(__file__).parent / "instances.json"
UPTIME_TRACKER_URL = "https://tidal-uptime.geeked.wtf"
CACHE_TTL = 3600

logger = logging.getLogger(__name__)


class TidalAPIClient:

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent / ".cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "endpoints_cache.json"

        self._endpoints_cache = None
        self._cache_timestamp = None
        self._qobuz_endpoints_cache = None
        self._qobuz_cache_timestamp = None

        self.endpoints = self._load_endpoints()
        self.qobuz_endpoints = self._load_qobuz_endpoints()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Origin': 'https://listen.tidal.com',
            'Referer': 'https://listen.tidal.com/',
        })
        self.success_history = {}
        self.download_status_cache = {}

    def _check_endpoint_connection(self, url: str, timeout: int = 5) -> Tuple[str, bool]:
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code < 500:
                return (url, True)
            response = requests.get(url, timeout=timeout)
            if response.status_code < 500:
                return (url, True)
            return (url, False)
        except requests.exceptions.Timeout:
            return (url, False)
        except requests.exceptions.ConnectionError:
            return (url, False)
        except requests.exceptions.RequestException:
            return (url, False)

    def _validate_endpoints_parallel(self, urls: List[str], max_workers: int = 10) -> set:
        reachable = set()
        if not urls:
            return reachable

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._check_endpoint_connection, url): url for url in urls}
            for future in as_completed(futures):
                try:
                    url, is_reachable = future.result()
                    if is_reachable:
                        reachable.add(url)
                except Exception:
                    pass

        return reachable

    def _fetch_endpoints_from_uptime_tracker(self) -> Optional[List[Dict]]:
        try:
            response = requests.get(UPTIME_TRACKER_URL, timeout=8)
            response.raise_for_status()
            data = response.json()

            api_entries = data.get('api', [])
            if not api_entries:
                return None

            endpoints = []
            for entry in api_entries:
                url = entry.get('url', '').rstrip('/')
                if not url:
                    continue
                try:
                    name = url.replace('https://', '').replace('http://', '').split('.')[0]
                except Exception:
                    name = f"endpoint_{len(endpoints)}"
                endpoints.append({
                    "name": name,
                    "url": url,
                    "priority": 1,
                    "provider": "uptime-tracker",
                    "version": entry.get('version'),
                })

            logger.info(f"Uptime tracker: {len(endpoints)} endpoint(s)")
            return endpoints

        except Exception as e:
            logger.warning(f"Failed to fetch from uptime tracker: {e}")
            return None

    def _fetch_endpoints_from_file(self) -> Optional[List[Dict]]:
        try:
            with open(INSTANCES_FILE, 'r') as f:
                data = json.load(f)
            endpoints = self._parse_endpoints_json(data)
            logger.info(f"Loaded {len(endpoints)} endpoints from instances.json")
            return endpoints
        except Exception as e:
            logger.warning(f"Failed to load endpoints from file: {e}")
            return None

    def _parse_endpoints_json(self, data: Dict) -> List[Dict]:
        endpoints = []
        priority = 1
        for provider_name, provider_data in data.get('api', {}).items():
            for url in provider_data.get('urls', []):
                url = url.rstrip('/')
                try:
                    name = url.replace('https://', '').replace('http://', '').split('.')[0]
                except Exception:
                    name = f"endpoint_{len(endpoints)}"
                endpoints.append({
                    "name": name,
                    "url": url,
                    "priority": priority,
                    "provider": provider_name,
                })
            priority += 1
        return endpoints

    def _parse_qobuz_endpoints_json(self, data: Dict) -> List[Dict]:
        endpoints = []
        priority = 1
        for provider_name, provider_data in data.get('qobuz', {}).items():
            for url in provider_data.get('urls', []):
                url = url.rstrip('/')
                try:
                    name = url.replace('https://', '').replace('http://', '').split('.')[0]
                except Exception:
                    name = f"qobuz_{len(endpoints)}"
                endpoints.append({
                    "name": name,
                    "url": url,
                    "priority": priority,
                    "provider": provider_name,
                })
            priority += 1
        return endpoints

    def _load_cached_endpoints(self) -> Optional[List[Dict]]:
        if not self.cache_file.exists():
            return None
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            if time.time() - cache_data.get('timestamp', 0) < CACHE_TTL:
                endpoints = cache_data.get('endpoints', [])
                logger.info(f"Loaded {len(endpoints)} endpoints from disk cache")
                return endpoints
            return None
        except Exception as e:
            logger.warning(f"Failed to load cached endpoints: {e}")
            return None

    def _save_cached_endpoints(self, endpoints: List[Dict]):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({'timestamp': time.time(), 'endpoints': endpoints}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save endpoints to cache: {e}")

    def _is_cache_valid(self) -> bool:
        return (
            self._endpoints_cache is not None
            and self._cache_timestamp is not None
            and time.time() - self._cache_timestamp < CACHE_TTL
        )

    def _is_qobuz_cache_valid(self) -> bool:
        return (
            self._qobuz_endpoints_cache is not None
            and self._qobuz_cache_timestamp is not None
            and time.time() - self._qobuz_cache_timestamp < CACHE_TTL
        )

    def _load_endpoints(self) -> List[Dict]:
        if self._is_cache_valid():
            return self._endpoints_cache

        # Tracker endpoints get priority=1, file endpoints get priority=2.
        # Merge both so we always have full coverage.
        tracker_endpoints = self._fetch_endpoints_from_uptime_tracker() or []
        file_endpoints = self._fetch_endpoints_from_file() or []

        seen_urls = {ep['url'] for ep in tracker_endpoints}
        for ep in file_endpoints:
            if ep['url'] not in seen_urls:
                ep = {**ep, 'priority': 2}
                tracker_endpoints.append(ep)
                seen_urls.add(ep['url'])

        endpoints = tracker_endpoints

        if not endpoints:
            logger.warning("Both uptime tracker and instances.json unavailable, falling back to disk cache")
            endpoints = self._load_cached_endpoints() or []

        if endpoints:
            self._save_cached_endpoints(endpoints)

        p1 = sum(1 for e in endpoints if e.get('priority', 2) == 1)
        p2 = sum(1 for e in endpoints if e.get('priority', 2) == 2)
        logger.info(f"Endpoint pool: {len(endpoints)} total ({p1} from tracker, {p2} from file)")

        self._endpoints_cache = endpoints
        self._cache_timestamp = time.time()
        return self._endpoints_cache

    def _load_qobuz_endpoints(self) -> List[Dict]:
        if self._is_qobuz_cache_valid():
            return self._qobuz_endpoints_cache

        tracker_endpoints = []
        try:
            response = requests.get(UPTIME_TRACKER_URL, timeout=8)
            response.raise_for_status()
            data = response.json()
            for entry in data.get('qobuz', []):
                url = entry.get('url', '').rstrip('/')
                if not url:
                    continue
                try:
                    name = url.replace('https://', '').replace('http://', '').split('.')[0]
                except Exception:
                    name = f"qobuz_{len(tracker_endpoints)}"
                tracker_endpoints.append({
                    "name": name,
                    "url": url,
                    "priority": 1,
                    "provider": "uptime-tracker",
                    "version": entry.get('version'),
                })
        except Exception as e:
            logger.warning(f"Failed to fetch Qobuz endpoints from uptime tracker: {e}")

        file_endpoints = []
        try:
            with open(INSTANCES_FILE, 'r') as f:
                data = json.load(f)
            file_endpoints = self._parse_qobuz_endpoints_json(data)
        except Exception as e:
            logger.warning(f"Failed to load Qobuz endpoints from file: {e}")

        seen_urls = {ep['url'] for ep in tracker_endpoints}
        for ep in file_endpoints:
            if ep['url'] not in seen_urls:
                ep = {**ep, 'priority': 2}
                tracker_endpoints.append(ep)
                seen_urls.add(ep['url'])

        endpoints = tracker_endpoints
        logger.info(f"Qobuz endpoint pool: {len(endpoints)} endpoint(s)")

        self._qobuz_endpoints_cache = endpoints
        self._qobuz_cache_timestamp = time.time()
        return self._qobuz_endpoints_cache

    def _sort_endpoints_by_priority(self, operation: Optional[str] = None) -> List[Dict]:
        endpoints = [ep.copy() for ep in self.endpoints]

        sticky_name = None
        if operation and operation in self.success_history:
            sticky_name = self.success_history[operation]['name']
        elif self.success_history:
            most_recent = max(self.success_history.values(), key=lambda x: x['timestamp'])
            sticky_name = most_recent['name']

        if sticky_name:
            for ep in endpoints:
                if ep['name'] == sticky_name:
                    ep['priority'] = 0
                    break

        return sorted(endpoints, key=lambda x: (x.get('priority', 999), x['name']))

    def _record_success(self, endpoint: Dict, operation: str):
        self.success_history[operation] = {
            'name': endpoint['name'],
            'url': endpoint['url'],
            'timestamp': time.time(),
        }

    def _make_request(self, path: str, params: Optional[Dict] = None, operation: Optional[str] = None) -> Optional[Dict]:
        sorted_endpoints = self._sort_endpoints_by_priority(operation)
        p1 = [ep for ep in sorted_endpoints if ep.get('priority', 999) <= 1]
        p2 = [ep for ep in sorted_endpoints if ep.get('priority', 999) > 1]

        logger.info(f"Starting request for {operation or path} with params: {params}")

        result = self._try_endpoints(p1, path, params, operation, phase="p1")
        if result is not None:
            return result

        # Try Qobuz before falling back to static instances
        if operation == "get_track" and params and 'id' in params:
            logger.info(f"All live endpoints failed for track {params['id']}, trying Qobuz...")
            qobuz_result = self._try_qobuz_for_track(params['id'], params.get('quality', 'LOSSLESS'))
            if qobuz_result:
                return qobuz_result
            logger.info("Qobuz unavailable, falling back to static instances...")

        result = self._try_endpoints(p2, path, params, operation, phase="p2")
        if result is not None:
            return result

        logger.error(f"All endpoints failed for {operation or path}")
        return None

    def _try_endpoints(self, endpoints: List[Dict], path: str, params: Optional[Dict], operation: Optional[str], phase: str) -> Optional[Dict]:
        for idx, endpoint in enumerate(endpoints, 1):
            url = f"{endpoint['url']}{path}"
            label = f"[{phase}:{idx}/{len(endpoints)}] {endpoint['name']}"

            try:
                response = self.session.get(url, params=params, timeout=10)

                if response.status_code == 429:
                    logger.warning(f"{label} rate limited, sleeping 2s")
                    time.sleep(2)
                    continue

                if response.status_code in (403, 404, 500):
                    logger.warning(f"{label} returned {response.status_code}")
                    continue

                if response.status_code == 200:
                    try:
                        data = response.json()

                        if isinstance(data, dict) and 'data' in data and 'version' in data:
                            data = data['data']

                        if isinstance(data, dict) and self._is_empty_response(data, operation):
                            logger.warning(f"{label} returned empty response for {operation}")
                            continue

                        logger.info(f"✓ {endpoint['name']} ({endpoint['url']})")
                        self._record_success(endpoint, operation or path)
                        return data
                    except ValueError:
                        logger.warning(f"{label} returned invalid JSON")
                        continue
                else:
                    logger.warning(f"{label} returned {response.status_code}")
                    continue

            except requests.exceptions.Timeout:
                logger.warning(f"{label} timed out")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"{label} connection failed: {e}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"{label} request failed: {e}")

        return None

    def _is_empty_response(self, data: dict, operation: Optional[str]) -> bool:
        # /info/ returns a direct track object — never treat it as empty
        if operation == "get_track_metadata":
            return False

        if 'items' in data and 'limit' in data:
            return not data.get('items')

        section_map = {
            "search_albums": "albums",
            "search_tracks": "tracks",
            "search_artists": "artists",
            "search_playlists": "playlists",
        }
        key = section_map.get(operation)
        if key:
            section = data.get(key, {})
            if isinstance(section, dict):
                return not section.get('items')

        return False

    def _try_qobuz_for_track(self, track_id: int, quality: str = "LOSSLESS", isrc: Optional[str] = None) -> Optional[Dict]:
        if not isrc:
            meta = self.get_track_metadata(track_id)
            if not meta:
                return None
            isrc = meta.get('isrc')
            if not isrc:
                return None

        result = self.get_qobuz_stream_url(isrc, quality)
        if not result or not result.get('url'):
            return None

        response = [
            {'duration': 0, 'id': track_id, 'isrc': isrc},
            {
                'OriginalTrackUrl': result['url'],
                'trackId': track_id,
                'audioQuality': quality,
                'source': 'qobuz',
                'endpoint': result.get('endpoint'),
            },
        ]
        if result.get('rgInfo'):
            response[1]['replayGain'] = result['rgInfo']

        logger.info(f"Qobuz fallback OK for track {track_id} via {result.get('endpoint')}")
        return response

    def get_qobuz_stream_url(self, isrc: str, quality: str = "LOSSLESS") -> Optional[Dict]:
        if not self.qobuz_endpoints or not isrc:
            return None

        quality_map = {
            'HI_RES_LOSSLESS': '27',
            'HI_RES': '27',
            'LOSSLESS': '6',
            'HIGH': '5',
            'LOW': '5',
        }
        qobuz_quality = quality_map.get(quality, '6')
        logger.info(f"Qobuz lookup: ISRC {isrc} quality {quality} -> {qobuz_quality}")

        for idx, endpoint in enumerate(self.qobuz_endpoints, 1):
            base_url = endpoint['url']
            label = f"[{idx}/{len(self.qobuz_endpoints)}] {endpoint['name']}"

            try:
                search = self.session.get(
                    f"{base_url}/api/get-music?q={isrc}&offset=0",
                    timeout=8,
                )
                if search.status_code != 200:
                    logger.debug(f"{label} search returned {search.status_code}")
                    continue

                tracks = search.json().get('data', {}).get('tracks', {}).get('items', [])
                if not tracks:
                    logger.debug(f"{label} no tracks for ISRC {isrc}")
                    continue

                match = next((t for t in tracks if t.get('isrc', '').lower() == isrc.lower()), tracks[0])
                qobuz_id = match.get('id')
                if not qobuz_id:
                    continue

                dl = self.session.get(
                    f"{base_url}/api/download-music?track_id={qobuz_id}&quality={qobuz_quality}",
                    timeout=8,
                )
                if dl.status_code != 200:
                    logger.debug(f"{label} download returned {dl.status_code}")
                    continue

                dl_data = dl.json()
                stream_url = dl_data.get('data', {}).get('url') if dl_data.get('success') else None
                if not stream_url:
                    continue

                rg_info = None
                if audio_info := match.get('audio_info'):
                    rg_info = {
                        'trackReplayGain': audio_info.get('replaygain_track_gain'),
                        'trackPeakAmplitude': audio_info.get('replaygain_track_peak'),
                        'albumReplayGain': audio_info.get('replaygain_album_gain'),
                        'albumPeakAmplitude': audio_info.get('replaygain_album_peak'),
                    }

                logger.info(f"Qobuz OK via {endpoint['name']} for ISRC {isrc}")
                return {'url': stream_url, 'rgInfo': rg_info, 'source': 'qobuz', 'endpoint': endpoint['name']}

            except requests.exceptions.Timeout:
                logger.debug(f"{label} timed out")
            except requests.exceptions.RequestException as e:
                logger.debug(f"{label} failed: {e}")
            except Exception as e:
                logger.warning(f"{label} unexpected error: {e}")

        logger.info(f"Qobuz failed for ISRC {isrc}")
        return None

    # -------------------------------------------------------------------------
    # Public API methods
    # -------------------------------------------------------------------------

    def search_tracks(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"s": query}, operation="search_tracks")

    def search_albums(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"al": query}, operation="search_albums")

    def search_artists(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"a": query}, operation="search_artists")

    def search_playlists(self, query: str) -> Optional[Dict]:
        return self._make_request("/search/", {"p": query}, operation="search_playlists")

    def get_track(self, track_id: int, quality: str = "LOSSLESS") -> Optional[Dict]:
        return self._make_request("/track/", {"id": track_id, "quality": quality}, operation="get_track")

    def get_track_metadata(self, track_id: int) -> Optional[Dict]:
        result = self._make_request("/info/", {"id": track_id}, operation="get_track_metadata")
        if not result:
            return None
        if isinstance(result, dict):
            if 'data' in result:
                return result['data']
            if 'id' in result or 'isrc' in result:
                return result
        if isinstance(result, list) and result:
            return result[0]
        return None

    def get_album(self, album_id: int) -> Optional[Dict]:
        return self._make_request("/album/", {"id": album_id}, operation="get_album")

    def get_album_tracks(self, album_id: int) -> Optional[Dict]:
        return self._make_request("/album/", {"id": album_id}, operation="get_album_tracks")

    def get_artist(self, artist_id: int) -> Optional[Dict]:
        return self._make_request("/artist/", {"f": artist_id}, operation="get_artist")

    def get_playlist(self, playlist_id: str) -> Optional[Dict]:
        return self._make_request("/playlist/", {"id": playlist_id}, operation="get_playlist")

    def get_playlist_tracks(self, playlist_id: str) -> Optional[Dict]:
        all_items = []
        offset = 0
        limit = 100
        base_response = None

        while True:
            data = self._make_request(
                "/playlist/",
                {"id": playlist_id, "offset": offset, "limit": limit},
                operation="get_playlist_tracks",
            )
            if not data:
                break

            if not base_response and isinstance(data, dict):
                base_response = data

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('items', [])
                if not items and 'tracks' in data:
                    tracks = data['tracks']
                    items = tracks.get('items', []) if isinstance(tracks, dict) else tracks

            if not items:
                break

            all_items.extend(items)

            if len(items) < limit or len(all_items) >= 10000:
                if len(all_items) >= 10000:
                    logger.warning(f"Playlist {playlist_id} truncated at 10000 tracks")
                break

            offset += limit

        if base_response:
            base_response['items'] = all_items
            base_response['totalNumberOfItems'] = len(all_items)
            if 'tracks' in base_response and isinstance(base_response['tracks'], dict):
                base_response['tracks']['items'] = all_items
                base_response['tracks']['totalNumberOfItems'] = len(all_items)
            return base_response

        return {'items': all_items, 'totalNumberOfItems': len(all_items)}

    def get_artist_albums(self, artist_id: int) -> Optional[Dict]:
        return self._make_request(f"/artist/{artist_id}/albums", operation="get_artist_albums")

    # -------------------------------------------------------------------------
    # Download status cache (used by queue manager)
    # -------------------------------------------------------------------------

    def get_download_status(self, track_id: int) -> Optional[Dict]:
        if track_id in self.download_status_cache:
            cached = self.download_status_cache[track_id]
            if time.time() - cached['timestamp'] < 300:
                return cached['status']
        return None

    def set_download_status(self, track_id: int, status: Dict):
        self.download_status_cache[track_id] = {'status': status, 'timestamp': time.time()}

    def clear_download_status(self, track_id: int):
        self.download_status_cache.pop(track_id, None)

    def cleanup_old_status_cache(self):
        cutoff = time.time() - 300
        expired = [k for k, v in self.download_status_cache.items() if v['timestamp'] < cutoff]
        for k in expired:
            del self.download_status_cache[k]
