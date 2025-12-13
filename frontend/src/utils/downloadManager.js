/**
 * Download Manager - Server Queue Integration
 * 
 * This module manages the connection between the frontend and the server's
 * download queue. All download processing happens server-side.
 * 
 * Responsibilities:
 * - Sync queue state from server periodically
 * - Add tracks to server queue
 * - Control server queue (start/stop for manual mode)
 * - Provide queue operations (clear, retry, remove)
 */

import { api } from "../api/client";
import { useDownloadStore } from "../stores/downloadStore";
import { useToastStore } from "../stores/toastStore";

class DownloadManager {
  constructor() {
    this.initialized = false;
    this.syncInterval = null;
    this.syncIntervalMs = 1000; // 1 second for smooth progress updates
  }

  /**
   * Initialize the download manager
   * Starts periodic sync with server queue
   */
  async initialize() {
    if (this.initialized) {
      console.log("Download manager already initialized");
      return;
    }

    console.log("🔄 Initializing download manager...");
    this.initialized = true;

    // Start periodic sync with server queue
    this.startSync();

    // Get initial queue state
    await this.syncQueueState();

    console.log("✅ Download manager initialized - server handles queue processing");
  }

  /**
   * Start periodic sync with server
   */
  startSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
    }

    // Sync immediately
    this.syncQueueState();

    // Then sync periodically
    this.syncInterval = setInterval(() => {
      this.syncQueueState();
    }, this.syncIntervalMs);

    console.log(`🔄 Server queue sync started (every ${this.syncIntervalMs}ms)`);
  }

  /**
   * Stop periodic sync
   */
  stopSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
      console.log("🛑 Server queue sync stopped");
    }
  }

  /**
   * Sync queue state from server to local store
   */
  async syncQueueState() {
    try {
      const serverState = await api.getQueue();
      if (!serverState) return;

      const store = useDownloadStore.getState();

      // Transform server state to store format
      const queue = (serverState.queue || []).map(item => ({
        id: `q-${item.track_id}`,
        tidal_id: item.track_id,
        title: item.title || "Unknown Title",
        artist: item.artist || "Unknown Artist",
        album: item.album || "",
        track_number: item.track_number,
        cover: item.cover,
        progress: 0,
      }));

      const downloading = (serverState.active || []).map(item => ({
        id: `d-${item.track_id}`,
        tidal_id: item.track_id,
        title: item.title || "Unknown Title",
        artist: item.artist || "Unknown Artist",
        album: item.album || "",
        progress: item.progress || 0,
      }));

      const completed = (serverState.completed || []).map(item => ({
        id: `c-${item.track_id}`,
        tidal_id: item.track_id,
        title: item.title || "Unknown Title",
        artist: item.artist || "Unknown Artist",
        filename: item.filename,
      }));

      const failed = (serverState.failed || []).map(item => ({
        id: `f-${item.track_id}`,
        tidal_id: item.track_id,
        title: item.title || "Unknown Title",
        artist: item.artist || "Unknown Artist",
        error: item.error,
      }));

      // Update store with server state
      store.setServerQueueState({ queue, downloading, completed, failed });

      // Update settings from server
      if (serverState.settings) {
        store.setQueueSettings(serverState.settings);
      }
    } catch (error) {
      // Silently fail - connection issues shouldn't spam errors
      console.debug("Queue sync failed:", error.message);
    }
  }

  /**
   * Add tracks to the server queue
   * @param {Array} tracks - Array of track objects with tidal_id, title, artist, etc.
   */
  async addToServerQueue(tracks) {
    try {
      const { quality, organizationTemplate, groupCompilations, runBeets, embedLyrics } =
        useDownloadStore.getState();

      // Transform tracks to API format
      const formattedTracks = tracks.map(track => ({
        track_id: Number(track.tidal_id || track.id),
        title: String(track.title || "Unknown Title"),
        artist: String(track.artist || "Unknown Artist"),
        album: track.album || "",
        album_artist: track.album_artist || track.albumArtist || null, // Pass Album Artist
        album_id: track.album_id || null,
        track_number: track.track_number || track.trackNumber || null,
        cover: track.cover || null,
        quality: quality || "HIGH",
        target_format: null,
        bitrate_kbps: null,
        run_beets: runBeets || false,
        embed_lyrics: embedLyrics || false,
        organization_template: organizationTemplate || "{Artist}/{Album}/{TrackNumber} - {Title}",
        group_compilations: groupCompilations !== false,
        ...(track.tidal_track_id && { tidal_track_id: String(track.tidal_track_id) }),
        ...(track.tidal_artist_id && { tidal_artist_id: String(track.tidal_artist_id) }),
        ...(track.tidal_album_id && { tidal_album_id: String(track.tidal_album_id) }),
      }));

      const result = await api.addToQueue(formattedTracks);
      console.log(`✅ Added ${result.added} tracks to server queue (${result.skipped} skipped)`);

      // Refresh state
      await this.syncQueueState();

      return result;
    } catch (error) {
      console.error("Error adding to server queue:", error);
      useToastStore.getState().addToast(
        `Failed to add to queue: ${error.message}`,
        "error"
      );
      return { added: 0, skipped: tracks.length };
    }
  }

  /**
   * Remove a track from the queue
   */
  async removeFromQueue(trackId) {
    try {
      await api.removeFromQueue(trackId);
      await this.syncQueueState();
      return true;
    } catch (error) {
      console.error("Error removing from queue:", error);
      return false;
    }
  }

  /**
   * Clear the server queue
   */
  async clearQueue() {
    try {
      const result = await api.clearQueue();
      console.log(`Cleared ${result.cleared} items from queue`);
      await this.syncQueueState();
      return result.cleared;
    } catch (error) {
      console.error("Error clearing queue:", error);
      return 0;
    }
  }

  /**
   * Clear completed items
   */
  async clearCompleted() {
    try {
      const result = await api.clearCompleted();
      await this.syncQueueState();
      return result.cleared;
    } catch (error) {
      console.error("Error clearing completed:", error);
      return 0;
    }
  }

  /**
   * Clear failed items
   */
  async clearFailed() {
    try {
      const result = await api.clearFailed();
      await this.syncQueueState();
      return result.cleared;
    } catch (error) {
      console.error("Error clearing failed:", error);
      return 0;
    }
  }

  /**
   * Retry all failed downloads
   */
  async retryAllFailed() {
    try {
      const result = await api.retryAllFailed();
      console.log(`Retried ${result.retried} failed downloads`);
      await this.syncQueueState();
      return result.retried;
    } catch (error) {
      console.error("Error retrying failed:", error);
      return 0;
    }
  }

  /**
   * Retry a single failed download
   */
  async retryFailed(trackId) {
    try {
      const result = await api.retryFailed(trackId);
      await this.syncQueueState();
      return result.success;
    } catch (error) {
      console.error("Error retrying failed download:", error);
      return false;
    }
  }

  /**
   * Start queue processing on server (for manual mode)
   */
  async start() {
    try {
      console.log("🎵 Requesting server queue processing start...");
      const result = await api.startQueue();
      console.log("✅ Server queue started:", result.message);
      await this.syncQueueState();
    } catch (error) {
      console.error("Error starting server queue:", error);
    }
  }

  /**
   * Stop queue processing on server
   */
  async stop() {
    try {
      console.log("🛑 Requesting server queue processing stop...");
      const result = await api.stopQueue();
      console.log("✅ Server queue stopped:", result.message);
      await this.syncQueueState();
    } catch (error) {
      console.error("Error stopping server queue:", error);
    }
  }

  /**
   * Get queue settings from server
   */
  async getQueueSettings() {
    try {
      return await api.getQueueSettings();
    } catch (error) {
      console.error("Error getting queue settings:", error);
      return { max_concurrent: 3, auto_process: true };
    }
  }

  // Legacy method aliases for backwards compatibility
  startServerQueueSync(intervalMs = 3000) {
    this.syncIntervalMs = intervalMs;
    this.startSync();
  }

  stopServerQueueSync() {
    this.stopSync();
  }

  syncServerQueueToStore() {
    return this.syncQueueState();
  }
}

export const downloadManager = new DownloadManager();

// Auto-initialize on module load
if (typeof window !== "undefined") {
  window.addEventListener("load", () => {
    console.log("Auto-initializing download manager on page load");
    downloadManager.initialize();
  });
}
