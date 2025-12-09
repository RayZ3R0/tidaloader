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

  getAuthHeaders() {
    const authHeader = useAuthStore.getState().getAuthHeader();
    return authHeader ? { Authorization: authHeader } : {};
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
   * Search for playlists
   */
  searchPlaylists(query) {
    return this.get("/search/playlists", { q: query });
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
   * Get playlist details and tracks
   */
  getPlaylist(playlistId) {
    return this.get(`/playlist/${playlistId}`);
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
   * Create Troi progress stream
   */
  createTroiProgressStream(progressId) {
    const authHeader = useAuthStore.getState().getAuthHeader();
    const url = new URL(
      `${API_BASE}/troi/progress/${progressId}`,
      window.location.origin
    );

    const eventSource = new EventSource(url.toString(), {
      withCredentials: true,
    });

    return eventSource;
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

    return new EventSource(url.toString(), {
      withCredentials: true,
    });
  }

  /**
   * Get cover URL from Tidal
   */
  getCoverUrl(coverId, size = "640") {
    const variants = this.getCoverUrlVariants(coverId, [size]);
    return variants.length > 0 ? variants[0] : null;
  }

  /**
   * Return multiple size variants for a cover ID or URL (largest to smallest)
   */
  getCoverUrlVariants(coverId, sizes = ["640", "320", "160"]) {
    if (!coverId) return [];
    if (typeof coverId === "string" && coverId.startsWith("http")) {
      return [coverId];
    }

    const cleanOriginal = String(coverId).replace(/-/g, "/");
    const candidates = [
      cleanOriginal,
      cleanOriginal.toUpperCase(),
      cleanOriginal.toLowerCase(),
    ].filter(Boolean);

    const urls = [];
    for (const id of candidates) {
      for (const s of sizes) {
        const url = `https://resources.tidal.com/images/${id}/${s}x${s}.jpg`;
        if (!urls.includes(url)) {
          urls.push(url);
        }
      }
    }
    return urls;
  }

  get baseUrl() {
    return window.location.origin;
  }

  // ============================================================================
  // QUEUE API METHODS
  // ============================================================================

  /**
   * Get current queue state from server
   */
  getQueue() {
    return this.get("/queue");
  }

  /**
   * Add tracks to the server queue
   */
  addToQueue(tracks, options = {}) {
    return this.post("/queue/add", { tracks, ...options });
  }

  /**
   * Remove a track from the queue
   */
  async removeFromQueue(trackId) {
    const response = await fetch(`${API_BASE}/queue/${trackId}`, {
      method: "DELETE",
      headers: this.getHeaders(),
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error(`Failed to remove from queue: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Clear the queue
   */
  clearQueue() {
    return this.post("/queue/clear");
  }

  /**
   * Clear completed items
   */
  clearCompleted() {
    return this.post("/queue/clear-completed");
  }

  /**
   * Clear failed items
   */
  clearFailed() {
    return this.post("/queue/clear-failed");
  }

  /**
   * Retry all failed items
   */
  retryAllFailed() {
    return this.post("/queue/retry-failed");
  }

  /**
   * Retry a single failed item
   */
  retryFailed(trackId) {
    return this.post(`/queue/retry/${trackId}`);
  }

  /**
   * Start queue processing (for manual mode)
   */
  startQueue() {
    return this.post("/queue/start");
  }

  /**
   * Stop queue processing
   */
  stopQueue() {
    return this.post("/queue/stop");
  }

  /**
   * Get queue settings
   */
  getQueueSettings() {
    return this.get("/queue/settings");
  }
}

export const api = new ApiClient();
