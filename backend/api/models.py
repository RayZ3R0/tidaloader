from typing import Optional
from dataclasses import dataclass
from pydantic import BaseModel

@dataclass
class PlaylistTrack:
    """Track from generated playlist"""
    title: str
    artist: str
    mbid: Optional[str] = None
    tidal_id: Optional[int] = None
    tidal_artist_id: Optional[int] = None
    tidal_album_id: Optional[int] = None
    tidal_exists: bool = False
    album: Optional[str] = None
    cover: Optional[str] = None

class ListenBrainzGenerateRequest(BaseModel):
    username: str
    playlist_type: str = "periodic-jams"
    should_validate: bool = True

class SpotifyGenerateRequest(BaseModel):
    playlist_url: str

class ValidateTrackRequest(BaseModel):
    track: PlaylistTrack

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

class ListenBrainzTrackResponse(BaseModel):
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
