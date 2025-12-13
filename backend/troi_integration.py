"""
Troi command execution and playlist parsing
"""
import re
import subprocess
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class TroiTrack:
    """Track from Troi playlist"""
    title: str
    artist: str
    mbid: Optional[str] = None
    tidal_id: Optional[int] = None
    tidal_artist_id: Optional[int] = None
    tidal_album_id: Optional[int] = None
    tidal_exists: bool = False
    album: Optional[str] = None

class TroiIntegration:
    """Execute Troi and parse playlists"""
    
    @staticmethod
    def generate_playlist(username: str, playlist_type: str = "periodic-jams") -> List[TroiTrack]:
        """
        Run Troi and generate playlist
        
        Args:
            username: ListenBrainz username
            playlist_type: "periodic-jams" or "daily-jams"
        
        Returns:
            List of TroiTrack objects
        """
        cmd = ["troi", "playlist", playlist_type, username]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            
            # Troi outputs to STDERR
            output = result.stderr if result.stderr else result.stdout
            return TroiIntegration._parse_output(output)
            
        except subprocess.TimeoutExpired:
            raise Exception("Troi command timed out after 60 seconds")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Troi command failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception("Troi not found. Install with: pip install troi-recommendation-playground")
    
    @staticmethod
    def _parse_output(output: str) -> List[TroiTrack]:
        """Parse Troi command output"""
        tracks = []
        lines = output.split('\n')
        
        in_track_list = False
        
        for line in lines:
            if 'playlist:' in line:
                in_track_list = True
                continue
            
            if not in_track_list:
                continue
            
            if 'description:' in line or line.strip() == '':
                if 'description:' in line:
                    break
                continue
            
            # Parse format: "Title                    Artist                    mbid1 mbid2    ..."
            parts = re.split(r'\s{2,}', line.strip())
            
            if len(parts) >= 2:
                title = parts[0].strip()
                artist = parts[1].strip()
                mbid = parts[2].strip()[:5] if len(parts) > 2 else None
                
                if title and artist:
                    tracks.append(TroiTrack(
                        title=title,
                        artist=artist,
                        mbid=mbid
                    ))
        
        return tracks