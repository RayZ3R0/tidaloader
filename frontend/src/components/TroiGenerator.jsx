import { h } from "preact";
import { useState, useRef, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";

export function TroiGenerator() {
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState(null);
  const [progressLogs, setProgressLogs] = useState([]);
  const [validationProgress, setValidationProgress] = useState(0);
  const [validationTotal, setValidationTotal] = useState(0);
  const logsEndRef = useRef(null);

  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLogs]);

  const handleGenerate = async () => {
    if (!username.trim()) {
      setError("Please enter a ListenBrainz username");
      return;
    }

    setLoading(true);
    setError(null);
    setTracks([]);
    setSelected(new Set());
    setProgressLogs([]);
    setValidationProgress(0);
    setValidationTotal(0);

    try {
      const { progress_id } = await api.generateTroiPlaylist(
        username.trim(),
        "periodic-jams"
      );

      const eventSource = api.createTroiProgressStream(progress_id);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "ping") return;

        setProgressLogs((prev) => [
          ...prev,
          {
            type: data.type,
            message: data.message,
            timestamp: new Date().toISOString(),
          },
        ]);

        if (data.progress !== undefined && data.total !== undefined) {
          setValidationProgress(data.progress);
          setValidationTotal(data.total);
        }

        if (data.type === "complete") {
          setTracks(data.tracks);
          const autoSelected = new Set(
            data.tracks.filter((t) => t.tidal_exists).map((t) => t.tidal_id)
          );
          setSelected(autoSelected);
          setLoading(false);
          eventSource.close();

          addToast(
            `Found ${data.found_count} of ${data.tracks.length} tracks on Tidal`,
            data.found_count > 0 ? "success" : "warning"
          );
        }

        if (data.type === "error" && !data.progress) {
          setError(data.message);
          setLoading(false);
          eventSource.close();
          addToast(`Failed to generate playlist: ${data.message}`, "error");
        }
      };

      eventSource.onerror = () => {
        setError("Connection lost to server");
        setLoading(false);
        eventSource.close();
        addToast("Connection lost to server", "error");
      };
    } catch (err) {
      setError(err.message);
      setLoading(false);
      addToast(`Failed to generate playlist: ${err.message}`, "error");
    }
  };

  const toggleTrack = (tidalId) => {
    const newSelected = new Set(selected);
    if (newSelected.has(tidalId)) {
      newSelected.delete(tidalId);
    } else {
      newSelected.add(tidalId);
    }
    setSelected(newSelected);
  };

  const toggleAll = () => {
    if (selected.size === tracks.filter((t) => t.tidal_exists).length) {
      setSelected(new Set());
    } else {
      setSelected(
        new Set(tracks.filter((t) => t.tidal_exists).map((t) => t.tidal_id))
      );
    }
  };

  const handleDownload = () => {
    const selectedTracks = tracks
      .filter((t) => selected.has(t.tidal_id))
      .map(t => ({
        ...t,
        tidal_track_id: t.tidal_id,
        tidal_artist_id: t.tidal_artist_id,
        tidal_album_id: t.tidal_album_id
      }));

    downloadManager.addToServerQueue(selectedTracks).then(result => {
      addToast(
        `Added ${result.added} tracks to download queue`,
        "success"
      );
    });
  };

  const progressPercentage =
    validationTotal > 0
      ? Math.round((validationProgress / validationTotal) * 100)
      : 0;

  return (
    <div class="space-y-6">
      <div class="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={username}
          onInput={(e) => setUsername(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === "Enter" && !loading && username.trim()) {
              handleGenerate();
            }
          }}
          placeholder="Enter ListenBrainz username..."
          disabled={loading}
          class="input-field flex-1"
        />
        <button
          onClick={handleGenerate}
          disabled={loading || !username.trim()}
          class="btn-primary flex items-center justify-center gap-2 sm:w-auto"
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
            <svg
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          )}
          Generate Playlist
        </button>
      </div>

      {loading && progressLogs.length > 0 && (
        <div class="space-y-4">
          {validationTotal > 0 && (
            <div class="p-4 bg-primary/5 border border-primary/20 rounded-lg">
              <div class="flex items-center justify-between text-sm mb-2">
                <span class="text-sm font-medium text-primary">
                  Validating tracks on Tidal...
                </span>
                <span class="text-sm font-semibold text-primary">
                  {validationProgress} / {validationTotal}
                </span>
              </div>
              <div class="w-full bg-background-alt rounded-full h-2 overflow-hidden">
                <div
                  class="h-full bg-gradient-to-r from-primary to-primary-light transition-all duration-300 ease-out"
                  style={{ width: `${progressPercentage}%` }}
                />
              </div>
            </div>
          )}

          <div class="p-4 bg-surface-alt border border-border-light rounded-lg max-h-[200px] overflow-y-auto font-mono text-xs space-y-1">
            {progressLogs.map((log, idx) => (
              <div
                key={idx}
                class={`flex items-start gap-2 ${log.type === "error"
                  ? "text-red-600"
                  : log.type === "success"
                    ? "text-green-600"
                    : log.type === "validating"
                      ? "text-blue-600"
                      : "text-text-muted"
                  }`}
              >
                <span class="flex-shrink-0">
                  {log.type === "error" && "❌"}
                  {log.type === "success" && "✅"}
                  {log.type === "validating" && "🔍"}
                  {log.type === "info" && "ℹ️"}
                </span>
                <span class="flex-1">{log.message}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        </div>
      )}

      {error && (
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-600">{error}</p>
        </div>
      )}

      {tracks.length > 0 && (
        <div class="space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <h3 class="text-lg font-semibold text-text">
              Found {tracks.length} tracks (
              {tracks.filter((t) => t.tidal_exists).length} on Tidal)
            </h3>
            {selected.size > 0 && (
              <button class="btn-primary" onClick={handleDownload}>
                Add {selected.size} to Queue
              </button>
            )}
          </div>

          <div class="flex items-center gap-2 p-3 bg-surface-alt rounded-lg border border-border-light">
            <input
              type="checkbox"
              checked={
                selected.size === tracks.filter((t) => t.tidal_exists).length &&
                selected.size > 0
              }
              onChange={toggleAll}
              class="custom-checkbox"
            />
            <span class="text-sm font-medium text-text">
              Select all available tracks (
              {tracks.filter((t) => t.tidal_exists).length})
            </span>
          </div>

          <div class="space-y-3 max-h-[600px] overflow-y-auto">
            {tracks.map((track, idx) => (
              <label
                key={idx}
                class={`search-result-card ${track.tidal_exists
                  ? selected.has(track.tidal_id)
                    ? "selected"
                    : ""
                  : "opacity-60 cursor-not-allowed"
                  }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(track.tidal_id)}
                  onChange={() => toggleTrack(track.tidal_id)}
                  disabled={!track.tidal_exists}
                  class="custom-checkbox"
                />
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-semibold text-text truncate">
                    {track.title}
                  </p>
                  <p class="text-xs text-text-muted truncate mt-1">
                    {track.artist}
                    {track.album && ` • ${track.album}`}
                  </p>
                </div>
                {!track.tidal_exists ? (
                  <span class="px-3 py-1 bg-red-100 text-red-600 text-xs font-semibold rounded-full flex-shrink-0">
                    Not Found
                  </span>
                ) : (
                  <span class="px-3 py-1 bg-primary text-white text-xs font-semibold rounded-full flex-shrink-0">
                    Available
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
