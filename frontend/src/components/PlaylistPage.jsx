import { h } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";

export function PlaylistPage({ playlistId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [playlist, setPlaylist] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [selectedTracks, setSelectedTracks] = useState(new Set());
  const [error, setError] = useState(null);

  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    loadPlaylistData();
  }, [playlistId]);

  const loadPlaylistData = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await api.getPlaylist(playlistId);

      setPlaylist(
        result.playlist || {
          id: playlistId,
          title: "Unknown Playlist",
        }
      );

      const items = result.items || [];
      setTracks(items);
      setSelectedTracks(new Set(items.map((t) => t.id)));
    } catch (err) {
      setError(err.message);
      addToast(`Failed to load playlist: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const toggleTrack = (trackId) => {
    const updated = new Set(selectedTracks);
    if (updated.has(trackId)) {
      updated.delete(trackId);
    } else {
      updated.add(trackId);
    }
    setSelectedTracks(updated);
  };

  const selectAll = () => setSelectedTracks(new Set(tracks.map((t) => t.id)));
  const deselectAll = () => setSelectedTracks(new Set());

  const handleDownloadTracks = () => {
    const selected = tracks.filter((t) => selectedTracks.has(t.id));

    if (selected.length === 0) {
      addToast("No tracks selected", "warning");
      return;
    }

    const payload = selected.map((t, idx) => ({
      tidal_id: t.id,
      title: t.title,
      artist: t.artist || "Unknown Artist",
      album: t.album,
      cover: t.cover || playlist?.cover,
      track_number: t.track_number || t.trackNumber || idx + 1,
      tidal_exists: true,
    }));

    downloadManager.addToServerQueue(payload).then((res) => {
      addToast(
        `Added ${res.added} track${res.added === 1 ? "" : "s"} to queue`,
        "success"
      );
    });
  };

  const totalDuration = tracks.reduce((sum, t) => sum + (t.duration || 0), 0);

  if (loading && !playlist) {
    return (
      <div class="space-y-6">
        <button class="btn-surface flex items-center gap-2" onClick={onBack}>
          <BackIcon />
          Back to Search
        </button>
        <div class="p-12 bg-primary/5 border border-primary/20 rounded-lg text-center">
          <div class="flex items-center justify-center gap-3">
            <div class="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <span class="text-base font-medium text-primary">
              Loading playlist...
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div class="space-y-6">
        <button class="btn-surface flex items-center gap-2" onClick={onBack}>
          <BackIcon />
          Back to Search
        </button>
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div class="space-y-6">
      <button class="btn-surface flex items-center gap-2" onClick={onBack}>
        <BackIcon />
        Back to Search
      </button>

      <div class="flex flex-col md:flex-row gap-6 p-6 bg-surface-alt rounded-lg border border-border-light">
        {playlist?.cover ? (
          <CoverWithFallback cover={playlist.cover} title={playlist?.title} />
        ) : (
          <div class="w-48 h-48 rounded-lg bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white text-4xl font-bold flex-shrink-0 shadow-md">
            {playlist?.title?.charAt(0) || "?"}
          </div>
        )}

        <div class="flex-1 flex flex-col justify-center space-y-3">
          <h2 class="text-2xl sm:text-3xl font-bold text-text">
            {playlist?.title || "Playlist"}
          </h2>
          {playlist?.creator && (
            <p class="text-lg text-text-muted">By {playlist.creator}</p>
          )}
          <div class="flex flex-wrap gap-4 text-sm text-text-muted">
            {tracks.length > 0 && <span>{tracks.length} tracks</span>}
            {totalDuration > 0 && (
              <>
                <span>•</span>
                <span>{formatTotalDuration(totalDuration)}</span>
              </>
            )}
          </div>
          {playlist?.description && (
            <p class="text-sm text-text-muted line-clamp-3">
              {playlist.description}
            </p>
          )}
        </div>
      </div>

      {tracks.length > 0 ? (
        <div class="space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 bg-surface-alt rounded-lg border border-border-light">
            <div class="flex flex-wrap gap-3">
              <button class="btn-surface text-sm" onClick={selectAll}>
                Select All
              </button>
              <button class="btn-surface text-sm" onClick={deselectAll}>
                Deselect All
              </button>
            </div>
            {selectedTracks.size > 0 && (
              <button class="btn-primary" onClick={handleDownloadTracks}>
                Add {selectedTracks.size} Track
                {selectedTracks.size !== 1 ? "s" : ""} to Queue
              </button>
            )}
          </div>

          <div class="space-y-2 max-h-[600px] overflow-y-auto">
            {tracks.map((track, idx) => {
              const isSelected = selectedTracks.has(track.id);
              const trackNumber =
                track.track_number || track.trackNumber || idx + 1;
              return (
                <label
                  key={track.id}
                  class="flex items-center gap-3 p-3 bg-surface-alt hover:bg-background-alt rounded-lg border border-border-light cursor-pointer transition-all duration-200"
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleTrack(track.id)}
                    class="w-4 h-4 text-primary focus:ring-primary rounded"
                  />
                  <span class="text-sm font-semibold text-text-muted w-8 flex-shrink-0">
                    {trackNumber}
                  </span>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-text truncate">
                      {track.title}
                    </p>
                    <p class="text-xs text-text-muted truncate">
                      {track.artist}
                      {track.duration && (
                        <span> • {formatDuration(track.duration)}</span>
                      )}
                    </p>
                  </div>
                  {track.quality && (
                    <span class="px-2 py-1 bg-primary text-white text-xs font-semibold rounded flex-shrink-0">
                      {track.quality}
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      ) : (
        <div class="text-center py-12">
          <svg
            class="w-16 h-16 mx-auto text-border mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
            />
          </svg>
          <p class="text-text-muted">No tracks found for this playlist</p>
        </div>
      )}
    </div>
  );
}

function CoverWithFallback({ cover, title }) {
  const variants = api.getCoverUrlVariants(cover);
  if (!variants.length) {
    return (
      <div class="w-48 h-48 rounded-lg bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white text-4xl font-bold flex-shrink-0 shadow-md">
        {title?.charAt(0) || "?"}
      </div>
    );
  }

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
      class="w-48 h-48 rounded-lg object-cover shadow-md flex-shrink-0"
    />
  );
}

function BackIcon() {
  return (
    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M10 19l-7-7m0 0l7-7m-7 7h18"
      />
    </svg>
  );
}

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

function formatTotalDuration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours} hr ${minutes} min`;
  }
  return `${minutes} min`;
}

