import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../../api/client";
import { useToastStore } from "../../stores/toastStore";
import { DeleteFilesModal } from "./DeleteFilesModal";

export function MonitoredList() {
    const [playlists, setPlaylists] = useState([]);
    const [loading, setLoading] = useState(true);
    const [syncingMap, setSyncingMap] = useState({}); // uuid -> boolean
    const [editingId, setEditingId] = useState(null); // uuid of playlist being edited
    const [deleteModal, setDeleteModal] = useState({ isOpen: false, uuid: null, name: null });
    const addToast = useToastStore((state) => state.addToast);

    const fetchPlaylists = async () => {
        try {
            const res = await api.getMonitoredPlaylists();
            // Filter: Only show Tidal playlists (source == 'tidal' or undefined/null)
            const tidalPlaylists = res.filter(p => !p.source || p.source === 'tidal');
            setPlaylists(tidalPlaylists);
        } catch (e) {
            addToast(`Failed to load playlists: ${e.message}`, "error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchPlaylists();
    }, []);

    const handleSync = async (uuid) => {
        setSyncingMap((prev) => ({ ...prev, [uuid]: true }));
        try {
            await api.syncPlaylist(uuid);
            addToast("Sync started in background", "success");
            // Ideally we would poll or listen for progress, but for now just show started
            // We could update last_sync locally but server update is async.
            // Reload list after a delay?
            setTimeout(fetchPlaylists, 2000);
        } catch (e) {
            addToast(`Sync failed: ${e.message}`, "error");
        } finally {
            setSyncingMap((prev) => ({ ...prev, [uuid]: false }));
        }
    };

    const handleRemove = async (uuid) => {
        if (!confirm("Are you sure you want to stop monitoring this playlist? Files won't be deleted.")) return;
        try {
            await api.removeMonitoredPlaylist(uuid);
            setPlaylists((prev) => prev.filter((p) => p.uuid !== uuid));
            addToast("Playlist removed from monitoring", "success");
        } catch (e) {
            addToast(`Remove failed: ${e.message}`, "error");
        }
    };

    if (loading) {
        return (
            <div class="flex items-center justify-center p-12">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (playlists.length === 0) {
        return (
            <div class="text-center p-12 text-text-muted bg-surface-alt rounded-lg border border-dashed border-border">
                <p>No playlists are currently being monitored.</p>
                <p class="text-sm mt-2">Go to the "Search & Add" tab to start syncing a playlist.</p>
            </div>
        );
    }

    return (
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="border-b border-border bg-surface-alt">
                        <th class="p-4 font-medium text-text">Name</th>
                        <th class="p-4 font-medium text-text">Frequency</th>
                        <th class="p-4 font-medium text-text">Quality</th>
                        <th class="p-4 font-medium text-text">Last Sync</th>
                        <th class="p-4 font-medium text-text text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-border">
                    {playlists.map((playlist) => (
                        <tr key={playlist.uuid} class="hover:bg-surface-alt/50 transition-colors">
                            <td class="p-4">
                                <div class="font-medium text-text">{playlist.name}</div>
                                <div class="flex items-center gap-2 text-xs text-text-muted">
                                    <span>{playlist.track_count || 0} tracks</span>
                                </div>
                            </td>
                            <td class="p-4 capitalize">
                                {editingId === playlist.uuid ? (
                                    <select
                                        class="input-field text-xs py-1 px-2 pr-8"
                                        autoFocus
                                        value={playlist.sync_frequency}
                                        onBlur={() => setEditingId(null)}
                                        onChange={(e) => {
                                            const newFreq = e.target.value;
                                            // Optimistic update to UI to prevent flicker
                                            setPlaylists(prev => prev.map(p => p.uuid === playlist.uuid ? { ...p, sync_frequency: newFreq } : p));
                                            setEditingId(null);

                                            api.monitorPlaylist(
                                                playlist.uuid,
                                                playlist.name,
                                                newFreq,
                                                playlist.quality
                                            ).then(() => {
                                                addToast("Frequency updated", "success");
                                                fetchPlaylists(); // Refresh to be sure
                                            }).catch(err => {
                                                addToast(err.message, "error");
                                                fetchPlaylists(); // Revert on error
                                            });
                                        }}
                                    >
                                        <option value="manual">Manual</option>
                                        <option value="daily">Daily</option>
                                        <option value="weekly">Weekly</option>
                                        <option value="monthly">Monthly</option>
                                    </select>
                                ) : (
                                    <button
                                        onClick={() => setEditingId(playlist.uuid)}
                                        class={`inline-block px-2 py-1 text-xs rounded-full cursor-pointer hover:scale-105 transition-transform ${playlist.sync_frequency === 'manual' ? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' :
                                            'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                            }`}
                                        title="Click to change frequency"
                                    >
                                        {playlist.sync_frequency}
                                    </button>
                                )}
                            </td>
                            <td class="p-4 text-sm text-text-muted">{playlist.quality}</td>
                            <td class="p-4 text-sm text-text-muted">
                                {playlist.last_sync ? new Date(playlist.last_sync).toLocaleString() : "Never"}
                            </td>
                            <td class="p-4 text-right space-x-2">
                                <button
                                    onClick={() => handleSync(playlist.uuid)}
                                    disabled={syncingMap[playlist.uuid]}
                                    class="btn-sm btn-surface border border-border hover:border-primary hover:text-primary transition-colors"
                                >
                                    {syncingMap[playlist.uuid] ? "Started..." : "Sync"}
                                </button>
                                <button
                                    onClick={() => handleRemove(playlist.uuid)}
                                    class="btn-sm btn-surface border border-border hover:border-red-500 hover:text-red-500 transition-colors text-red-500/80"
                                >
                                    Stop
                                </button>

                                <button
                                    onClick={() => setDeleteModal({ isOpen: true, uuid: playlist.uuid, name: playlist.name })}
                                    class="p-2 btn-surface border border-border hover:border-red-500 hover:text-red-500 transition-colors text-red-500/80"
                                    title="Delete downloaded files"
                                >
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <DeleteFilesModal
                isOpen={deleteModal.isOpen}
                uuid={deleteModal.uuid}
                playlistName={deleteModal.name}
                onClose={() => setDeleteModal({ ...deleteModal, isOpen: false })}
            />
        </div >
    );
}
