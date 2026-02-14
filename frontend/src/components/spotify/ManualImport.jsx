import { h } from "preact";
import { useState, useRef, useEffect } from "preact/hooks";
import { api } from "../../api/client";
import { downloadManager } from "../../utils/downloadManager";
import { useToastStore } from "../../stores/toastStore";

const ModernCheckbox = ({ checked, onChange, disabled }) => (
  <div
    onClick={!disabled ? onChange : undefined}
    class={`relative flex items-center justify-center w-5 h-5 rounded-[6px] border transition-all duration-300 ease-out cursor-pointer ${
      disabled ? "opacity-50 cursor-not-allowed" : "hover:border-primary/50"
    } ${
      checked
        ? "bg-primary border-primary shadow-[0_0_10px_rgba(var(--color-primary),0.3)]"
        : "bg-surface-alt border-gray-600"
    }`}
  >
    <svg
      class={`w-3.5 h-3.5 text-black transition-all duration-300 ease-[cubic-bezier(0.175,0.885,0.32,1.275)] ${
        checked ? "scale-100 opacity-100" : "scale-50 opacity-0"
      }`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      stroke-width="4"
    >
      <path stroke-linecap="round" stroke-linejoin="round" d="M4 12l5 5L20 7" />
    </svg>
  </div>
);

export function ManualImport() {
  const [playlistUrl, setPlaylistUrl] = useState("");
  const [playlistName, setPlaylistName] = useState("");
  const [loading, setLoading] = useState(false);
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(new Set()); // Set of indices (numbers)
  const [error, setError] = useState(null);
  const [progressLogs, setProgressLogs] = useState([]);
  const logsEndRef = useRef(null);
  const [generatingM3U8, setGeneratingM3U8] = useState(false);

  // Track status map: { idx: 'idle' | 'validating' | 'success' | 'error' }
  const [trackStatuses, setTrackStatuses] = useState({});

  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLogs]);

  const handleFetch = async () => {
    if (!playlistUrl.trim()) {
      setError("Please enter a Spotify playlist URL");
      return;
    }

    setLoading(true);
    setError(null);
    setTracks([]);
    setSelected(new Set());
    setProgressLogs([]);
    setTrackStatuses({});

    // polling variables
    let pollInterval;
    let isComplete = false;

    try {
      const { progress_id } = await api.generateSpotifyPlaylist(
        playlistUrl.trim(),
        false,
      ); // false = don't validate yet

      const poll = async () => {
        if (isComplete) return;

        try {
          const data = await api.getSpotifySyncProgress(progress_id);
          // console.log("[POLL]", data);

          if (data.status === "error") {
            setError(data.message || "Unknown error occurred");
            setLoading(false);
            isComplete = true;
            clearInterval(pollInterval);
            addToast(`Failed to process playlist: ${data.message}`, "error");
            return;
          }

          // Append logs
          if (data.messages && data.messages.length > 0) {
            // In a real app we might want to deduplicate based on message ID or index/timestamp
            // But here we rely on the backend state providing the full history or we just take the last few?
            // Actually getSpotifySyncProgress likely returns ALL messages so we just replace state
            // Or if it returns partial, we append. Based on SyncProgressModal it seems it might return all.
            // Let's assume it returns { messages: [...] } containing everything so far or relevant ones.
            // Checking SyncProgressModal logic: it does `setMessages(data.messages)` replacing them.
            // The backend `get_spotify_progress` returns `state` object which has a `messages` list.
            // So we should replace local state to match backend state.

            // Map backend message format to our format if needed, or just use as is.
            // Backend: { text: "...", type: "...", timestamp: ... }
            // Frontend previous: { type, message: data.message, timestamp }

            const newLogs = (data.messages || []).map((msg) => ({
              type: msg.type || "info",
              message: msg.text,
              timestamp: msg.timestamp
                ? new Date(msg.timestamp * 1000).toISOString()
                : new Date().toISOString(),
            }));

            setProgressLogs(newLogs);
          }

          if (
            data.status === "complete" ||
            data.status === "waiting_confirmation"
          ) {
            // Note: "waiting_confirmation" usually means "ready" in the other flow,
            // here it effectively means "fetched" so we can show tracks.

            // Backend populates `tracks` in state when complete?
            // Let's check `api/services/spotify.py`.
            // `process_spotify_playlist` updates state['tracks'] at the end.

            if (data.tracks && data.tracks.length > 0) {
              setTracks(data.tracks);
              setLoading(false);
              isComplete = true;
              clearInterval(pollInterval);
              addToast(
                `Fetched ${data.tracks.length} tracks. Check availability before downloading.`,
                "success",
              );
            } else if (
              data.status === "complete" &&
              (!data.tracks || data.tracks.length === 0)
            ) {
              // Complete but empty?
              setLoading(false);
              isComplete = true;
              clearInterval(pollInterval);
              addToast("Playlist appeared to be empty.", "info");
            }
          }
        } catch (e) {
          console.warn("Poll error", e);
          // Don't stop polling on single error, could be transient
        }
      };

      // Start polling
      pollInterval = setInterval(poll, 1000);
      poll(); // initial call

      // Cleanup function if component unmounts?
      // We can't easily return cleanup from here, but we can rely on `isComplete` flag and standard component unmounting if needed.
      // But since this is inside a function, we need a way to clear typical ref for cleanup if unmount happens while loading.
      // For now, simple logic is fine.
    } catch (err) {
      setError(err.message);
      setLoading(false);
      if (pollInterval) clearInterval(pollInterval);
      addToast(`Failed to start process: ${err.message}`, "error");
    }
  };

  const validateTrack = async (idx) => {
    // We get the track from current state just to initiate the request
    // This assumes track content (Title/Artist) is immutable
    const track = tracks[idx];
    if (!track) return;

    setTrackStatuses((prev) => ({ ...prev, [idx]: "validating" }));

    try {
      const result = await api.validateListenBrainzTrack(track);

      // Functional update to avoid stale closures
      setTracks((prevTracks) => {
        const newTracks = [...prevTracks];
        newTracks[idx] = result;
        return newTracks;
      });

      if (result.tidal_exists) {
        setTrackStatuses((prev) => ({ ...prev, [idx]: "success" }));
      } else {
        setTrackStatuses((prev) => ({ ...prev, [idx]: "error" }));
      }
      return result;
    } catch (e) {
      console.error("Validation failed", e);
      setTrackStatuses((prev) => ({ ...prev, [idx]: "error" }));
      return track;
    }
  };

  const validateAll = async () => {
    const indicesToValidate = tracks
      .map((_, i) => i)
      .filter((i) => !tracks[i].tidal_exists && trackStatuses[i] !== "error");

    const concurrency = 3;
    for (let i = 0; i < indicesToValidate.length; i += concurrency) {
      const batch = indicesToValidate.slice(i, i + concurrency);
      await Promise.all(batch.map((idx) => validateTrack(idx)));
    }
  };

  const validateSelected = async () => {
    const indicesToValidate = Array.from(selected).filter(
      (i) => !tracks[i].tidal_exists && trackStatuses[i] !== "error",
    );

    // Sort indices to process in order (optional but nicer)
    indicesToValidate.sort((a, b) => a - b);

    const concurrency = 3;
    for (let i = 0; i < indicesToValidate.length; i += concurrency) {
      const batch = indicesToValidate.slice(i, i + concurrency);
      await Promise.all(batch.map((idx) => validateTrack(idx)));
    }
  };

  // Toggle selection by INDEX now
  const toggleTrack = (idx) => {
    const newSelected = new Set(selected);
    if (newSelected.has(idx)) {
      newSelected.delete(idx);
    } else {
      newSelected.add(idx);
    }
    setSelected(newSelected);
  };

  const toggleAll = () => {
    if (selected.size === tracks.length) {
      setSelected(new Set());
    } else {
      // Select all indices
      const allIndices = new Set(tracks.map((_, i) => i));
      setSelected(allIndices);
    }
  };

  const handleDownloadSingle = async (idx) => {
    let track = tracks[idx]; // Initial state

    if (!track.tidal_exists) {
      // Result from validateTrack will be the NEW track object
      track = await validateTrack(idx);
    }

    if (track && track.tidal_exists) {
      const trackToDl = {
        ...track,
        tidal_track_id: track.tidal_id,
        tidal_artist_id: track.tidal_artist_id,
        tidal_album_id: track.tidal_album_id,
        cover: track.cover,
      };
      downloadManager.addToServerQueue([trackToDl]);
      addToast(`Added "${track.title}" to queue`, "success");
    } else {
      addToast(
        `Could not find "${track ? track.title : "track"}" on Tidal`,
        "error",
      );
    }
  };

  const handleDownloadSelected = () => {
    // Only download valid ones from selection
    const selectedTracks = Array.from(selected)
      .map((idx) => tracks[idx])
      .filter((t) => t && t.tidal_exists)
      .map((t) => ({
        ...t,
        tidal_track_id: t.tidal_id,
        tidal_artist_id: t.tidal_artist_id,
        tidal_album_id: t.tidal_album_id,
        cover: t.cover,
      }));

    if (selectedTracks.length === 0) {
      if (selected.size > 0) {
        addToast(
          "None of the selected tracks are validated yet. Please check them first.",
          "error",
        );
      }
      return;
    }

    downloadManager.addToServerQueue(selectedTracks).then((result) => {
      addToast(`Added ${result.added} tracks to download queue`, "success");
    });
  };

  const handleGenerateM3U8 = async () => {
    const validatedTracks = tracks.filter((t) => t.tidal_exists && t.tidal_id);

    if (validatedTracks.length === 0) {
      addToast(
        "No validated tracks found. Please check tracks on Tidal first.",
        "error",
      );
      return;
    }

    if (!playlistName.trim()) {
      addToast("Please enter a playlist name", "error");
      return;
    }

    setGeneratingM3U8(true);
    try {
      const result = await api.generateSpotifyM3U8(
        playlistName.trim(),
        validatedTracks,
      );
      addToast(
        `Playlist created: ${result.included_count} tracks included, ${result.skipped_count} not yet downloaded`,
        "success",
      );
    } catch (e) {
      addToast(`Failed to generate playlist: ${e.message}`, "error");
    } finally {
      setGeneratingM3U8(false);
    }
  };

  return (
    <div class="space-y-4 sm:space-y-6">
      <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 sm:gap-4">
        <div class="sm:col-span-3">
          <label class="block text-xs font-semibold text-text-muted mb-1.5 uppercase tracking-wider">
            Spotify Playlist URL
          </label>
          <input
            type="text"
            value={playlistUrl}
            onInput={(e) => setPlaylistUrl(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter" && !loading && playlistUrl.trim()) {
                handleFetch();
              }
            }}
            placeholder="https://open.spotify.com/playlist/..."
            disabled={loading}
            class="input-field w-full h-[42px] text-sm"
          />
        </div>

        <div class="sm:col-span-1 flex items-end">
          <button
            onClick={handleFetch}
            disabled={loading || !playlistUrl.trim()}
            class="btn-primary w-full h-[42px] flex items-center justify-center gap-2 text-sm"
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
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z" />
              </svg>
            )}
            Fetch Playlist
          </button>
        </div>
      </div>

      {loading && (
        <div class="p-4 bg-surface-alt border border-border-light rounded-lg">
          <div class="flex items-center gap-3 text-text-muted">
            <svg
              class="animate-spin h-5 w-5 text-primary"
              fill="none"
              viewBox="0 0 24 24"
            >
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
            <span>Fetching playlist from Spotify...</span>
          </div>
          {progressLogs.length > 0 && (
            <div class="mt-2 text-xs font-mono text-text-muted max-h-32 overflow-y-auto">
              {progressLogs.slice(-1)[0].message}
            </div>
          )}
        </div>
      )}

      {error && (
        <div class="p-4 bg-red-500/10 border border-red-500/20 rounded-lg animate-fadeIn">
          <p class="text-sm text-red-500 flex items-center gap-2">
            <svg
              class="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            {error}
          </p>
        </div>
      )}

      {tracks.length > 0 && (
        <div class="space-y-4 animate-fadeIn">
          {/* Playlist Name & M3U8 Generation */}
          <div class="p-4 bg-surface-alt/50 border border-border-light rounded-lg">
            <div class="flex flex-col sm:flex-row sm:items-end gap-3">
              <div class="flex-1">
                <label class="block text-xs font-semibold text-text-muted mb-1.5 uppercase tracking-wider">
                  Playlist Name (for M3U8)
                </label>
                <input
                  type="text"
                  value={playlistName}
                  onInput={(e) => setPlaylistName(e.target.value)}
                  placeholder="My Spotify Playlist"
                  class="input-field w-full h-[38px]"
                />
              </div>
              <button
                onClick={handleGenerateM3U8}
                disabled={
                  generatingM3U8 ||
                  !playlistName.trim() ||
                  tracks.filter((t) => t.tidal_exists).length === 0
                }
                class="btn-surface h-[38px] px-4 text-sm flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
                title="Generate M3U8 playlist for Navidrome/Jellyfin"
              >
                {generatingM3U8 ? (
                  <svg
                    class="animate-spin h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
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
                  <svg
                    class="w-4 h-4"
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
                )}
                Generate M3U8
              </button>
            </div>
            <p class="text-xs text-text-muted mt-2">
              Only validated tracks that are already downloaded will be included
              in the playlist.
            </p>
          </div>

          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-border-light">
            <div class="flex items-center gap-3">
              <h3 class="text-lg font-bold text-text">Results</h3>
              <span class="px-2 py-0.5 rounded-full bg-surface-alt border border-border-light text-xs font-mono text-text-muted">
                {tracks.filter((t) => t.tidal_exists).length}/{tracks.length}{" "}
                MATCHED
              </span>
            </div>

            <div class="flex items-center gap-3">
              <button
                onClick={validateAll}
                disabled={loading}
                class="text-xs font-medium text-primary hover:text-primary-light transition-colors uppercase tracking-wider flex items-center gap-1"
              >
                <svg
                  class="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Check All
              </button>

              {selected.size > 0 &&
                Array.from(selected).some((i) => !tracks[i].tidal_exists) && (
                  <button
                    onClick={validateSelected}
                    disabled={loading}
                    class="text-xs font-medium text-text hover:text-primary transition-colors uppercase tracking-wider ml-2"
                  >
                    Check Selected (
                    {
                      Array.from(selected).filter(
                        (i) => !tracks[i].tidal_exists,
                      ).length
                    }
                    )
                  </button>
                )}

              <div class="h-4 w-px bg-border mx-2"></div>

              <button
                onClick={toggleAll}
                class="text-xs font-medium text-text-muted hover:text-text transition-colors"
              >
                {selected.size === tracks.length
                  ? "Deselect All"
                  : "Select All"}
              </button>
              {selected.size > 0 && (
                <button
                  class="btn-primary py-1.5 px-4 text-sm"
                  onClick={handleDownloadSelected}
                >
                  Add{" "}
                  {
                    Array.from(selected).filter((i) => tracks[i].tidal_exists)
                      .length
                  }{" "}
                  to Queue
                </button>
              )}
            </div>
          </div>

          <div class="grid grid-cols-1 gap-2 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin">
            {tracks.map((track, idx) => (
              <div
                key={idx}
                onClick={() => toggleTrack(idx)}
                class={`group relative flex items-center p-2 rounded-lg border transition-all duration-200 cursor-pointer ${
                  track.tidal_exists
                    ? selected.has(idx)
                      ? "bg-primary/5 border-primary/30"
                      : "bg-surface hover:bg-surface-alt border-border-light hover:border-border"
                    : trackStatuses[idx] === "error"
                      ? selected.has(idx)
                        ? "bg-red-500/10 border-red-500/20"
                        : "bg-red-500/5 border-red-500/10"
                      : selected.has(idx)
                        ? "bg-surface-alt border-border"
                        : "bg-surface border-border-light"
                }`}
              >
                <div class="absolute left-2 top-1/2 -translate-y-1/2 z-10 flex items-center justify-center">
                  <ModernCheckbox
                    checked={selected.has(idx)}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleTrack(idx);
                    }}
                  />
                </div>

                <div
                  class={`relative h-12 w-12 rounded overflow-hidden flex-shrink-0 ml-8 mr-3 bg-surface-alt`}
                >
                  {track.cover ? (
                    <img
                      src={api.getCoverUrl(track.cover, "160")}
                      alt={track.album}
                      class="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div class="h-full w-full flex items-center justify-center text-text-muted/20">
                      <svg
                        class="w-6 h-6"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z" />
                      </svg>
                    </div>
                  )}
                  {/* Overlay Status Icon */}
                  {trackStatuses[idx] === "validating" && (
                    <div class="absolute inset-0 bg-black/50 flex items-center justify-center">
                      <svg
                        class="animate-spin h-5 w-5 text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
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
                    </div>
                  )}
                </div>

                <div class="flex-1 min-w-0 pr-2">
                  <div class="flex items-center gap-2">
                    <p
                      class={`text-sm font-semibold truncate ${track.tidal_exists ? "text-text" : "text-text-muted"}`}
                    >
                      {track.title}
                    </p>
                    {!track.tidal_exists && trackStatuses[idx] === "error" && (
                      <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/10 text-red-500 uppercase">
                        Missing
                      </span>
                    )}
                  </div>
                  <p class="text-xs text-text-muted truncate mt-0.5">
                    {track.artist}
                    {track.album && (
                      <span class="opacity-50"> • {track.album}</span>
                    )}
                  </p>
                </div>

                <div class="flex items-center gap-2">
                  {!track.tidal_exists &&
                    trackStatuses[idx] !== "error" &&
                    trackStatuses[idx] !== "validating" && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          validateTrack(idx);
                        }}
                        class="p-1.5 rounded hover:bg-surface-alt/50 text-text-muted hover:text-primary transition-colors"
                        title="Check Availability"
                      >
                        <svg
                          class="w-5 h-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                          />
                        </svg>
                      </button>
                    )}

                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownloadSingle(idx);
                    }}
                    class={`p-1.5 rounded hover:bg-surface-alt/50 transition-colors ${
                      track.tidal_exists
                        ? "text-text hover:text-primary"
                        : "text-text-muted hover:text-text"
                    }`}
                    title={
                      track.tidal_exists
                        ? "Add to Queue"
                        : "Check & Add to Queue"
                    }
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
