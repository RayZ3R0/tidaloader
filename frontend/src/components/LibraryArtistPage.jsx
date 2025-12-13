
import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { useToastStore } from "../stores/toastStore";
import { downloadManager } from "../utils/downloadManager";

export function LibraryArtistPage({ artistName, onBack }) {
    const [localData, setLocalData] = useState(null);
    const [remoteData, setRemoteData] = useState(null);
    const [mergedAlbums, setMergedAlbums] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchingTidal, setSearchingTidal] = useState(true);

    const [selectedAlbum, setSelectedAlbum] = useState(null);
    const addToast = useToastStore((state) => state.addToast);

    // Load local data and then search Tidal
    useEffect(() => {
        const loadData = async () => {
            setLoading(true);
            try {
                const local = await api.getLibraryArtist(artistName);
                if (!local) throw new Error("Artist not found locally");
                console.log("Local Data Loaded:", local);

                setLocalData(local);

                // Initial merge with just local data
                mergeData(local, null);

                // SHOW LOCAL DATA IMMEDIATELY
                setLoading(false);

                // Then search Tidal in background
                searchTidalArtist(local.name, local);
            } catch (err) {
                console.error("Failed to load local artist:", err);
                addToast("Failed to load artist details", "error");
                setLoading(false);
            }
        };
        loadData();
    }, [artistName]);

    const searchTidalArtist = async (name, localContext) => {
        setSearchingTidal(true);
        try {
            // NEW: Use embedded Tidal ID if available (100% accuracy)
            if (localContext?.tidal_id) {
                console.log(`Using embedded Tidal ID: ${localContext.tidal_id}`);
                const details = await api.getArtist(localContext.tidal_id);
                console.log("Remote Details (via ID):", details);
                setRemoteData(details);
                mergeData(localContext, details);
                setSearchingTidal(false);
                return;
            }

            console.log(`Searching Tidal for: ${name}`);
            const searchRes = await api.searchArtists(name);

            if (searchRes.items?.length > 0) {
                // Find best match by exact name (case-insensitive)
                const searchNameLower = name.toLowerCase();
                const items = searchRes.items;
                let tidalArtist = items.find(a => a.name.toLowerCase() === searchNameLower);

                // Fallback to first item if no exact match
                if (!tidalArtist) {
                    console.warn(`No exact match for '${name}', using first result: ${items[0].name}`);
                    tidalArtist = items[0];
                }

                console.log("Found Tidal Artist:", tidalArtist);

                const details = await api.getArtist(tidalArtist.id);
                console.log("Remote Details:", details);

                setRemoteData(details);
                // Merge will update the view with remote info
                mergeData(localContext || localData, details);
            } else {
                console.warn("No Tidal artist found for:", name);
            }
        } catch (err) {
            console.error("Failed to search Tidal:", err);
        } finally {
            setSearchingTidal(false);
        }
    };

    // The Magic: Merge Local and Remote Albums
    const mergeData = (local, remote) => {
        if (!local || !remote) {
            if (local) {
                // If only local, just show local albums
                const onlyLocal = (local.albums || []).map(a => ({
                    ...a,
                    origin: 'local',
                    tracks: a.tracks || [],
                    remoteTracks: 0,
                    year: a.year || 'Unknown'
                }));
                setMergedAlbums(onlyLocal);
            }
            return;
        }

        console.log("MergeData Input - Remote Albums:", remote.albums?.length || 0);

        // Robust normalization to match "Album (Deluxe)" with "Album"
        const normalize = (s) => String(s).toLowerCase()
            .replace(/\(.*\)/g, "") // match anything in Parens
            .replace(/\[.*\]/g, "") // match anything in Brackets
            .replace(/\b(deluxe|remaster(ed)?|edition|expanded|version)\b/g, "") // remove keywords
            .replace(/[^a-z0-9]/g, ""); // remove non-alphanumeric

        const merged = [];
        const remoteAlbums = remote.albums || [];
        const localAlbums = [...(local.albums || [])]; // Copy to allow removing items
        const consumedLocalIndices = new Set();

        // 1. Process Remote Albums
        remoteAlbums.forEach(rAlbum => {
            const rTitleNorm = normalize(rAlbum.title);
            let matchIndex = -1;

            // Strategy A: Exact ID Match (Primary)
            matchIndex = localAlbums.findIndex((l, idx) =>
                !consumedLocalIndices.has(idx) &&
                l.tidal_id &&
                String(l.tidal_id) === String(rAlbum.id)
            );

            // Strategy B: Title Match (Fallback) - ONLY if Local has NO ID
            if (matchIndex === -1) {
                matchIndex = localAlbums.findIndex((l, idx) =>
                    !consumedLocalIndices.has(idx) &&
                    !l.tidal_id && // Critical: Only match by title if local has NO explicit ID
                    normalize(l.title) === rTitleNorm
                );
            }

            if (matchIndex !== -1) {
                consumedLocalIndices.add(matchIndex);
                const lMatch = localAlbums[matchIndex];
                merged.push({
                    ...lMatch, // Local takes precedence for ID/path
                    remoteId: rAlbum.id,
                    remoteTracks: rAlbum.numberOfTracks,
                    cover: rAlbum.cover, // Use remote cover if available
                    origin: 'merged',
                    year: rAlbum.year || lMatch.year
                });
            } else {
                merged.push({
                    ...rAlbum,
                    remoteId: rAlbum.id,
                    origin: 'remote',
                    tracks: [] // No local tracks
                });
            }
        });

        // 2. Process remaining Local Albums (no remote match)
        localAlbums.forEach((lAlbum, idx) => {
            if (!consumedLocalIndices.has(idx)) {
                merged.push({
                    ...lAlbum,
                    origin: 'local',
                    remoteTracks: 0
                });
            }
        });

        // Sort by year desc
        merged.sort((a, b) => (parseInt(b.year) || 0) - (parseInt(a.year) || 0));

        console.log("Final Merged Albums:", merged.length);
        setMergedAlbums(merged);
    };

    if (loading && !localData) {
        return (
            <div class="flex items-center justify-center p-12">
                <div class="animate-spin text-primary text-2xl">⟳</div>
            </div>
        );
    }

    return (
        <div class="animate-fade-in p-6 pb-24 max-w-7xl mx-auto">
            {/* Header */}
            <div class="flex items-start gap-6 mb-8">
                <div class="w-32 h-32 rounded-full overflow-hidden shadow-lg bg-surface-alt flex-shrink-0 border-4 border-surface">
                    {remoteData?.artist.picture ? (
                        <img src={api.getCoverUrl(remoteData.artist.picture, 320)} class="w-full h-full object-cover" />
                    ) : localData.cover_path ? (
                        <img src={api.getLocalCoverUrl(localData.cover_path)} class="w-full h-full object-cover" />
                    ) : (
                        <div class="w-full h-full flex items-center justify-center bg-primary text-white text-3xl font-bold">
                            {artistName.charAt(0)}
                        </div>
                    )}
                </div>

                <div class="flex-1 mt-2">
                    <button onClick={onBack} class="mb-2 text-sm text-text-muted hover:text-text flex items-center gap-1 transition-colors">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                        Back to Library
                    </button>
                    <h1 class="text-4xl font-bold text-text mb-1">{artistName}</h1>
                    <div class="flex items-center gap-3 text-sm text-text-muted">
                        <span>{localData.albums.length} Local Albums</span>
                        {searchingTidal && <span class="flex items-center gap-1 text-primary"><span class="animate-spin">⟳</span> Syncing with Tidal...</span>}
                    </div>
                </div>
            </div>

            {/* Local / Merged Albums */}
            <section>
                <div class="flex items-center justify-between mb-4 px-2">
                    <h2 class="text-xl font-bold text-text">My Collection</h2>
                </div>
                <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    {mergedAlbums.filter(a => a.origin !== 'remote').map(album => (
                        <div
                            key={album.id || album.remoteId}
                            onClick={() => setSelectedAlbum(album)}
                            class={`group p-3 rounded-lg cursor-pointer border transition-all duration-200 hover:shadow-md
                       ${album.origin !== 'remote' ? 'bg-surface hover:bg-surface-alt border-transparent hover:border-border' : 'bg-surface/30 hover:bg-surface border-transparent hover:border-border'}
                    `}
                        >
                            <div class="aspect-square mb-3 rounded-md overflow-hidden bg-surface-alt shadow-sm relative">
                                {/* Cover Art Logic */}
                                {album.cover ? (
                                    <img src={api.getCoverUrl(album.cover, 320)} class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" loading="lazy" />
                                ) : album.cover_path ? (
                                    <img src={api.getLocalCoverUrl(album.cover_path)} class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" loading="lazy" />
                                ) : (
                                    <div class="w-full h-full flex items-center justify-center text-text-muted bg-surface-alt">
                                        <span class="text-xs">No Cover</span>
                                    </div>
                                )}

                                {/* Status Badges */}
                                <div class="absolute top-2 right-2 flex flex-col gap-1 items-end">
                                    {album.origin === 'merged' && album.remoteTracks > album.tracks.length && (
                                        <span class="bg-yellow-500/90 text-white text-[10px] px-2 py-0.5 rounded backdrop-blur-sm shadow-sm font-medium">
                                            {album.tracks.length}/{album.remoteTracks} Tracks
                                        </span>
                                    )}
                                    {album.origin === 'merged' && album.remoteTracks <= album.tracks.length && (
                                        <span class="bg-green-500/90 text-white text-[10px] px-1.5 py-0.5 rounded-full backdrop-blur-sm shadow-sm">
                                            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" /></svg>
                                        </span>
                                    )}
                                </div>

                                <div class="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded backdrop-blur-sm">
                                    {album.year}
                                </div>
                            </div>

                            <h3 class="font-bold text-sm text-text truncate group-hover:text-primary transition-colors" title={album.title}>{album.title}</h3>
                            <p class="text-xs text-text-muted flex items-center gap-1.5">
                                <span>{album.tracks.length} tracks</span>
                                {album.origin === 'merged' && album.remoteTracks > album.tracks.length && (
                                    <span class="text-yellow-600 dark:text-yellow-400 text-[10px]">• Incomplete</span>
                                )}
                            </p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Missing Albums */}
            {mergedAlbums.some(a => a.origin === 'remote') && (
                <section>
                    <div class="flex items-center justify-between mb-4 px-2 pt-4 border-t border-border/50">
                        <h2 class="text-xl font-bold text-text">Missing from Collection</h2>
                        <span class="text-sm text-text-muted">{mergedAlbums.filter(a => a.origin === 'remote').length} albums</span>
                    </div>
                    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                        {mergedAlbums.filter(a => a.origin === 'remote').map(album => (
                            <div
                                key={album.remoteId}
                                onClick={() => setSelectedAlbum(album)}
                                class="group p-3 rounded-lg cursor-pointer border border-transparent hover:border-border bg-surface/30 hover:bg-surface transition-all duration-200 hover:shadow-md"
                            >
                                <div class="aspect-square mb-3 rounded-md overflow-hidden bg-surface-alt shadow-sm relative">
                                    {album.cover ? (
                                        <img src={api.getCoverUrl(album.cover, 320)} class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105" loading="lazy" />
                                    ) : (
                                        <div class="w-full h-full flex items-center justify-center text-text-muted bg-surface-alt">No Cover</div>
                                    )}

                                    <div class="absolute top-2 right-2">
                                        <span class="bg-black/60 text-white text-[10px] px-2 py-0.5 rounded backdrop-blur-sm shadow-sm flex items-center gap-1">
                                            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                                            Missing
                                        </span>
                                    </div>
                                    <div class="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded backdrop-blur-sm">
                                        {album.year}
                                    </div>
                                </div>

                                <h3 class="font-bold text-sm text-text truncate group-hover:text-primary transition-colors" title={album.title}>{album.title}</h3>
                                <p class="text-xs text-text-muted">Available on Tidal</p>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {/* Unified Album Modal */}
            {selectedAlbum && (
                <UnifiedAlbumModal
                    album={selectedAlbum}
                    artistName={localData.name}
                    onClose={() => setSelectedAlbum(null)}
                    api={api}
                    downloadManager={downloadManager}
                    addToast={addToast}
                />
            )}
        </div>
    );
}

// ----------------------------------------------------------------------
// Unified Album Modal Component
// ----------------------------------------------------------------------

const UnifiedAlbumModal = ({ album, artistName, onClose, api, downloadManager, addToast }) => {
    const [tracks, setTracks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedIds, setSelectedIds] = useState(new Set());

    useEffect(() => {
        const loadContent = async () => {
            setLoading(true);
            try {
                // If it's a purely local album, we just use local tracks
                if (album.origin === 'local') {
                    setTracks(album.tracks.map(t => ({ ...t, isLocal: true, localPath: t.path })));
                    setLoading(false);
                    return;
                }

                // If we have a remote ID (Merged or Remote), fetch full tracklist from Tidal
                console.log("Fetching tracks for remoteId:", album.remoteId);
                const res = await api.getAlbumTracks(album.remoteId);
                console.log("Album Tracks Res:", res);
                const remoteItems = res.items || [];

                // Map remote tracks to local status
                const normalize = (s) => String(s).toLowerCase()
                    .replace(/\(.*\)/g, "")
                    .replace(/\[.*\]/g, "")
                    .replace(/\b(deluxe|remaster(ed)?|edition|expanded|version)\b/g, "")
                    .replace(/[^a-z0-9]/g, "");

                const localTracks = album.origin === 'merged' ? album.tracks : [];

                const mergedTracks = remoteItems.map(rt => {
                    const localMatch = localTracks.find(lt => normalize(lt.title) === normalize(rt.title));
                    return {
                        ...rt,
                        isLocal: !!localMatch,
                        localPath: localMatch?.path
                    };
                });

                setTracks(mergedTracks);

            } catch (err) {
                console.error("Failed to load album tracks:", err);
                addToast("Failed to load tracks", "error");
            } finally {
                setLoading(false);
            }
        };
        loadContent();
    }, [album]);

    const toggleSelection = (id) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) newSet.delete(id);
        else newSet.add(id);
        setSelectedIds(newSet);
    };

    const handleDownloadSelected = () => {
        const toDownload = tracks
            .filter(t => selectedIds.has(t.id) && !t.isLocal)
            .map(t => ({
                tidal_id: t.id,
                title: t.title,
                artist: t.artist?.name || artistName,
                album: album.title,
                cover: album.cover,
                track_number: t.trackNumber,
                album_artist: t.albumArtist || artistName,
                tidal_exists: true,
                tidal_track_id: t.id,
                tidal_artist_id: t.tidal_artist_id || t.artist?.id,
                tidal_album_id: t.tidal_album_id || t.album?.id || album.remoteId
            }));

        if (toDownload.length === 0) return;

        downloadManager.addToServerQueue(toDownload).then(res => {
            addToast(`Added ${res.added} tracks to queue`, "success");
            onClose();
        });
    };

    const handleDownloadAll = () => {
        if (!album.remoteId) {
            addToast("Cannot download local album", "error");
            return;
        }

        const toDownload = tracks
            .filter(t => !t.isLocal)
            .map(t => ({
                tidal_id: t.id,
                title: t.title,
                artist: t.artist?.name || artistName,
                album: album.title,
                cover: album.cover,
                track_number: t.trackNumber,
                album_artist: t.albumArtist || artistName,
                tidal_exists: true,
                tidal_track_id: t.id,
                tidal_artist_id: t.tidal_artist_id || t.artist?.id,
                tidal_album_id: t.tidal_album_id || t.album?.id || album.remoteId
            }));

        if (toDownload.length === 0) {
            addToast("All tracks already downloaded", "success");
            return;
        }

        downloadManager.addToServerQueue(toDownload).then(res => {
            addToast(`Added ${res.added} tracks to queue`, "success");
            onClose();
        });
    };

    const downloadCount = tracks.filter(t => selectedIds.has(t.id) && !t.isLocal).length;
    const missingCount = tracks.filter(t => !t.isLocal).length;

    return (
        <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
            <div class="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden">
                {/* Header */}
                <div class="p-6 border-b border-border flex gap-6 items-start bg-surface-alt/30">
                    <img
                        src={album.cover ? api.getCoverUrl(album.cover, 320) : (album.cover_path ? api.getLocalCoverUrl(album.cover_path) : null)}
                        class="w-32 h-32 rounded shadow-lg object-cover bg-surface-alt"
                    />
                    <div class="flex-1 min-w-0">
                        <h2 class="text-2xl font-bold text-text truncate">{album.title}</h2>
                        <p class="text-text-muted mb-2">{artistName} • {tracks.length} Tracks • {album.year}</p>

                        <div class="flex gap-2">
                            {album.origin === 'remote' && <span class="badge bg-primary/10 text-primary">On Tidal</span>}
                            {album.origin === 'local' && <span class="badge bg-surface text-text-muted border border-border">Local Only</span>}
                            {album.origin === 'merged' && <span class="badge bg-green-500/10 text-green-600 border border-green-500/20">Library + Tidal</span>}
                        </div>

                        {/* Download All Button */}
                        {missingCount > 0 && (
                            <button onClick={handleDownloadAll} class="btn-primary mt-2 text-xs self-start flex items-center gap-2">
                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                                Download All Missing ({missingCount})
                            </button>
                        )}
                    </div>

                    <button onClick={onClose} class="self-start p-2 rounded-full hover:bg-surface-alt transition-colors">
                        <svg class="w-6 h-6 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>

                {/* Tracklist */}
                <div class="flex-1 overflow-y-auto p-2">
                    {loading ? (
                        <div class="flex justify-center p-8"><div class="animate-spin text-primary">⟳</div></div>
                    ) : (
                        <div class="flex flex-col gap-1">
                            {tracks.map((track, i) => (
                                <div
                                    key={track.id}
                                    class={`flex items-center gap-3 p-2 rounded hover:bg-surface-alt/50 group ${track.isLocal ? 'opacity-75' : ''}`}
                                >
                                    <div class="w-8 text-center text-sm text-text-muted">{track.trackNumber}</div>
                                    <div class="flex-1 min-w-0">
                                        <div class="text-sm font-medium text-text truncate">{track.title}</div>
                                        <div class="text-xs text-text-muted flex items-center gap-2">
                                            {/* Quality Badge */}
                                            {track.audioQuality === 'HI_RES' && <span class="text-[10px] bg-yellow-500/10 text-yellow-500 px-1 rounded">MQA</span>}
                                            {track.audioQuality === 'LOSSLESS' && <span class="text-[10px] bg-cyan-500/10 text-cyan-500 px-1 rounded">HiFi</span>}
                                            {Math.floor(track.duration / 60)}:{(track.duration % 60).toString().padStart(2, '0')}
                                        </div>
                                    </div>

                                    {track.isLocal ? (
                                        <span class="text-xs bg-surface border border-border px-2 py-1 rounded text-text-muted flex items-center gap-1">
                                            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                            In Library
                                        </span>
                                    ) : (
                                        <button
                                            onClick={() => toggleSelection(track.id)}
                                            class={`p-1.5 rounded-full transition-colors ${selectedIds.has(track.id) ? 'bg-primary text-white' : 'hover:bg-surface border border-border text-text-muted'}`}
                                        >
                                            {selectedIds.has(track.id) ? (
                                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                                            ) : (
                                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                                            )}
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer Actions */}
                {downloadCount > 0 && (
                    <div class="p-4 border-t border-border bg-surface-alt/30 flex justify-end animate-slide-up">
                        <button onClick={handleDownloadSelected} class="btn-primary flex items-center gap-2">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                            Download Selected ({downloadCount})
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
