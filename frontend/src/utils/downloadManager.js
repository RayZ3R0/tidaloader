import { api } from "../api/client";
import { useDownloadStore } from "../stores/downloadStore";

const DOWNLOAD_MODE = "server";
const API_BASE = "/api";

class DownloadManager {
  constructor() {
    this.isProcessing = false;
    this.activeDownloads = new Map();
  }

  async start() {
    if (this.isProcessing) {
      console.log("Download manager already running");
      return;
    }

    this.isProcessing = true;
    console.log("🎵 Download manager started");

    while (this.isProcessing) {
      const state = useDownloadStore.getState();
      const { queue, downloading, maxConcurrent } = state;

      if (downloading.length < maxConcurrent && queue.length > 0) {
        const track = queue[0];
        await this.downloadTrack(track);
      } else if (downloading.length === 0 && queue.length === 0) {
        await this.sleep(1000);
      } else {
        await this.sleep(500);
      }
    }

    console.log("🛑 Download manager stopped");
  }

  stop() {
    this.isProcessing = false;
    this.activeDownloads.forEach((controller) => {
      controller.abort();
    });
    this.activeDownloads.clear();
  }

  async downloadTrack(track) {
    if (DOWNLOAD_MODE === "server") {
      return this.downloadTrackServerSide(track);
    } else {
      return this.downloadTrackClientSide(track);
    }
  }

  /**
   * Download track server-side (saves to backend/downloads/ or custom path)
   */
  async downloadTrackServerSide(track) {
    const {
      startDownload,
      completeDownload,
      failDownload,
      updateProgress,
      quality,
    } = useDownloadStore.getState();

    startDownload(track.id);

    const trackId = track.tidal_id || track.id;
    if (!trackId) {
      failDownload(track.id, "Track ID is missing");
      return;
    }

    let eventSource = null;
    let downloadCompleted = false;

    try {
      console.log(`⬇️ Downloading (server): ${track.artist} - ${track.title}`);
      console.log(`  Track ID: ${trackId}`);
      console.log(`  Quality: ${quality}`);

      // Create a promise that resolves when download completes
      const downloadCompletionPromise = new Promise((resolve, reject) => {
        // Connect to progress stream
        eventSource = new EventSource(
          `${API_BASE}/download/progress/${trackId}`
        );

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.progress !== undefined) {
              updateProgress(track.id, data.progress);
              console.log(
                `  Progress: ${data.progress}% (${
                  data.status || "downloading"
                })`
              );

              // Check if download is complete
              if (data.status === "completed" || data.progress >= 100) {
                downloadCompleted = true;
                console.log("  Download completed!");
                eventSource?.close();
                resolve();
              }
            }

            // Handle not found status
            if (data.status === "not_found") {
              console.error("  Download progress not found");
              reject(new Error("Download progress not found"));
            }

            // Handle failed status
            if (data.status === "failed") {
              console.error("  Download failed on server");
              reject(new Error("Download failed on server"));
            }
          } catch (error) {
            console.error("Failed to parse progress event:", error);
          }
        };

        eventSource.onerror = (error) => {
          console.error("SSE connection error:", error);

          // Don't immediately fail - might just be reconnecting
          if (!downloadCompleted) {
            console.log(
              "  SSE connection lost, but download may still be in progress..."
            );
            // Give it a chance to reconnect
            setTimeout(() => {
              if (!downloadCompleted) {
                eventSource?.close();
                reject(new Error("SSE connection failed"));
              }
            }, 5000);
          } else {
            eventSource?.close();
          }
        };

        // Timeout after 5 minutes
        setTimeout(() => {
          if (!downloadCompleted) {
            console.error("  Download timeout (5 minutes)");
            eventSource?.close();
            reject(new Error("Download timeout (5 minutes)"));
          }
        }, 300000);
      });

      // Give SSE connection time to establish
      await this.sleep(500);

      // Start the download
      const requestBody = {
        track_id: Number(trackId),
        artist: String(track.artist || "Unknown Artist"),
        title: String(track.title || "Unknown Title"),
        quality: String(quality),
      };

      console.log("Starting download...");

      const response = await fetch(`${API_BASE}/download/track`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      console.log(`Response status: ${response.status} ${response.statusText}`);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Error response body:", errorText);

        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { detail: errorText || response.statusText };
        }

        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      console.log("Download started:", result);

      // Wait for download to complete via SSE
      if (result.status === "downloading") {
        console.log("  Waiting for download to complete...");
        await downloadCompletionPromise;
      } else if (result.status === "exists") {
        // File already exists, mark as complete immediately
        downloadCompleted = true;
      }

      completeDownload(track.id, result.filename);
      console.log(`✓ Downloaded: ${result.filename}`);
      if (result.path) {
        console.log(`  Location: ${result.path}`);
      }
    } catch (error) {
      console.error(`✗ Download failed: ${track.title}`, error);
      failDownload(track.id, error.message);
    } finally {
      if (eventSource) {
        eventSource.close();
      }
    }

    await this.sleep(1000);
  }

  /**
   * Download track client-side (browser Downloads folder)
   */
  async downloadTrackClientSide(track) {
    const {
      startDownload,
      completeDownload,
      failDownload,
      updateProgress,
      quality,
    } = useDownloadStore.getState();

    startDownload(track.id);

    const controller = new AbortController();
    this.activeDownloads.set(track.id, controller);

    try {
      console.log(`⬇️ Downloading: ${track.artist} - ${track.title}`);

      const streamData = await api.get(`/download/stream/${track.tidal_id}`, {
        quality,
      });

      if (!streamData.stream_url) {
        throw new Error("No stream URL returned");
      }

      const response = await fetch(streamData.stream_url, {
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const totalBytes = parseInt(
        response.headers.get("content-length") || "0"
      );
      let receivedBytes = 0;

      const reader = response.body.getReader();
      const chunks = [];

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        chunks.push(value);
        receivedBytes += value.length;

        if (totalBytes > 0) {
          const progress = Math.round((receivedBytes / totalBytes) * 100);
          updateProgress(track.id, progress);
        }
      }

      const blob = new Blob(chunks, {
        type: response.headers.get("content-type") || "audio/flac",
      });

      const filename = this.sanitizeFilename(
        `${track.artist} - ${track.title}.flac`
      );

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      completeDownload(track.id, filename);
      console.log(
        `✓ Downloaded: ${filename} (${(receivedBytes / 1024 / 1024).toFixed(
          2
        )} MB)`
      );
    } catch (error) {
      if (error.name === "AbortError") {
        console.log(`⏹️ Download cancelled: ${track.title}`);
        failDownload(track.id, "Download cancelled");
      } else {
        console.error(`✗ Download failed: ${track.title}`, error);
        failDownload(track.id, error.message);
      }
    } finally {
      this.activeDownloads.delete(track.id);
    }

    await this.sleep(1000);
  }

  sanitizeFilename(filename) {
    const invalid = /[<>:"/\\|?*]/g;
    return filename.replace(invalid, "_").trim();
  }

  sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

export const downloadManager = new DownloadManager();
