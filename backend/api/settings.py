from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    music_dir: str = str(Path.home() / "music")
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    sync_time: str = "04:00"
    organization_template: str = "{Artist}/{Album}/{TrackNumber} - {Title}"
    active_downloads: int = 3
    
    # Feature toggles
    use_musicbrainz: bool = True
    run_beets: bool = False
    embed_lyrics: bool = False
    group_compilations: bool = True
    
    # Jellyfin Integration
    jellyfin_url: Optional[str] = None
    jellyfin_api_key: Optional[str] = None
    
    class Config:
        env_file = Path(__file__).parent.parent.parent / ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()

DOWNLOAD_DIR = Path(settings.music_dir)
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

PLAYLISTS_DIR = DOWNLOAD_DIR / "tidaloader_playlists"
PLAYLISTS_DIR.mkdir(parents=True, exist_ok=True)

MP3_QUALITY_MAP = {
    "MP3_128": 128,
    "MP3_256": 256,
}

OPUS_QUALITY_MAP = {
    "OPUS_192VBR": 192,
}
