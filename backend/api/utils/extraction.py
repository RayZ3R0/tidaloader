import base64
import json
import re
from typing import List, Optional, Dict

from api.utils.logging import log_info, log_warning, log_error


def extract_items(result, key: str) -> List:
    if not result:
        log_warning("extract_items received empty result")
        return []

    if isinstance(result, list):
        if result and isinstance(result[0], dict) and key in result[0]:
            nested = result[0][key]
            if isinstance(nested, dict) and 'items' in nested:
                return nested['items']
            if isinstance(nested, list):
                return nested
        return result

    if isinstance(result, dict):
        if key in result and isinstance(result[key], dict):
            return result[key].get('items', [])
        if 'items' in result:
            return result['items']

    log_warning(f"Key '{key}' not found in result. Keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
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


def extract_isrc(track_data) -> Optional[str]:
    entries = track_data if isinstance(track_data, list) else [track_data]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if 'isrc' in entry:
            return entry['isrc']
        if isinstance(entry.get('item'), dict) and 'isrc' in entry['item']:
            return entry['item']['isrc']
    return None


def _decode_manifest(manifest) -> Optional[str]:
    try:
        decoded = base64.b64decode(manifest).decode('utf-8')
    except Exception:
        return None

    try:
        parsed = json.loads(decoded)
        urls = parsed.get('urls', [])
        if urls:
            return urls[0]
    except json.JSONDecodeError:
        pass

    match = re.search(r'https?://[^\s"]+', decoded)
    return match.group(0) if match else None


def extract_stream_url(track_data) -> Optional[str]:
    entries = track_data if isinstance(track_data, list) else [track_data]

    for entry in entries:
        if isinstance(entry, dict) and 'OriginalTrackUrl' in entry:
            return entry['OriginalTrackUrl']

    for entry in entries:
        if isinstance(entry, dict) and 'manifest' in entry:
            url = _decode_manifest(entry['manifest'])
            if url:
                return url
            log_error("Failed to decode manifest")

    return None


def extract_stream_url_with_qobuz_fallback(track_data, quality: str = "LOSSLESS") -> Dict:
    entries = track_data if isinstance(track_data, list) else [track_data]

    for entry in entries:
        if isinstance(entry, dict) and 'OriginalTrackUrl' in entry:
            return {'url': entry['OriginalTrackUrl'], 'source': 'tidal', 'rgInfo': None}

    for entry in entries:
        if isinstance(entry, dict) and 'manifest' in entry:
            url = _decode_manifest(entry['manifest'])
            if url:
                return {'url': url, 'source': 'tidal', 'rgInfo': None}
            log_error("Failed to decode manifest")

    isrc = extract_isrc(track_data)
    if isrc:
        try:
            from api.clients import tidal_client
            result = tidal_client.get_qobuz_stream_url(isrc, quality)
            if result and result.get('url'):
                log_info(f"Using Qobuz stream for ISRC {isrc}")
                return {
                    'url': result['url'],
                    'source': 'qobuz',
                    'rgInfo': result.get('rgInfo'),
                    'endpoint': result.get('endpoint'),
                }
        except Exception as e:
            log_warning(f"Qobuz fallback failed: {e}")

    return {'url': None, 'source': None, 'rgInfo': None}
