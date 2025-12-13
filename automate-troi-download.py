#!/usr/bin/env python3
"""
Automate Troi playlist downloads using Tidal API
Downloads tracks from Troi periodic-jams playlists to local directory
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import quote
import requests
from dataclasses import dataclass

# Load API endpoints from config file
ENDPOINTS_FILE = Path(__file__).parent / "api_endpoints.json"

# Default endpoints (will be saved to file)
DEFAULT_ENDPOINTS = [
    {"name": "kraken", "url": "https://kraken.squid.wtf", "priority": 1},
    {"name": "triton", "url": "https://triton.squid.wtf", "priority": 1},
    {"name": "zeus", "url": "https://zeus.squid.wtf", "priority": 1},
    {"name": "aether", "url": "https://aether.squid.wtf", "priority": 1},
    {"name": "phoenix", "url": "https://phoenix.squid.wtf", "priority": 1},
    {"name": "shiva", "url": "https://shiva.squid.wtf", "priority": 1},
    {"name": "chaos", "url": "https://chaos.squid.wtf", "priority": 1},
    {"name": "vercel", "url": "https://tidal-api-2.binimum.org", "priority": 5},
    {"name": "jakarta", "url": "https://jakarta.monochrome.tf", "priority": 2},
    {"name": "california", "url": "https://california.monochrome.tf", "priority": 2},
    {"name": "london", "url": "https://london.monochrome.tf", "priority": 2},
    {"name": "hund", "url": "https://hund.qqdl.site", "priority": 2},
    {"name": "katze", "url": "https://katze.qqdl.site", "priority": 2},
    {"name": "maus", "url": "https://maus.qqdl.site", "priority": 2},
    {"name": "vogel", "url": "https://vogel.qqdl.site", "priority": 2},
    {"name": "wolf", "url": "https://wolf.qqdl.site", "priority": 2},
    {"name": "monochrome", "url": "https://hifi.prigoana.com", "priority": 2},
    {"name": "singapore", "url": "https://singapore.monochrome.tf", "priority": 3},
    {"name": "ohio", "url": "https://ohio.monochrome.tf", "priority": 3},
    {"name": "oregon", "url": "https://oregon.monochrome.tf", "priority": 3},
    {"name": "virginia", "url": "https://virginia.monochrome.tf", "priority": 3},
    {"name": "frankfurt", "url": "https://frankfurt.monochrome.tf", "priority": 3},
    {"name": "tokyo", "url": "https://tokyo.monochrome.tf", "priority": 3},
]

DOWNLOAD_DIR = Path(__file__).parent / "downloads"
QUALITY = "LOSSLESS"  # or "HI_RES_LOSSLESS" for hi-res
RATE_LIMIT_DELAY = 1.0  # seconds between downloads
MAX_RETRIES = 3
DEBUG = True  # Enable debug output
TEST_MODE = True  # Only download first 5 tracks

def debug_print(msg: str):
    """Print debug messages"""
    if DEBUG:
        print(f"[DEBUG] {msg}")

def load_endpoints() -> List[Dict]:
    """Load endpoints from file or create default"""
    if ENDPOINTS_FILE.exists():
        try:
            with open(ENDPOINTS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('endpoints', DEFAULT_ENDPOINTS)
        except Exception as e:
            debug_print(f"Failed to load endpoints file: {e}")
    
    # Save default endpoints
    save_endpoints(DEFAULT_ENDPOINTS)
    return DEFAULT_ENDPOINTS

def save_endpoints(endpoints: List[Dict]):
    """Save endpoints to file"""
    try:
        with open(ENDPOINTS_FILE, 'w') as f:
            json.dump({'endpoints': endpoints, 'last_updated': time.time()}, f, indent=2)
    except Exception as e:
        debug_print(f"Failed to save endpoints: {e}")

@dataclass
class Track:
    title: str
    artist: str
    album: Optional[str] = None
    mbid: Optional[str] = None

class TidalAPIClient:
    """Client for Tidal API with automatic endpoint rotation and learning"""
    
    def __init__(self):
        self.endpoints = load_endpoints()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.success_history = {}  # Track which endpoints work for which operations
    
    def _sort_endpoints_by_priority(self, operation: str = None) -> List[Dict]:
        """Sort endpoints by priority and success history"""
        endpoints = self.endpoints.copy()
        
        # Boost priority for recently successful endpoints
        if operation and operation in self.success_history:
            last_success = self.success_history[operation]
            for ep in endpoints:
                if ep['name'] == last_success['name']:
                    ep = ep.copy()
                    ep['priority'] = 0  # Highest priority
                    debug_print(f"Prioritizing {ep['name']} (last successful for {operation})")
        
        # Sort by priority (lower number = higher priority)
        return sorted(endpoints, key=lambda x: (x.get('priority', 999), x['name']))
    
    def _record_success(self, endpoint: Dict, operation: str):
        """Record successful endpoint for operation"""
        self.success_history[operation] = {
            'name': endpoint['name'],
            'url': endpoint['url'],
            'timestamp': time.time()
        }
        debug_print(f"Recorded success: {endpoint['name']} for {operation}")
    
    def _make_request(self, path: str, params: Dict = None, operation: str = None) -> Optional[Dict]:
        """Make request with automatic endpoint rotation on failure"""
        sorted_endpoints = self._sort_endpoints_by_priority(operation)
        
        for endpoint in sorted_endpoints:
            url = f"{endpoint['url']}{path}"
            
            try:
                response = self.session.get(url, params=params, timeout=10)
                
                if response.status_code == 429:
                    print(f"⚠️  Rate limited on {endpoint['name']}, trying next endpoint...")
                    time.sleep(2)
                    continue
                
                if response.status_code == 500:
                    print(f"⚠️  {endpoint['name']} returned 500, trying next endpoint...")
                    continue
                
                if response.status_code == 404:
                    print(f"⚠️  {endpoint['name']} returned 404, trying next endpoint...")
                    continue
                
                if response.status_code == 200:
                    self._record_success(endpoint, operation or path)
                    return response.json()
                
                print(f"⚠️  {endpoint['name']} returned {response.status_code}, trying next endpoint...")
                
            except requests.exceptions.RequestException as e:
                print(f"⚠️  Error with {endpoint['name']}: {e}, trying next endpoint...")
                continue
        
        return None
    
    def search_track(self, query: str) -> Optional[Dict]:
        """Search for a track"""
        return self._make_request("/search/", {"s": query}, operation="search")
    
    def get_track(self, track_id: int) -> Optional[Dict]:
        """Get track details with stream URL"""
        return self._make_request("/track/", {"id": track_id, "quality": QUALITY}, operation="track")

class TroiPlaylistParser:
    """Parser for Troi playlist output"""
    
    @staticmethod
    def parse_output(output: str) -> List[Track]:
        """Parse Troi command output into Track objects"""
        tracks = []
        lines = output.split('\n')
        
        debug_print(f"Total lines in output: {len(lines)}")
        
        in_track_list = False
        line_num = 0
        
        for line in lines:
            line_num += 1
            
            # Look for playlist marker
            if 'playlist:' in line:
                debug_print(f"Found playlist marker at line {line_num}")
                in_track_list = True
                continue
            
            if not in_track_list:
                continue
            
            # Stop at description or empty line after tracks
            if 'description:' in line:
                debug_print(f"Found description marker at line {line_num}, stopping")
                break
            
            if line.strip() == '':
                continue
            
            # Parse format: "Title                    Artist                    mbid1 mbid2    ..."
            # Split on 2+ spaces
            parts = re.split(r'\s{2,}', line.strip())
            
            if len(parts) >= 2:
                title = parts[0].strip()
                artist = parts[1].strip()
                mbid = parts[2].strip()[:5] if len(parts) > 2 else None
                
                if title and artist:
                    track = Track(
                        title=title,
                        artist=artist,
                        mbid=mbid
                    )
                    tracks.append(track)
        
        return tracks

class TroiTidalDownloader:
    """Main downloader class"""
    
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.api = TidalAPIClient()
    
    def run_troi(self, username: str) -> List[Track]:
        """Run Troi and get playlist"""
        print("🎵 Generating Troi playlist...")
        
        # Check if troi is available
        try:
            version_check = subprocess.run(
                ["troi", "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            debug_print("Troi is available")
        except FileNotFoundError:
            print("✗ ERROR: 'troi' command not found. Is it installed?")
            print("  Install with: pip install troi-recommendation-playground")
            sys.exit(1)
        except Exception as e:
            print(f"✗ ERROR: Could not verify troi installation: {e}")
            sys.exit(1)
        
        # Run troi command
        cmd = ["troi", "playlist", "periodic-jams", username]
        debug_print(f"Running command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            debug_print(f"Command exit code: {result.returncode}")
            debug_print(f"STDOUT length: {len(result.stdout)} chars")
            debug_print(f"STDERR length: {len(result.stderr)} chars")
            
            # Troi outputs to STDERR, not STDOUT!
            output = result.stderr if result.stderr else result.stdout
            
            if result.stderr:
                debug_print("Using STDERR as output source")
            
            # Save raw output for inspection
            debug_file = Path(__file__).parent / "troi_debug_output.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write("=== STDOUT ===\n")
                f.write(result.stdout)
                f.write("\n\n=== STDERR ===\n")
                f.write(result.stderr)
            debug_print(f"Saved raw output to: {debug_file}")
            
            tracks = TroiPlaylistParser.parse_output(output)
            print(f"✓ Found {len(tracks)} tracks")
            
            if TEST_MODE and len(tracks) > 5:
                print(f"\n⚠️  TEST MODE: Limiting to first 5 tracks")
                tracks = tracks[:5]
            
            return tracks
            
        except subprocess.TimeoutExpired:
            print(f"✗ Troi command timed out after 60 seconds")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"✗ Troi command failed with exit code {e.returncode}")
            print(f"\nSTDOUT:")
            print(e.stdout)
            print(f"\nSTDERR:")
            print(e.stderr)
            sys.exit(1)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem"""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()
    
    def search_on_tidal(self, track: Track) -> Optional[Dict]:
        """Search for track on Tidal"""
        query = f"{track.artist} {track.title}"
        print(f"  🔍 Searching: {query}")
        
        result = self.api.search_track(query)
        if not result:
            return None
        
        # Navigate nested structure
        tracks = None
        if isinstance(result, dict):
            if 'tracks' in result and isinstance(result['tracks'], dict):
                tracks = result['tracks'].get('items', [])
            elif 'items' in result:
                tracks = result['items']
        
        if tracks and len(tracks) > 0:
            return tracks[0]
        
        return None
    
    def extract_stream_url(self, track_data: Dict) -> Optional[str]:
        """Extract stream URL from track data"""
        # Handle array response
        if isinstance(track_data, list):
            entries = track_data
        else:
            entries = [track_data]
        
        # Try OriginalTrackUrl first
        for entry in entries:
            if isinstance(entry, dict) and 'OriginalTrackUrl' in entry:
                return entry['OriginalTrackUrl']
        
        # Try manifest
        for entry in entries:
            if isinstance(entry, dict) and 'manifest' in entry:
                manifest = entry['manifest']
                try:
                    import base64
                    decoded = base64.b64decode(manifest).decode('utf-8')
                    
                    # Try JSON parse
                    try:
                        manifest_json = json.loads(decoded)
                        if 'urls' in manifest_json and manifest_json['urls']:
                            return manifest_json['urls'][0]
                    except json.JSONDecodeError:
                        pass
                    
                    # Try regex
                    url_match = re.search(r'https?://[^\s"]+', decoded)
                    if url_match:
                        return url_match.group(0)
                except Exception as e:
                    print(f"    ⚠️  Failed to decode manifest: {e}")
        
        return None
    
    def download_track(self, track: Track, tidal_track: Dict, stream_url: str) -> bool:
        """Download track to file"""
        filename = self.sanitize_filename(f"{track.artist} - {track.title}.flac")
        filepath = self.download_dir / filename
        
        # Skip if already exists
        if filepath.exists():
            print(f"  ⏭️  Already exists: {filename}")
            return True
        
        print(f"  ⬇️  Downloading: {filename}")
        
        try:
            response = self.api.session.get(stream_url, stream=True, timeout=30)
            
            if response.status_code == 429:
                print(f"  ✗ Rate limited")
                return False
            
            if not response.ok:
                print(f"  ✗ Download failed: HTTP {response.status_code}")
                return False
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"    Progress: {progress:.1f}%", end='\r')
            
            print(f"\n  ✓ Downloaded: {filename} ({downloaded / 1024 / 1024:.2f} MB)")
            return True
            
        except Exception as e:
            print(f"  ✗ Download error: {e}")
            if filepath.exists():
                filepath.unlink()  # Clean up partial file
            return False
    
    def process_tracks(self, tracks: List[Track]):
        """Process and download all tracks"""
        print(f"\n{'='*60}")
        print(f"Processing {len(tracks)} tracks")
        print(f"Download directory: {self.download_dir}")
        if TEST_MODE:
            print(f"⚠️  TEST MODE ENABLED - Only processing first 5 tracks")
        print(f"{'='*60}\n")
        
        success_count = 0
        fail_count = 0
        
        for i, track in enumerate(tracks, 1):
            print(f"\n[{i}/{len(tracks)}] {track.artist} - {track.title}")
            
            # Search on Tidal
            tidal_track = self.search_on_tidal(track)
            if not tidal_track:
                print(f"  ✗ Not found on Tidal")
                fail_count += 1
                continue
            
            # Get track details
            track_id = tidal_track.get('id')
            if not track_id:
                print(f"  ✗ No track ID")
                fail_count += 1
                continue
            
            print(f"  ℹ️  Track ID: {track_id}")
            
            # Get stream URL
            track_data = self.api.get_track(track_id)
            if not track_data:
                print(f"  ✗ Failed to get track data")
                fail_count += 1
                continue
            
            stream_url = self.extract_stream_url(track_data)
            if not stream_url:
                print(f"  ✗ Could not extract stream URL")
                fail_count += 1
                continue
            
            # Download
            if self.download_track(track, tidal_track, stream_url):
                success_count += 1
            else:
                fail_count += 1
            
            # Rate limit protection
            time.sleep(RATE_LIMIT_DELAY)
        
        print(f"\n{'='*60}")
        print(f"Download Summary")
        print(f"{'='*60}")
        print(f"Total tracks: {len(tracks)}")
        print(f"✓ Success: {success_count}")
        print(f"✗ Failed: {fail_count}")
        print(f"{'='*60}\n")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automate Troi playlist downloads from Tidal"
    )
    parser.add_argument(
        "username",
        help="ListenBrainz username"
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=DOWNLOAD_DIR,
        help=f"Download directory (default: {DOWNLOAD_DIR})"
    )
    parser.add_argument(
        "--no-debug",
        action="store_true",
        help="Disable debug output"
    )
    parser.add_argument(
        "--no-test-mode",
        action="store_true",
        help="Download all tracks (not just first 5)"
    )
    
    args = parser.parse_args()
    
    # Set debug mode
    global DEBUG, TEST_MODE
    DEBUG = not args.no_debug
    TEST_MODE = not args.no_test_mode
    
    print("🎵 Troi → Tidaloader")
    print(f"Username: {args.username}")
    print(f"Download directory: {args.download_dir}")
    print(f"Debug mode: {'ON' if DEBUG else 'OFF'}")
    print(f"Test mode: {'ON (first 5 tracks only)' if TEST_MODE else 'OFF (all tracks)'}\n")
    
    downloader = TroiTidalDownloader(args.download_dir)
    
    # Generate playlist
    tracks = downloader.run_troi(args.username)
    
    if not tracks:
        print("✗ No tracks found")
        print("\nCheck the debug output file: troi_debug_output.txt")
        sys.exit(1)
    
    # Download tracks
    downloader.process_tracks(tracks)

if __name__ == "__main__":
    main()