import { h, Fragment } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../../api/client";
import { useToastStore } from "../../stores/toastStore";

function PlaylistCoverImage({ cover, title }) {
  // Spotify covers are just URLs usually, but let's keep it safe
  const src = cover || null;
  if (!src)
    return (
      <div class="w-full aspect-square bg-surface-alt rounded-lg mb-2 shadow-sm flex items-center justify-center text-text-muted">
        <svg
          class="w-12 h-12 opacity-50"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
          />
        </svg>
      </div>
    );

  return (
    <img
      src={src}
      alt={title}
      loading="lazy"
      class="w-full aspect-square object-cover rounded-lg mb-2 shadow-sm"
    />
  );
}

const formatDuration = (ms) => {
  if (!ms) return "--:--";
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
};

function PreviewModal({ playlist, onClose }) {
  const [loading, setLoading] = useState(true);
  const [tracks, setTracks] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadTracks = async () => {
      try {
        const result = await api.getSpotifyPlaylist(playlist.id);
        setTracks(result.items || []);
      } catch (e) {
        console.error("Preview fetch error:", e);
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    loadTracks();
  }, [playlist]);

  return (
    <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 animate-fadeIn">
      <div class="bg-surface card w-full max-w-2xl flex flex-col max-h-[85vh] shadow-2xl rounded-xl">
        <div class="p-6 border-b border-border flex items-center gap-4 bg-surface rounded-t-xl">
          {playlist.image && (
            <img
              src={playlist.image}
              class="w-16 h-16 rounded-md shadow-sm object-cover"
              alt={playlist.name}
            />
          )}
          <div class="flex-1">
            <h2 class="text-xl font-bold text-text">{playlist.name}</h2>
            <p class="text-text-muted text-sm">
              {playlist.trackCount || tracks.length || "..."} tracks{" "}
              {playlist.owner ? `• by ${playlist.owner}` : ""}
            </p>
          </div>
          <button onClick={onClose} class="text-text-muted hover:text-text p-2">
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-0">
          {loading ? (
            <div class="flex flex-col items-center justify-center py-12 gap-3 text-primary">
              <div class="w-8 h-8 border-2 border-current border-t-transparent rounded-full animate-spin" />
              <p class="text-sm font-medium">Fetching tracks from Spotify...</p>
            </div>
          ) : error ? (
            <div class="p-8 text-center text-red-500">
              <p>Failed to load preview: {error}</p>
            </div>
          ) : (
            <div class="divide-y divide-border-light">
              {tracks.map((track, i) => (
                <div
                  key={i}
                  class="px-6 py-3 hover:bg-surface-alt/50 flex items-center gap-4 group"
                >
                  <span class="text-text-muted text-sm w-6 text-right tabular-nums">
                    {i + 1}
                  </span>
                  <div class="flex-1 min-w-0">
                    <p class="text-text font-medium text-sm truncate">
                      {track.title}
                    </p>
                    <p class="text-text-muted text-xs truncate">
                      {track.artist} {track.album ? `• ${track.album}` : ""}
                    </p>
                  </div>
                  <span class="text-text-muted text-xs tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                    {formatDuration(track.duration_ms || track.duration * 1000)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const MonitorModal = ({ playlist, onClose, onAdd }) => {
  const [frequency, setFrequency] = useState("manual");
  const [quality, setQuality] = useState("LOSSLESS");
  const [usePlaylistFolder, setUsePlaylistFolder] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const addToast = useToastStore((state) => state.addToast);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onAdd({
        uuid: playlist.id,
        name: playlist.name,
        frequency,
        quality,
        source: "spotify",
        extra_config: {
          spotify_id: playlist.id,
          image_url: playlist.image,
        },
        use_playlist_folder: usePlaylistFolder,
      });
      onClose();
    } catch (e) {
      console.error(e);
      // Error toast handled by caller
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="bg-surface card p-6 w-full max-w-md space-y-4 animate-scale-in">
        <h2 class="text-xl font-bold text-text">Sync Playlist</h2>
        <p class="text-text-muted">
          Setup synchronization for{" "}
          <span class="text-text font-medium">{playlist.name}</span>. Currently
          supports generating M3U8 playlists.
        </p>

        <form onSubmit={handleSubmit} class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-text mb-1">
              Update Frequency
            </label>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              class="input-field w-full"
            >
              <option value="manual">Manual (One-time)</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
            <p class="text-xs text-text-muted mt-1">
              {frequency === "manual"
                ? "Playlist will only be updated when you click 'Sync Now'."
                : "Playlist will be automatically updated in the background."}
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-text mb-1">
              Quality
            </label>
            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              class="input-field w-full"
            >
              <option value="LOW">Low (96kbps AAC)</option>
              <option value="HIGH">High (320kbps AAC)</option>
              <option value="LOSSLESS">Lossless (FLAC 16bit)</option>
              <option value="HI_RES">Hi-Res (FLAC 24bit)</option>
            </select>
          </div>

          <div>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={usePlaylistFolder}
                onChange={(e) => setUsePlaylistFolder(e.target.checked)}
                class="rounded border-border text-primary focus:ring-primary h-4 w-4"
              />
              <span class="text-sm font-medium text-text">
                Download tracks to playlist folder
              </span>
            </label>
            <p class="text-xs text-text-muted mt-1 ml-6">
              Creates a standalone folder "{playlist.name}" containing all
              tracks. Useful for keeping files together, but duplicates tracks
              if they already exist in library.
            </p>
          </div>

          <div class="flex gap-3 justify-end mt-6">
            <button
              type="button"
              onClick={onClose}
              class="px-4 py-2 text-text-muted hover:text-text hover:bg-surface-alt rounded-lg"
              disabled={submitting}
            >
              Cancel
            </button>
            <button type="submit" class="btn-primary" disabled={submitting}>
              {submitting ? "Starting..." : "Start Sync"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

function SyncProgressModal({ progressId, onClose }) {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("active"); // active, complete, error
  const [progress, setProgress] = useState({ current: 0, total: 0 });

  const [pollError, setPollError] = useState(false);

  useEffect(() => {
    let isMounted = true;
    // console.log("[DEBUG] VERSION: Polling Loading...");

    const poll = async () => {
      try {
        // Polling using authenticated client
        console.log(`[POLL] Polling ID: ${progressId}`);
        const data = await api.getSpotifySyncProgress(progressId);
        console.log("[POLL] Data:", data);

        if (isMounted) {
          setPollError(false);
          // Update state from backend
          if (data.status) setStatus(data.status);

          // Messages
          if (data.messages) setMessages(data.messages);

          // Progress
          if (data.current !== undefined) {
            setProgress({
              current: data.current || 0,
              total: data.total || 0,
              matches: data.matches || 0,
            });
          }
        }
      } catch (e) {
        console.warn("Polling error", e);
        if (isMounted) setPollError(true);
      }
    };

    const interval = setInterval(poll, 1000);
    poll();

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [progressId]);

  const percent =
    progress.total > 0
      ? Math.round((progress.current / progress.total) * 100)
      : 0;

  return (
    <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
      <div class="bg-surface card w-full max-w-lg shadow-2xl rounded-xl flex flex-col max-h-[80vh]">
        <div class="p-6 border-b border-border">
          <h3 class="text-xl font-bold text-text">
            Importing Playlist (Rapid Sync)
          </h3>
          <p class="text-text-muted text-sm">
            Synchronizing tracks from Spotify...
          </p>
        </div>

        <div class="p-6 flex-1 overflow-y-auto space-y-4">
          {/* Progress Bar */}
          <div class="space-y-2">
            <div class="flex justify-between text-sm text-text-muted">
              <span>Processing Tracks</span>
              <span>
                {percent}% ({progress.current}/{progress.total})
              </span>
            </div>
            <div class="h-2 bg-surface-alt rounded-full overflow-hidden">
              <div
                class="h-full bg-primary transition-all duration-300"
                style={{ width: `${percent}%` }}
              />
            </div>

            {/* Validation Stats */}
            <div class="flex items-center justify-between text-xs mt-2 px-1">
              <div class="text-text-muted">
                Connection:{" "}
                <span
                  class={
                    status === "active" ? "text-green-400" : "text-text-muted"
                  }
                >
                  {status === "active" ? "Connected" : "Closed"}
                </span>
              </div>
              {progress.total > 0 && (
                <div class="font-medium text-text">
                  Matches Found:{" "}
                  <span class="text-green-400">{progress.matches || 0}</span>{" "}
                  <span class="text-text-muted">
                    / {progress.current} analyzed
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Log */}
          <div class="bg-black/20 rounded-lg p-3 h-48 overflow-y-auto font-mono text-xs space-y-1">
            {pollError && (
              <div class="p-2 bg-red-500/20 text-red-500 border border-red-500/50 rounded mb-2">
                <strong>Connection Error:</strong> {pollError.toString()}
              </div>
            )}
            {messages.length === 0 && !pollError && (
              <span class="text-text-muted italic">Waiting for updates...</span>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                class={`
                                ${msg.type === "error" ? "text-red-400" : ""}
                                ${msg.type === "complete" ? "text-green-400" : ""}
                                ${msg.type === "validating" ? "text-text-muted" : "text-text"}
                            `}
              >
                <span class="opacity-50 mr-2">
                  [{new Date(msg.timestamp * 1000).toLocaleTimeString()}]
                </span>
                {msg.text}
              </div>
            ))}
          </div>
        </div>

        <div class="p-6 border-t border-border flex justify-end gap-3">
          {/* Always show both buttons. Confirm is disabled until ready. */}
          <button
            onClick={() => onClose(false, progressId)} // False = Cancel/Delete
            class="px-4 py-2 rounded-lg font-medium transition-colors bg-red-500/10 text-red-500 hover:bg-red-500/20"
          >
            {/* If complete/synced, offer Close. If analyzing/waiting, offer Cancel & Delete. */}
            {status === "complete" || status === "waiting_confirmation"
              ? "Cancel & Delete"
              : "Cancel"}
          </button>

          <button
            onClick={() => onClose(true, progressId)} // True = Confirm
            disabled={status === "active" || status === "error"}
            class={`px-4 py-2 rounded-lg font-medium transition-colors ${
              status === "active" || status === "error"
                ? "bg-surface-alt text-text-muted cursor-not-allowed opacity-50"
                : "bg-primary text-white hover:bg-primary-dark"
            }`}
          >
            {status === "active" ? "Analyzing..." : "Confirm Sync"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function SpotifySearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [previewPlaylist, setPreviewPlaylist] = useState(null);
  const [officialOnly, setOfficialOnly] = useState(false);
  const [monitoredUuids, setMonitoredUuids] = useState(new Set());

  // Progress Modal State
  const [progressContext, setProgressContext] = useState(null); // { id: uuid }

  const addToast = useToastStore((state) => state.addToast);

  // Fetch monitored playlists on mount to check status
  useEffect(() => {
    api
      .getMonitoredPlaylists()
      .then((list) => {
        setMonitoredUuids(new Set(list.map((p) => p.uuid)));
      })
      .catch((err) => console.error("Failed to load monitored status", err));
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const data = await api.searchSpotifyPlaylists(query);
      setResults(data.items || []);
      if ((data.items || []).length === 0) {
        addToast("No playlists found", "info");
      }
    } catch (err) {
      setError(err.message);
      addToast(`Search failed: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (config) => {
    // Simple manual UUID generator to avoid crypto.randomUUID() issues in non-secure contexts
    const generateId = () => {
      return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
        /[xy]/g,
        function (c) {
          var r = (Math.random() * 16) | 0,
            v = c == "x" ? r : (r & 0x3) | 0x8;
          return v.toString(16);
        },
      );
    };

    const progressId = generateId();

    // Open modal immediately with UUID
    setProgressContext({ id: progressId, uuid: config.uuid });

    try {
      await api.monitorPlaylist(
        config.uuid,
        config.name,
        config.frequency,
        config.quality,
        config.source,
        config.extra_config,
        config.use_playlist_folder,
        progressId,
        true, // skipDownload = true (Analyze only)
      );
      addToast(`Started monitoring "${config.name}"`, "success");
      setMonitoredUuids((prev) => new Set(prev).add(config.uuid));

      // Success! The SyncProgressModal stays open until completion/user close.
    } catch (e) {
      console.error("Monitor playlist failed", e);
      addToast(`Failed to add playlist: ${e.message}`, "error");
      setProgressContext(null); // Close popup on immediate failure
      throw e; // Propagate to MonitorModal to reset loading state
    }
  };

  const displayedResults = officialOnly
    ? results.filter((p) => p.owner === "Spotify")
    : results;

  return (
    <div class="space-y-4 sm:space-y-6">
      <div class="flex flex-col gap-3">
        <div class="flex flex-col sm:flex-row gap-2 sm:gap-3">
          <input
            type="text"
            value={query}
            onInput={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search Spotify Playlists..."
            class="input-field flex-1 text-sm"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            class="btn-primary flex items-center justify-center gap-2 w-full sm:w-auto text-sm"
          >
            {loading ? (
              <svg class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                ></circle>
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
            ) : (
              "Search"
            )}
          </button>
        </div>

        <div class="flex items-center justify-between sm:justify-start gap-3 bg-surface-alt/50 px-3 py-2 rounded-lg border border-border-light">
          <label
            class="text-xs sm:text-sm font-medium text-text cursor-pointer select-none"
            onClick={() => setOfficialOnly(!officialOnly)}
          >
            Official Spotify Playlists only
          </label>
          <label class="relative inline-flex items-center cursor-pointer flex-shrink-0">
            <input
              type="checkbox"
              checked={officialOnly}
              onChange={(e) => setOfficialOnly(e.target.checked)}
              class="sr-only peer"
            />
            <div class="w-9 h-5 sm:w-11 sm:h-6 bg-surface border border-border peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 sm:after:h-5 sm:after:w-5 after:transition-all peer-checked:bg-primary"></div>
          </label>
        </div>
      </div>

      {error && (
        <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-500 text-sm">
          {error}
        </div>
      )}

      <div class="grid grid-cols-2 xs:grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 sm:gap-4">
        {displayedResults.map((playlist) => (
          <div
            key={playlist.id}
            class="card-hover p-3 flex flex-col gap-2 relative group"
          >
            <div
              class="relative cursor-pointer hover:opacity-90 transition-opacity"
              onClick={() => setPreviewPlaylist(playlist)}
            >
              <PlaylistCoverImage
                cover={playlist.image}
                title={playlist.name}
              />

              {monitoredUuids.has(playlist.id) && (
                <div class="absolute top-2 right-2 bg-green-500 text-white rounded-full p-1 shadow-md z-10">
                  <svg
                    class="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
              )}
            </div>

            <div class="flex-1 min-w-0">
              <h3
                class="font-semibold text-text line-clamp-2 leading-tight"
                title={playlist.name}
              >
                {playlist.name}
              </h3>
              <p class="text-xs text-text-muted truncate mt-1">
                By {playlist.owner}
              </p>
              <p class="text-xs text-text-muted mt-0.5">
                {playlist.track_count} tracks
              </p>
            </div>

            {monitoredUuids.has(playlist.id) ? (
              <button
                disabled
                class="btn-surface w-full mt-2 text-sm py-1.5 opacity-75 cursor-not-allowed border border-border"
              >
                Already Synced
              </button>
            ) : (
              <button
                onClick={() => setSelectedPlaylist(playlist)}
                class="btn-primary w-full mt-2 text-sm py-1.5"
              >
                Sync Playlist
              </button>
            )}
          </div>
        ))}
      </div>

      {!loading &&
        displayedResults.length === 0 &&
        results.length > 0 &&
        query && (
          <div class="text-center py-12 text-text-muted">
            No Official Spotify playlists found. Try unchecking the filter.
          </div>
        )}

      {selectedPlaylist && (
        <MonitorModal
          playlist={selectedPlaylist}
          onClose={() => setSelectedPlaylist(null)}
          onAdd={handleAdd}
        />
      )}

      {previewPlaylist && (
        <PreviewModal
          playlist={previewPlaylist}
          onClose={() => setPreviewPlaylist(null)}
        />
      )}

      {progressContext && progressContext.id && (
        <SyncProgressModal
          progressId={progressContext.id}
          onClose={async (confirmed, explicitId) => {
            const uuid = progressContext.uuid;
            // Use explicitId passed back from modal, or fallback to context.id
            const pId = explicitId || progressContext.id;

            setProgressContext(null);

            if (confirmed) {
              try {
                // Trigger actual download
                // Pass pId to use cached analysis results
                await api.syncPlaylist(uuid, pId);
                addToast(
                  "Sync confirmed. Downloading tracks in background.",
                  "success",
                );
              } catch (e) {
                console.error(e);
                addToast("Failed to start sync: " + e.message, "error");
              }
            } else {
              // Cancelled - delete the monitored playlist
              try {
                await api.removeMonitoredPlaylist(uuid);
                addToast("Import cancelled.", "info");
                setMonitoredUuids((prev) => {
                  const next = new Set(prev);
                  next.delete(uuid);
                  return next;
                });
              } catch (e) {
                console.error(e);
              }
            }
          }}
        />
      )}
    </div>
  );
}
