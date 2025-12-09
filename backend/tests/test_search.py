from unittest.mock import MagicMock
import os

# Set dummy auth for tests
os.environ["AUTH_USERNAME"] = "test"
os.environ["AUTH_PASSWORD"] = "test"

# Mock Authorization header
AUTH_HEADER = {"Authorization": "Basic dGVzdDp0ZXN0"} # test:test

def test_search_tracks_success(client, mock_tidal_client):
    # Setup mock response
    mock_tidal_client.search_tracks.return_value = {
        "tracks": {
            "items": [
                {
                    "id": 123,
                    "title": "Test Track",
                    "artist": {"name": "Test Artist"},
                    "album": {"title": "Test Album", "cover": "abc-123"},
                    "duration": 300,
                    "audioQuality": "LOSSLESS"
                }
            ]
        }
    }
    
    response = client.get("/api/search/tracks?q=test", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test Track"
    assert data["items"][0]["artist"] == "Test Artist"

def test_search_tracks_empty(client, mock_tidal_client):
    mock_tidal_client.search_tracks.return_value = {}
    
    response = client.get("/api/search/tracks?q=empty", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []

def test_search_albums_success(client, mock_tidal_client):
    mock_tidal_client.search_albums.return_value = {
        "albums": {
            "items": [
                {"id": 456, "title": "Test Album"}
            ]
        }
    }
    
    response = client.get("/api/search/albums?q=test", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Test Album"

def test_search_playlists_success(client, mock_tidal_client):
    mock_tidal_client.search_playlists.return_value = {
        "playlists": {
            "items": [
                {
                    "uuid": "playlist-123",
                    "title": "My Playlist",
                    "creator": {"name": "Tester"},
                    "numberOfTracks": 2,
                    "image": "abc-123"
                }
            ]
        }
    }
    
    response = client.get("/api/search/playlists?q=test", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "playlist-123"
    assert data["items"][0]["title"] == "My Playlist"
    assert data["items"][0]["cover"] == "abc-123"


def test_search_playlists_squareimage_priority(client, mock_tidal_client):
    # squareImage should be preferred over image/cover
    mock_tidal_client.search_playlists.return_value = {
        "playlists": {
            "items": [
                {
                    "id": "playlist-xyz",
                    "title": "Square First",
                    "image": "image-low",
                    "cover": "cover-low",
                    "squareImage": "square-hi"
                }
            ]
        }
    }

    response = client.get("/api/search/playlists?q=test", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["cover"] == "square-hi"

def test_search_unauthorized(client):
    response = client.get("/api/search/tracks?q=test")
    assert response.status_code == 401

def test_get_playlist_tracks(client, mock_tidal_client):
    mock_tidal_client.get_playlist_tracks.return_value = {
        "playlist": {
            "uuid": "playlist-123",
            "title": "My Playlist"
        },
        "items": [
            {
                "item": {
                    "id": 111,
                    "title": "Song One",
                    "artist": {"name": "Artist A"},
                    "album": {"title": "Album A", "cover": "cov1"},
                    "duration": 200
                }
            },
            {
                "item": {
                    "id": 222,
                    "title": "Song Two",
                    "artist": {"name": "Artist B"},
                    "album": {"title": "Album B", "cover": "cov2"},
                    "duration": 180
                }
            }
        ]
    }
    
    response = client.get("/api/playlist/playlist-123", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert data["playlist"]["title"] == "My Playlist"
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Song One"
