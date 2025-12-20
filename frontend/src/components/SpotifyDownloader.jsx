import { h } from "preact";
import { useState, useRef, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";

export function SpotifyDownloader() {
    const [playlistUrl, setPlaylistUrl] = useState("");
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

        try {
            const { progress_id } = await api.generateSpotifyPlaylist(playlistUrl.trim());

            const eventSource = api.createSpotifyProgressStream(progress_id);

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === "ping") return;

                if (data.type === "info" || data.type === "error" || data.type === "validating") {
                    // Update logs
                    if (data.message) {
                        setProgressLogs((prev) => [
                            ...prev,
                            {
                                type: data.type,
                                message: data.message,
                                timestamp: new Date().toISOString(),
                            },
                        ]);
                    }
                }

                // Handle validation updates real-time if provided
                if (data.type === "validating" && data.current_track) {
                    // We could show current validation item
                }

                if (data.type === "complete") {
                    setTracks(data.tracks);
                    setLoading(false);
                    eventSource.close();
                    addToast(`Finished processing. Found ${data.found_count} matches on Tidal.`, "success");
                }

                if (data.type === "error") {
                    setError(data.message);
                    setLoading(false);
                    eventSource.close();
                    addToast(`Failed to process playlist: ${data.message}`, "error");
                }
            };

            eventSource.onerror = () => {
                setError("Connection lost to server");
                setLoading(false);
                eventSource.close();
            };
        } catch (err) {
            setError(err.message);
            setLoading(false);
            addToast(`Failed to start process: ${err.message}`, "error");
        }
    };

    const validateTrack = async (idx) => {
        const track = tracks[idx];
        if (!track) return;

        setTrackStatuses(prev => ({ ...prev, [idx]: 'validating' }));

        try {
            // Reuse LB validation endpoint or just respect backend result? 
            // The backend ALREADY validates all tracks in this flow.
            // So re-validation is effectively "Manual Check" via general search?
            // Actually, for Spotify process we validate ALL on backend.
            // But if user wants to retry one that failed?

            // We can use the ListenBrainz validate-track endpoint as it accepts a generic track object
            // and performs search. It's compatible.
            const result = await api.validateListenBrainzTrack(track);

            // Update track with result
            const newTracks = [...tracks];
            newTracks[idx] = result;
            setTracks(newTracks);

            if (result.tidal_exists) {
                setTrackStatuses(prev => ({ ...prev, [idx]: 'success' }));
                setSelected(prev => new Set(prev).add(result.tidal_id));
            } else {
                setTrackStatuses(prev => ({ ...prev, [idx]: 'error' }));
            }

            return result;
        } catch (e) {
            console.error("Validation failed", e);
            setTrackStatuses(prev => ({ ...prev, [idx]: 'error' }));
            return track;
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
        const availableTracks = tracks.filter((t) => t.tidal_exists);

        if (selected.size === availableTracks.length) {
            setSelected(new Set());
        } else {
            setSelected(
                new Set(availableTracks.map((t) => t.tidal_id))
            );
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
                cover: t.cover
            }));

        if (selectedTracks.length === 0) return;

        downloadManager.addToServerQueue(selectedTracks).then((result) => {
            addToast(`Added ${result.added} tracks to download queue`, "success");
        });
    };

    return (
        <div class="space-y-6">
            <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
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
                        class="input-field w-full h-[42px]"
                    />
                </div>

                <div class="sm:col-span-1 flex items-end">
                    <button
                        onClick={handleFetch}
                        disabled={loading || !playlistUrl.trim()}
                        class="btn-primary w-full h-[42px] flex items-center justify-center gap-2"
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
                        <svg class="animate-spin h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Fetching playlist from Spotify & matching tracks...</span>
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
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        {error}
                    </p>
                </div>
            )}

            {tracks.length > 0 && (
                <div class="space-y-4 animate-fadeIn">
                    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-border-light">
                        <div class="flex items-center gap-3">
                            <h3 class="text-lg font-bold text-text">
                                Results
                            </h3>
                            <span class="px-2 py-0.5 rounded-full bg-surface-alt border border-border-light text-xs font-mono text-text-muted">
                                {tracks.filter((t) => t.tidal_exists).length}/{tracks.length} MATCHED
                            </span>
                        </div>

                        <div class="flex items-center gap-3">
                            <button
                                onClick={toggleAll}
                                class="text-xs font-medium text-text-muted hover:text-text transition-colors"
                            >
                                {selected.size > 0 && selected.size === tracks.filter((t) => t.tidal_exists).length ? "Deselect All" : "Select All Matches"}
                            </button>
                            {selected.size > 0 && (
                                <button class="btn-primary py-1.5 px-4 text-sm" onClick={handleDownloadSelected}>
                                    Add {selected.size} to Queue
                                </button>
                            )}
                        </div>
                    </div>

                    <div class="grid grid-cols-1 gap-2 max-h-[600px] overflow-y-auto pr-2 scrollbar-thin">
                        {tracks.map((track, idx) => (
                            <div
                                key={idx}
                                class={`group relative flex items-center p-2 rounded-lg border transition-all duration-200 ${track.tidal_exists
                                    ? selected.has(track.tidal_id)
                                        ? "bg-primary/5 border-primary/30"
                                        : "bg-surface hover:bg-surface-alt border-border-light hover:border-border"
                                    : "bg-surface border-border-light opacity-60"
                                    }`}
                            >
                                <div class="absolute left-2 top-1/2 -translate-y-1/2 z-10 flex items-center justify-center">
                                    {track.tidal_exists ? (
                                        <input
                                            type="checkbox"
                                            checked={selected.has(track.tidal_id)}
                                            onChange={() => toggleTrack(track.tidal_id)}
                                            class={`w-5 h-5 rounded border-gray-600 text-primary focus:ring-primary focus:ring-offset-gray-900 bg-gray-800/50 transition-opacity`}
                                        />
                                    ) : (
                                        <span class="text-red-500 font-bold text-xs" title="Not found on Tidal">X</span>
                                    )}
                                </div>

                                <div class={`relative h-12 w-12 rounded overflow-hidden flex-shrink-0 ml-8 mr-3 bg-surface-alt`}>
                                    {track.cover ? (
                                        <img
                                            src={api.getCoverUrl(track.cover, "160")}
                                            alt={track.album}
                                            class="h-full w-full object-cover"
                                            loading="lazy"
                                        />
                                    ) : (
                                        <div class="h-full w-full flex items-center justify-center text-text-muted/20">
                                            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z" /></svg>
                                        </div>
                                    )}
                                </div>

                                <div class="flex-1 min-w-0 pr-2">
                                    <div class="flex items-center gap-2">
                                        <p class={`text-sm font-semibold truncate ${track.tidal_exists ? 'text-text' : 'text-text-muted'}`}>
                                            {track.title}
                                        </p>
                                    </div>
                                    <p class="text-xs text-text-muted truncate mt-0.5">
                                        {track.artist}
                                        {track.album && <span class="opacity-50"> • {track.album}</span>}
                                    </p>
                                </div>

                                {!track.tidal_exists && (
                                    <button
                                        onClick={() => validateTrack(idx)}
                                        class="p-1.5 rounded hover:bg-surface-alt/50 text-text-muted hover:text-primary transition-colors"
                                        title="Retry Match"
                                    >
                                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                        </svg>
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
