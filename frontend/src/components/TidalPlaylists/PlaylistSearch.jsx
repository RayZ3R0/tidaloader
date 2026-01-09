import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../../api/client";
import { useToastStore } from "../../stores/toastStore";


function extractPlaylistUuid(input) {
    if (!input) return null;
    const trimmed = input.trim();


    const uuidPattern = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;


    if (uuidPattern.test(trimmed)) {
        return trimmed;
    }


    const urlMatch = trimmed.match(/tidal\.com\/(?:browse\/)?playlist\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/i);
    if (urlMatch) {
        return urlMatch[1];
    }

    return null;
}

export function PlaylistSearch({ onSyncStarted }) {
    const [query, setQuery] = useState("");
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState([]);
    const [officialOnly, setOfficialOnly] = useState(false);
    const [selectedPlaylist, setSelectedPlaylist] = useState(null);
    const addToast = useToastStore((state) => state.addToast);

    const handleSearch = async () => {
        if (!query.trim()) return;


        const extractedUuid = extractPlaylistUuid(query);
        if (extractedUuid) {

            setLoading(true);
            setResults([]);
            try {
                const res = await api.getPlaylist(extractedUuid);
                if (res && res.playlist) {
                    const playlist = {
                        id: extractedUuid,
                        uuid: extractedUuid,
                        title: res.playlist.title || res.playlist.name || "Playlist",
                        numberOfTracks: res.items?.length || res.playlist.numberOfTracks,
                        cover: res.playlist.cover,
                        creator: res.playlist.creator,
                    };
                    setResults([playlist]);
                    addToast(`Found playlist: ${playlist.title}`, "success");
                } else {
                    addToast("Playlist not found", "error");
                }
            } catch (e) {
                addToast(`Failed to load playlist: ${e.message}`, "error");
            } finally {
                setLoading(false);
            }
            return;
        }

        setLoading(true);
        setResults([]);
        try {
            const res = await api.searchPlaylists(query);
            setResults(res.items || []);
            if (res.items?.length === 0) {
                addToast("No playlists found", "info");
            }
        } catch (e) {
            addToast(`Search failed: ${e.message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    const [previewPlaylist, setPreviewPlaylist] = useState(null);
    const [monitoredUuids, setMonitoredUuids] = useState(new Set());

    useEffect(() => {

        api.getMonitoredPlaylists().then(list => {
            setMonitoredUuids(new Set(list.map(p => p.uuid)));
        }).catch(err => console.error("Failed to load monitored status", err));
    }, []);

    const displayedResults = officialOnly
        ? results.filter(p => !p.creator || p.creator === "TIDAL" || p.creator === "Tidal")
        : results;

    const openMonitorModal = (playlist) => {
        setSelectedPlaylist(playlist);
    };

    const openPreview = (playlist) => {
        setPreviewPlaylist(playlist);
    };

    return (
        <>
            <div class="space-y-4 sm:space-y-6">
                <div class="flex flex-col gap-3">
                    <div class="flex flex-col sm:flex-row gap-2 sm:gap-3">
                        <input
                            type="text"
                            value={query}
                            onInput={(e) => setQuery(e.target.value)}
                            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
                            placeholder="Search or paste a Tidal playlist URL..."
                            disabled={loading}
                            class="input-field flex-1 text-sm"
                        />
                        <button
                            onClick={handleSearch}
                            disabled={loading || !query.trim()}
                            class="btn-primary flex items-center justify-center gap-2 w-full sm:w-auto text-sm"
                        >
                            {loading ? "Searching..." : "Search"}
                        </button>
                    </div>

                    <div class="flex items-center justify-between sm:justify-start gap-3 bg-surface-alt/50 px-3 py-2 rounded-lg border border-border-light">
                        <label class="text-xs sm:text-sm font-medium text-text cursor-pointer select-none" onClick={() => setOfficialOnly(!officialOnly)}>
                            Official Tidal Playlists only
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

                <div class="grid grid-cols-2 xs:grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 sm:gap-4">
                    {displayedResults.map((playlist) => (
                        <div
                            key={playlist.uuid || playlist.id}
                            class="card-hover p-3 flex flex-col gap-2 relative"
                        >
                            {playlist.cover ? (
                                <div
                                    class="cursor-pointer hover:opacity-90 transition-opacity"
                                    onClick={(e) => {
                                        openPreview(playlist);
                                    }}
                                >
                                    <PlaylistCoverImage cover={playlist.cover} title={playlist.title} />
                                </div>
                            ) : null}

                            {monitoredUuids.has(playlist.uuid || playlist.id) && (
                                <div class="absolute top-2 right-2 bg-green-500 text-white rounded-full p-1 shadow-md z-10">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                </div>
                            )}

                            <div class="flex-1 min-w-0">
                                <h3 class="font-semibold text-text line-clamp-2 leading-tight" title={playlist.title}>{playlist.title}</h3>
                                {playlist.creator && (
                                    <p class="text-xs text-text-muted truncate mt-1">
                                        By {playlist.creator}
                                    </p>
                                )}
                                <p class="text-xs text-text-muted mt-0.5">
                                    {playlist.numberOfTracks} tracks
                                </p>
                            </div>

                            {monitoredUuids.has(playlist.uuid || playlist.id) ? (
                                <button
                                    disabled
                                    class="btn-surface w-full mt-2 text-sm py-1.5 opacity-75 cursor-not-allowed border border-border"
                                >
                                    Already Synced
                                </button>
                            ) : (
                                <button
                                    onClick={(e) => {
                                        openMonitorModal(playlist);
                                    }}
                                    class="btn-primary w-full mt-2 text-sm py-1.5"
                                >
                                    Sync Playlist
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {selectedPlaylist && (
                <MonitorModal
                    playlist={selectedPlaylist}
                    onClose={() => setSelectedPlaylist(null)}
                    onSuccess={() => {
                        setSelectedPlaylist(null);
                        if (onSyncStarted) onSyncStarted();
                    }}
                />
            )}

            {previewPlaylist && (
                <PreviewModal
                    playlist={previewPlaylist}
                    onClose={() => setPreviewPlaylist(null)}
                />
            )}
        </>
    );
}

function PreviewModal({ playlist, onClose }) {
    const [loading, setLoading] = useState(true);
    const [tracks, setTracks] = useState([]);
    const [error, setError] = useState(null);

    useEffect(() => {
        console.log("PreviewModal useEffect fetching tracks");
        const loadTracks = async () => {
            try {
                const uuid = playlist.uuid || playlist.id;
                const result = await api.getPlaylist(uuid);
                console.log("PreviewModal fetched tracks:", result.items?.length);
                setTracks(result.items || []);
            } catch (e) {
                console.error("PreviewModal fetch error:", e);
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        loadTracks();
    }, [playlist]);

    return (
        <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
            <div class="bg-surface card w-full max-w-2xl flex flex-col max-h-[85vh] shadow-2xl rounded-xl">
                <div class="p-6 border-b border-border flex items-center gap-4 bg-surface rounded-t-xl">
                    {playlist.cover && (
                        <img
                            src={api.getCoverUrl(playlist.cover, "160")}
                            class="w-16 h-16 rounded-md shadow-sm object-cover"
                            alt={playlist.title}
                        />
                    )}
                    <div class="flex-1">
                        <h2 class="text-xl font-bold text-text">{playlist.title}</h2>
                        <p class="text-text-muted text-sm">{tracks.length} tracks {playlist.creator ? `• by ${playlist.creator}` : ''}</p>
                    </div>
                    <button onClick={onClose} class="text-text-muted hover:text-text p-2">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>

                <div class="flex-1 overflow-y-auto p-0">
                    {loading ? (
                        <div class="flex flex-col items-center justify-center py-12 gap-3 text-primary">
                            <div class="w-8 h-8 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            <p class="text-sm font-medium">Loading tracks...</p>
                        </div>
                    ) : error ? (
                        <div class="p-8 text-center text-red-500">
                            <p>Failed to load preview: {error}</p>
                        </div>
                    ) : (
                        <div class="divide-y divide-border-light">
                            {tracks.map((track, i) => (
                                <div key={track.id} class="px-6 py-3 hover:bg-surface-alt/50 flex items-center gap-4 group">
                                    <span class="text-text-muted text-sm w-6 text-right tabular-nums">{i + 1}</span>
                                    <div class="flex-1 min-w-0">
                                        <p class="text-text font-medium text-sm truncate">{track.title}</p>
                                        <p class="text-text-muted text-xs truncate">{track.artist} {track.album ? `• ${track.album}` : ''}</p>
                                    </div>
                                    <span class="text-text-muted text-xs tabular-nums opacity-0 group-hover:opacity-100 transition-opacity">
                                        {formatDuration(track.duration)}
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

function formatDuration(seconds) {
    if (!seconds) return '--:--';
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function PlaylistCoverImage({ cover, title }) {
    const variants = api.getCoverUrlVariants(cover);

    if (!variants.length) return null;

    const handleError = (e) => {
        const idx = Number(e.target.dataset.idx || 0);
        const next = idx + 1;
        if (next < variants.length) {
            e.target.dataset.idx = String(next);
            e.target.src = variants[next];
        }
    };

    return (
        <img
            src={variants[0]}
            data-idx="0"
            alt={title}
            onError={handleError}
            class="w-full aspect-square object-cover rounded-lg mb-2 shadow-sm"
        />
    );
}

function MonitorModal({ playlist, onClose, onSuccess }) {
    const [frequency, setFrequency] = useState("manual");
    const [quality, setQuality] = useState("LOSSLESS");
    const [usePlaylistFolder, setUsePlaylistFolder] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const addToast = useToastStore((state) => state.addToast);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            const uuid = playlist.uuid || playlist.id;
            // monitorPlaylist(uuid, name, frequency, quality, source, extra_config, use_playlist_folder)
            await api.monitorPlaylist(uuid, playlist.title, frequency, quality, "tidal", null, usePlaylistFolder);
            addToast(`Started monitoring "${playlist.title}"`, "success");
            onSuccess();
        } catch (e) {
            addToast(`Failed to monitor playlist: ${e.message}`, "error");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div class="bg-surface card p-6 w-full max-w-md space-y-4 animate-scale-in">
                <h2 class="text-xl font-bold text-text">Sync Playlist</h2>
                <p class="text-text-muted">
                    Setup synchronization for <span class="text-text font-medium">{playlist.title}</span>.
                    Currently supports generating M3U8 playlists.
                </p>

                <form onSubmit={handleSubmit} class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-text mb-1">Update Frequency</label>
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
                        <label class="block text-sm font-medium text-text mb-1">Quality</label>
                        <select
                            value={quality}
                            onChange={(e) => setQuality(e.target.value)}
                            class="input-field w-full"
                        >
                            <option value="LOW">Low (96kbps / 320kbps AAC)</option>
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
                            <span class="text-sm font-medium text-text">Download tracks to playlist folder</span>
                        </label>
                        <p class="text-xs text-text-muted mt-1 ml-6">
                            Creates a standalone folder "{playlist.title}" containing all tracks.
                            Useful for keeping files together, but duplicates tracks if they already exist in library.
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
                        <button
                            type="submit"
                            class="btn-primary"
                            disabled={submitting}
                        >
                            {submitting ? "Starting..." : "Start Sync"}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
