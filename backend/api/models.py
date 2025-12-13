from typing import Optional
from pydantic import BaseModel

class TroiGenerateRequest(BaseModel):
    username: str
    playlist_type: str = "periodic-jams"

class TrackSearchResult(BaseModel):
    id: int
    title: str
    artist: str
    album: Optional[str] = None
    track_number: Optional[int] = None
    duration: Optional[int] = None
    cover: Optional[str] = None
    quality: Optional[str] = None
    trackNumber: Optional[int] = None
    albumArtist: Optional[str] = None
    tidal_artist_id: Optional[int] = None
    tidal_album_id: Optional[int] = None

class PlaylistSearchResult(BaseModel):
    id: str
    title: str
    creator: Optional[str] = None
    description: Optional[str] = None
    numberOfTracks: Optional[int] = None
    cover: Optional[str] = None

class TroiTrackResponse(BaseModel):
    title: str
    artist: str
    mbid: Optional[str]
    tidal_id: Optional[int]
    tidal_exists: bool
    album: Optional[str]

class DownloadTrackRequest(BaseModel):
    track_id: int
    artist: str
    title: str
    album: Optional[str] = None
    album_id: Optional[int] = None
    track_number: Optional[int] = None
    cover: Optional[str] = None
    quality: Optional[str] = "LOSSLESS"
    organization_template: Optional[str] = "{Artist}/{Album}/{TrackNumber} - {Title}"
    group_compilations: Optional[bool] = True
    run_beets: Optional[bool] = False
    embed_lyrics: Optional[bool] = False
    tidal_track_id: Optional[str] = None
    tidal_artist_id: Optional[str] = None
    tidal_album_id: Optional[str] = None
