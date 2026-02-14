import { h } from "preact";
import { useState, useRef, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";

export function WeeklyJamsGenerator() {
  const [activeTab, setActiveTab] = useState("manual"); // 'manual' | 'automated'

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex gap-1 sm:gap-2 border-b border-border pb-0 overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
        <button
          className={`px-3 sm:px-4 py-2 font-medium rounded-t-lg transition-all duration-200 whitespace-nowrap text-sm flex-shrink-0 ${
            activeTab === "manual"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
          }`}
          onClick={() => setActiveTab("manual")}
        >
          Manual Generation
        </button>
        <button
          className={`px-3 sm:px-4 py-2 font-medium rounded-t-lg transition-all duration-200 whitespace-nowrap text-sm flex-shrink-0 ${
            activeTab === "automated"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
          }`}
          onClick={() => setActiveTab("automated")}
        >
          Jellyfin Automation
        </button>
      </div>

      <div className="rounded-b-xl">
        {activeTab === "manual" ? <ManualGenerator /> : <AutomatedSync />}
      </div>
    </div>
  );
}

function AutomatedSync() {
  const [jellyfinUsers, setJellyfinUsers] = useState([]);
  const [monitoredPlaylists, setMonitoredPlaylists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [jellyfinConfigured, setJellyfinConfigured] = useState(true); // Assume true initially

  // Local state to store LB username inputs for each Jellyfin user
  const [lbInputs, setLbInputs] = useState({});
  // Local state for quality selection per user. Format: { userId: 'LOSSLESS' | 'HIGH' | 'LOW' }
  const [qualityInputs, setQualityInputs] = useState({});
  // State to track specific connection steps for better error messages
  const [connectionStatus, setConnectionStatus] = useState({
    checkedSettings: false,
    connectionTest: "idle", // 'idle' | 'testing' | 'success' | 'failed'
    connectionMessage: null,
  });

  const addToast = useToastStore((state) => state.addToast);

  const PLAYLIST_TYPES = [
    { id: "weekly-jams", label: "Weekly Jams", freq: "weekly" },
    { id: "weekly-exploration", label: "Weekly Exploration", freq: "weekly" },
    {
      id: "year-in-review-discoveries",
      label: "YiR Discoveries",
      freq: "yearly",
    },
    { id: "year-in-review-missed", label: "YiR Missed", freq: "yearly" },
  ];

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setConnectionStatus({
      checkedSettings: false,
      connectionTest: "idle",
      connectionMessage: null,
    });

    try {
      // 2. Direct fetch attempt (Simpler is more robust)
      // Rely on the backend call to succeed or fail.
      const [usersResp, playlists] = await Promise.all([
        api.getJellyfinUsers(),
        api.getMonitoredPlaylists(),
      ]);

      if (usersResp.status === "error") {
        // If 401/403 backend returns status error usually
        throw new Error(usersResp.message || "Failed to fetch users");
      }

      const users = usersResp?.users || [];
      // Success!
      setJellyfinUsers(users);
      setMonitoredPlaylists(playlists || []);
      setConnectionStatus((prev) => ({ ...prev, connectionTest: "success" }));
    } catch (e) {
      console.error(e);
      addToast(`Jellyfin Error: ${e.message}`, "error");
      setConnectionStatus((prev) => ({
        ...prev,
        connectionTest: "failed",
        connectionMessage: e.message,
      }));
    } finally {
      setLoading(false);
    }
  };

  // Effect to pre-fill inputs once data is loaded
  useEffect(() => {
    if (jellyfinUsers.length > 0 && monitoredPlaylists.length > 0) {
      const newLbInputs = { ...lbInputs };
      const newQualityInputs = { ...qualityInputs };
      let changed = false;

      jellyfinUsers.forEach((user) => {
        // Try to infer state from existing playlists for this user
        for (const p of monitoredPlaylists) {
          if (p.source === "listenbrainz" && p.extra_config?.lb_username) {
            // Check if playlist name starts with User Name (heuristic)
            if (p.name.startsWith(`${user.Name} - `)) {
              if (!newLbInputs[user.Id]) {
                newLbInputs[user.Id] = p.extra_config.lb_username;
                changed = true;
              }
              // Also infer quality from the FIRST found playlist for this user?
              // Or just default to LOSSLESS.
              // If we find a playlist, we could check its quality ??
              // Actually MonitoredPlaylist object has 'quality'.
              // But we can't easily map back if they have mixed qualities.
              // Let's just default to 'LOSSLESS' if not set.
              break;
            }
          }
        }
        if (!newQualityInputs[user.Id]) {
          newQualityInputs[user.Id] = "LOSSLESS";
          changed = true;
        }
      });

      if (changed) {
        setLbInputs(newLbInputs);
        setQualityInputs(newQualityInputs);
      }
    } else if (jellyfinUsers.length > 0) {
      // Initialize defaults even if no playlists
      const newQualityInputs = { ...qualityInputs };
      let changed = false;
      jellyfinUsers.forEach((user) => {
        if (!newQualityInputs[user.Id]) {
          newQualityInputs[user.Id] = "LOSSLESS";
          changed = true;
        }
      });
      if (changed) setQualityInputs(newQualityInputs);
    }
  }, [jellyfinUsers, monitoredPlaylists]);

  const getUuid = (lbUser, type) => `lb:${lbUser}:${type}`;

  const isMonitored = (lbUser, type) => {
    if (!lbUser) return false;
    const uuid = getUuid(lbUser, type);
    return monitoredPlaylists.some((p) => p.uuid === uuid);
  };

  const formatLastSync = (isoString) => {
    if (!isoString) return "Never";
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const handleManualSync = async (uuid, label) => {
    try {
      addToast(`Starting sync for ${label}...`, "info");
      const res = await api.syncPlaylist(uuid);

      if (res.status === "success") {
        if (res.queued > 0) {
          addToast(
            `Sync complete! Added ${res.queued} tracks to queue.`,
            "success",
          );
        } else {
          addToast(
            `Sync complete! Playlist up to date (${res.total_tracks} tracks).`,
            "success",
          );
        }
      } else if (res.status === "empty") {
        addToast(
          `Sync complete! No tracks found in source playlist.`,
          "warning",
        );
      } else {
        addToast(`Sync finished with status: ${res.status}`, "info");
      }

      // Refresh playlists to update last_sync time
      const playlists = await api.getMonitoredPlaylists();
      setMonitoredPlaylists(playlists);
    } catch (e) {
      addToast(`Sync failed: ${e.message}`, "error");
    }
  };

  const handleRemove = async (uuid, label) => {
    if (
      !confirm(`Stop syncing "${label}"? This will delete the playlist file.`)
    )
      return;
    try {
      await api.removeMonitoredPlaylist(uuid);
      const playlists = await api.getMonitoredPlaylists();
      setMonitoredPlaylists(playlists);
      addToast(`Stopped syncing ${label}`, "success");
    } catch (e) {
      addToast(`Failed to remove: ${e.message}`, "error");
    }
  };

  const handleCreate = async (jfUser, typeObj, lbUser, quality) => {
    if (!lbUser) {
      addToast("Please enter a ListenBrainz username first", "error");
      return;
    }
    const uuid = getUuid(lbUser, typeObj.id);
    try {
      const name = `${jfUser.Name} - ${typeObj.label}`;
      await api.monitorPlaylist(
        uuid,
        name,
        typeObj.freq,
        quality || "LOSSLESS",
        "listenbrainz",
        { lb_username: lbUser, lb_type: typeObj.id },
      );
      const playlists = await api.getMonitoredPlaylists();
      setMonitoredPlaylists(playlists);
      addToast(
        `Started syncing ${typeObj.label} [${quality || "LOSSLESS"}]`,
        "success",
      );
    } catch (e) {
      addToast(`Failed to create: ${e.message}`, "error");
    }
  };

  if (loading)
    return (
      <div className="flex flex-col items-center justify-center p-12 text-zinc-500">
        <svg
          className="animate-spin h-8 w-8 mb-4 text-primary"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          ></circle>
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
        <p>Loading automation data...</p>
      </div>
    );

  if (jellyfinUsers.length === 0)
    return (
      <div className="p-12 text-center text-text-muted">
        No Jellyfin users found. Please check your connection in Settings.
      </div>
    );

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {jellyfinUsers.map((user) => (
        <div key={user.Id} className="card p-4 flex flex-col h-full">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-dark shadow-sm flex-shrink-0 overflow-hidden relative">
              <img
                src={`/api/system/jellyfin/users/${user.Id}/image`}
                alt={user.Name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.target.style.display = "none";
                  e.target.nextSibling.style.display = "flex";
                }}
              />
              <div className="absolute inset-0 flex items-center justify-center text-white text-sm font-bold uppercase hidden bg-gradient-to-br from-primary to-primary-dark">
                {user.Name.substring(0, 2)}
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-base font-semibold text-text truncate">
                {user.Name}
              </h3>
              <div className="flex gap-2 mt-1">
                <input
                  type="text"
                  className="input-field py-1 h-7 text-xs flex-1 min-w-0"
                  placeholder="ListenBrainz Username"
                  value={lbInputs[user.Id] || ""}
                  onInput={(e) =>
                    setLbInputs((prev) => ({
                      ...prev,
                      [user.Id]: e.target.value,
                    }))
                  }
                />
                <select
                  className="input-field py-1 h-7 text-xs w-32"
                  value={qualityInputs[user.Id] || "LOSSLESS"}
                  onChange={(e) =>
                    setQualityInputs((prev) => ({
                      ...prev,
                      [user.Id]: e.target.value,
                    }))
                  }
                >
                  <option value="HI_RES_LOSSLESS">Hi-Res</option>
                  <option value="LOSSLESS">FLAC (16bit)</option>
                  <option value="HIGH">High (320)</option>
                  <option value="LOW">Low (96)</option>
                  <option value="MP3_256">MP3 256</option>
                </select>
              </div>
            </div>
          </div>

          <div className="space-y-2 flex-1">
            {PLAYLIST_TYPES.map((type) => {
              const lbUser = lbInputs[user.Id];
              const uuid = lbUser ? getUuid(lbUser, type.id) : null;
              const playlist = monitoredPlaylists.find((p) => p.uuid === uuid);
              const active = !!playlist;

              return (
                <div
                  key={type.id}
                  className={`flex items-center justify-between p-2 rounded-lg border transition-all ${
                    active
                      ? "bg-primary/5 border-primary/20"
                      : "bg-surface-alt border-border-light hover:border-border"
                  }`}
                >
                  <div className="min-w-0 flex-1 mr-2">
                    <span
                      className={`text-xs font-semibold block truncate ${active ? "text-primary" : "text-text-muted"}`}
                    >
                      {type.label}
                    </span>
                    {active ? (
                      <span className="text-[10px] text-text-muted flex items-center gap-1">
                        <svg
                          className="w-3 h-3"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        {formatLastSync(playlist.last_sync)}
                        {/* Show saved quality if desired, e.g. • {playlist.quality} */}
                      </span>
                    ) : (
                      <span className="text-[10px] text-text-muted opacity-70">
                        Sync: {type.freq}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1">
                    {active ? (
                      <>
                        <button
                          onClick={() => handleManualSync(uuid, type.label)}
                          className="p-1.5 rounded hover:bg-primary/10 text-text-muted hover:text-primary transition-colors"
                          title="Sync Now"
                        >
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                            />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleRemove(uuid, type.label)}
                          className="p-1.5 rounded hover:bg-red-500/10 text-text-muted hover:text-red-500 transition-colors"
                          title="Stop Syncing"
                        >
                          <svg
                            className="w-4 h-4"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                            />
                          </svg>
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() =>
                          handleCreate(
                            user,
                            type,
                            lbUser,
                            qualityInputs[user.Id],
                          )
                        }
                        className="p-1.5 rounded bg-surface hover:bg-primary hover:text-white text-text-muted border border-border transition-all shadow-sm"
                        title={`Enable Sync (${qualityInputs[user.Id] || "LOSSLESS"})`}
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                          />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Existing Logic Refactored into Component
// ----------------------------------------------------------------------------

function ManualGenerator() {
  const [username, setUsername] = useState("");
  const [playlistType, setPlaylistType] = useState("weekly-jams");
  const [loading, setLoading] = useState(false);
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState(null);
  const [progressLogs, setProgressLogs] = useState([]);
  const logsEndRef = useRef(null);

  // Track status map: { idx: 'idle' | 'validating' | 'success' | 'error' }
  const [trackStatuses, setTrackStatuses] = useState({});

  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [progressLogs]);

  const handleFetch = async () => {
    if (!username.trim()) {
      setError("Please enter a ListenBrainz username");
      return;
    }

    setLoading(true);
    setError(null);
    setTracks([]);
    setSelected(new Set());
    setProgressLogs([]);
    setTrackStatuses({});

    try {
      // Validate = false for just fetching list
      const { progress_id } = await api.generateListenBrainzPlaylist(
        username.trim(),
        playlistType,
        false,
      );

      const eventSource = api.createListenBrainzProgressStream(progress_id);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "ping") return;

        if (data.type === "info" || data.type === "error") {
          setProgressLogs((prev) => [
            ...prev,
            {
              type: data.type,
              message: data.message,
              timestamp: new Date().toISOString(),
            },
          ]);
        }

        if (data.type === "complete") {
          setTracks(data.tracks);
          setLoading(false);
          eventSource.close();
          addToast(
            `Fetched ${data.tracks.length} tracks. Check availability before downloading.`,
            "success",
          );
        }

        if (data.type === "error") {
          setError(data.message);
          setLoading(false);
          eventSource.close();
          addToast(`Failed to fetch playlist: ${data.message}`, "error");
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
      addToast(`Failed to fetch playlist: ${err.message}`, "error");
    }
  };

  const validateTrack = async (idx) => {
    setTrackStatuses((prev) => ({ ...prev, [idx]: "validating" }));

    try {
      // Get track from current state using functional update
      let trackToValidate;
      setTracks((prev) => {
        trackToValidate = prev[idx];
        return prev; // No change yet
      });

      if (!trackToValidate) return;

      const result = await api.validateListenBrainzTrack(trackToValidate);

      // Update using functional state update to prevent race condition
      setTracks((prev) => {
        const newTracks = [...prev];
        newTracks[idx] = result;
        return newTracks;
      });

      if (result.tidal_exists) {
        setTrackStatuses((prev) => ({ ...prev, [idx]: "success" }));
        setSelected((prev) => new Set(prev).add(result.tidal_id));
      } else {
        setTrackStatuses((prev) => ({ ...prev, [idx]: "error" }));
      }

      return result;
    } catch (e) {
      console.error("Validation failed", e);
      setTrackStatuses((prev) => ({ ...prev, [idx]: "error" }));

      // Return original track from current state
      let originalTrack;
      setTracks((prev) => {
        originalTrack = prev[idx];
        return prev;
      });
      return originalTrack;
    }
  };

  const validateAll = async () => {
    // Find all tracks that need validation
    const indicesToValidate = tracks
      .map((_, i) => i)
      .filter((i) => !tracks[i].tidal_exists && trackStatuses[i] !== "error");

    let validatedCount = 0;

    // Process in batches to avoid overwhelming (though browser handles async well, server might rate limit)
    // Let's do logical concurrency of 3
    const concurrency = 3;
    for (let i = 0; i < indicesToValidate.length; i += concurrency) {
      const batch = indicesToValidate.slice(i, i + concurrency);
      await Promise.all(batch.map((idx) => validateTrack(idx)));
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
    // Only select tracks that EXIST
    const availableTracks = tracks.filter((t) => t.tidal_exists);

    if (selected.size === availableTracks.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(availableTracks.map((t) => t.tidal_id)));
    }
  };

  const handleDownloadSingle = async (idx) => {
    let track = tracks[idx];

    // If not validated, validate first
    if (!track.tidal_exists) {
      track = await validateTrack(idx);
    }

    if (track.tidal_exists) {
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
      addToast(`Could not find "${track.title}" on Tidal`, "error");
    }
  };

  const handleDownloadSelected = () => {
    const selectedTracks = tracks
      .filter((t) => selected.has(t.tidal_id))
      .map((t) => ({
        ...t,
        tidal_track_id: t.tidal_id,
        tidal_artist_id: t.tidal_artist_id,
        tidal_album_id: t.tidal_album_id,
        cover: t.cover,
      }));

    if (selectedTracks.length === 0) return;

    downloadManager.addToServerQueue(selectedTracks).then((result) => {
      addToast(`Added ${result.added} tracks to download queue`, "success");
    });
  };

  const PLAYLIST_TYPES = [
    { id: "weekly-jams", label: "Weekly Jams" },
    { id: "weekly-exploration", label: "Weekly Exploration" },
    { id: "year-in-review-discoveries", label: "Year in Review: Discoveries" },
    { id: "year-in-review-missed", label: "Year in Review: Missed" },
  ];

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="sm:col-span-1">
          <label className="block text-xs font-semibold text-text-muted mb-1.5 uppercase tracking-wider">
            Playlist Type
          </label>
          <select
            value={playlistType}
            onChange={(e) => setPlaylistType(e.target.value)}
            disabled={loading}
            className="input-field w-full h-[42px] text-sm"
          >
            {PLAYLIST_TYPES.map((type) => (
              <option key={type.id} value={type.id}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div className="sm:col-span-2">
          <label className="block text-xs font-semibold text-text-muted mb-1.5 uppercase tracking-wider">
            ListenBrainz Username
          </label>
          <input
            type="text"
            value={username}
            onInput={(e) => setUsername(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter" && !loading && username.trim()) {
                handleFetch();
              }
            }}
            placeholder="Username..."
            disabled={loading}
            className="input-field w-full h-[42px] text-sm"
          />
        </div>

        <div className="sm:col-span-1 flex items-end">
          <button
            onClick={handleFetch}
            disabled={loading || !username.trim()}
            className="btn-primary w-full h-[42px] flex items-center justify-center gap-2 text-sm"
          >
            {loading ? (
              <svg
                className="animate-spin h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
            ) : (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            )}
            Fetch Playlist
          </button>
        </div>
      </div>

      {loading && (
        <div className="p-4 bg-surface-alt border border-border-light rounded-lg">
          <div className="flex items-center gap-3 text-text-muted">
            <svg
              className="animate-spin h-5 w-5 text-primary"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            <span>Fetching playlist data...</span>
          </div>
          {progressLogs.length > 0 && (
            <div className="mt-2 text-xs font-mono text-text-muted">
              {progressLogs[progressLogs.length - 1].message}
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg animate-fadeIn">
          <p className="text-sm text-red-500 flex items-center gap-2">
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            {error}
          </p>
        </div>
      )}

      {tracks.length > 0 && (
        <div className="space-y-4 animate-fadeIn">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-border-light">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-bold text-text">Results</h3>
              <span className="px-2 py-0.5 rounded-full bg-surface-alt border border-border-light text-xs font-mono text-text-muted">
                {tracks.filter((t) => t.tidal_exists).length}/{tracks.length}{" "}
                FOUND
              </span>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={validateAll}
                disabled={loading}
                className="text-xs font-medium text-primary hover:text-primary-light transition-colors uppercase tracking-wider flex items-center gap-1"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Check All
              </button>
              <div className="h-4 w-px bg-border"></div>
              <button
                onClick={toggleAll}
                className="text-xs font-medium text-text-muted hover:text-text transition-colors"
              >
                {selected.size > 0 &&
                selected.size === tracks.filter((t) => t.tidal_exists).length
                  ? "Deselect All"
                  : "Select All Available"}
              </button>
              {selected.size > 0 && (
                <button
                  className="btn-primary py-1.5 px-4 text-sm"
                  onClick={handleDownloadSelected}
                >
                  Add {selected.size} to Queue
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin">
            {tracks.map((track, idx) => (
              <div
                key={idx}
                className={`group relative flex items-center p-2 rounded-lg border transition-all duration-200 ${
                  track.tidal_exists
                    ? selected.has(track.tidal_id)
                      ? "bg-primary/5 border-primary/30"
                      : "bg-surface hover:bg-surface-alt border-border-light hover:border-border"
                    : trackStatuses[idx] === "error"
                      ? "bg-red-500/5 border-red-500/10"
                      : "bg-surface border-border-light"
                }`}
              >
                <div className="absolute left-2 top-1/2 -translate-y-1/2 z-10 flex items-center justify-center">
                  {/* Checkbox only if exists */}
                  {track.tidal_exists ? (
                    <input
                      type="checkbox"
                      checked={selected.has(track.tidal_id)}
                      onChange={() => toggleTrack(track.tidal_id)}
                      className={`w-5 h-5 rounded border-gray-600 text-primary focus:ring-primary focus:ring-offset-gray-900 bg-gray-800/50 transition-opacity`}
                    />
                  ) : // If not exists, maybe show a status icon or check button?
                  // Let's show check button if idle
                  trackStatuses[idx] === "validating" ? (
                    <svg
                      className="animate-spin h-5 w-5 text-primary"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                  ) : trackStatuses[idx] === "error" ? (
                    <span className="text-red-500 font-bold text-xs">X</span>
                  ) : (
                    <span className="text-text-muted text-xs font-mono">
                      {idx + 1}
                    </span>
                  )}
                </div>

                <div
                  className={`relative h-12 w-12 rounded overflow-hidden flex-shrink-0 ml-8 mr-3 bg-surface-alt`}
                >
                  {track.cover ? (
                    <img
                      src={api.getCoverUrl(track.cover, "160")}
                      alt={track.album}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="h-full w-full flex items-center justify-center text-text-muted/20">
                      <svg
                        className="w-6 h-6"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z" />
                      </svg>
                    </div>
                  )}
                </div>

                <div className="flex-1 min-w-0 pr-2">
                  <div className="flex items-center gap-2">
                    <p
                      className={`text-sm font-semibold truncate ${track.tidal_exists ? "text-text" : "text-text-muted"}`}
                    >
                      {track.title}
                    </p>
                    {!track.tidal_exists && trackStatuses[idx] === "error" && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/10 text-red-500 uppercase">
                        Missing
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-text-muted truncate mt-0.5">
                    {track.artist}
                    {track.album && (
                      <span className="opacity-50"> • {track.album}</span>
                    )}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {!track.tidal_exists &&
                    trackStatuses[idx] !== "error" &&
                    trackStatuses[idx] !== "validating" && (
                      <button
                        onClick={() => validateTrack(idx)}
                        className="p-1.5 rounded hover:bg-surface-alt/50 text-text-muted hover:text-primary transition-colors"
                        title="Check Availability"
                      >
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                          />
                        </svg>
                      </button>
                    )}

                  <button
                    onClick={() => handleDownloadSingle(idx)}
                    className={`p-1.5 rounded hover:bg-surface-alt/50 transition-colors ${
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
                      className="w-5 h-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
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
