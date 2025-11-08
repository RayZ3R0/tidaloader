/**
 * API client for Troi Tidal Downloader backend
 */

import { useAuthStore } from "../store/authStore";

const API_BASE = "/api";

class ApiClient {
  /**
   * Get authorization headers
   */
  getHeaders() {
    const headers = {
      "Content-Type": "application/json",
    };

    const authHeader = useAuthStore.getState().getAuthHeader();
    if (authHeader) {
      headers["Authorization"] = authHeader;
    }

    return headers;
  }

  /**
   * Make GET request with auth
   */
  async get(path, params = {}) {
    const url = new URL(API_BASE + path, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, value);
      }
    });

    const response = await fetch(url, {
      headers: this.getHeaders(),
      credentials: "include",
    });

    if (response.status === 401) {
      useAuthStore.getState().clearCredentials();
      throw new Error("Authentication required");
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Make POST request with auth
   */
  async post(path, data = {}) {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(data),
      credentials: "include",
    });

    if (response.status === 401) {
      useAuthStore.getState().clearCredentials();
      throw new Error("Authentication required");
    }

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return response.json();
  }

  /**
   * Search for tracks
   */
  searchTracks(query) {
    return this.get("/search/tracks", { q: query });
  }

  /**
   * Search for albums
   */
  searchAlbums(query) {
    return this.get("/search/albums", { q: query });
  }

  /**
   * Search for artists
   */
  searchArtists(query) {
    return this.get("/search/artists", { q: query });
  }

  /**
   * Get album tracks
   */
  getAlbumTracks(albumId) {
    return this.get(`/album/${albumId}/tracks`);
  }

  /**
   * Get artist details
   */
  getArtist(artistId) {
    return this.get(`/artist/${artistId}`);
  }

  /**
   * Get stream URL for track
   */
  getStreamUrl(trackId, quality = "LOSSLESS") {
    return this.get(`/download/stream/${trackId}`, { quality });
  }

  /**
   * Download track server-side
   */
  downloadTrack(trackId, artist, title, quality = "LOSSLESS") {
    return this.post("/download/track", {
      track_id: trackId,
      artist,
      title,
      quality,
    });
  }

  /**
   * Generate Troi playlist
   */
  generateTroiPlaylist(username, playlistType = "periodic-jams") {
    return this.post("/troi/generate", {
      username,
      playlist_type: playlistType,
    });
  }

  /**
   * Create Server-Sent Events stream for download progress
   */
  createProgressStream(trackId) {
    const authHeader = useAuthStore.getState().getAuthHeader();
    const url = new URL(
      `${API_BASE}/download/progress/${trackId}`,
      window.location.origin
    );

    // Create EventSource with custom headers via fetch
    return new EventSource(url.toString(), {
      withCredentials: true,
    });
  }

  /**
   * Get cover URL from Tidal
   */
  getCoverUrl(coverId, size = "640") {
    if (!coverId) return null;

    // Handle different cover ID formats
    const cleanId = String(coverId).replace(/-/g, "/");
    return `https://resources.tidal.com/images/${cleanId}/${size}x${size}.jpg`;
  }
}

export const api = new ApiClient();
