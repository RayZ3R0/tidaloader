import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";

export function AlbumPage({ albumId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [album, setAlbum] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [selectedTracks, setSelectedTracks] = useState(new Set());
  const [error, setError] = useState(null);

  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    loadAlbumData();
  }, [albumId]);

  const loadAlbumData = async () => {
    setLoading(true);
    setError(null);

    try {
      console.log(`Loading album data for ID: ${albumId}`);
      const result = await api.get(`/album/${albumId}/tracks`);

      let albumInfo = null;

      if (result.album) {
        albumInfo = result.album;
      } else if (result.items && result.items.length > 0) {
        const firstTrack = result.items[0];

        if (firstTrack.album && typeof firstTrack.album === "object") {
          albumInfo = firstTrack.album;
        } else {
          albumInfo = {
            id: albumId,
            title: firstTrack.album || "Unknown Album",
            cover: firstTrack.cover,
            artist: firstTrack.artist ? { name: firstTrack.artist } : null,
          };
        }
      }

      setAlbum(
        albumInfo || {
          id: albumId,
          title: "Unknown Album",
          artist: { name: "Unknown Artist" },
        }
      );

      setTracks(result.items || []);

      if (result.items) {
        setSelectedTracks(new Set(result.items.map((t) => t.id)));
      }

      console.log(`Loaded album:`, albumInfo);
      console.log(`Loaded: ${result.items?.length || 0} tracks`);
    } catch (err) {
      console.error("Failed to load album:", err);
      setError(err.message);
      addToast(`Failed to load album: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const toggleTrack = (trackId) => {
    const newSelected = new Set(selectedTracks);
    if (newSelected.has(trackId)) {
      newSelected.delete(trackId);
    } else {
      newSelected.add(trackId);
    }
    setSelectedTracks(newSelected);
  };

  const selectAllTracks = () => {
    setSelectedTracks(new Set(tracks.map((t) => t.id)));
  };

  const deselectAllTracks = () => {
    setSelectedTracks(new Set());
  };

  const handleDownloadTracks = () => {
    const selectedTrackList = tracks
      .filter((t) => selectedTracks.has(t.id))
      .map((t, index) => ({
        tidal_id: t.id,
        title: t.title,
        artist: t.artist || album?.artist?.name || "Unknown Artist",
        album: album?.title || t.album,
        album_artist: t.albumArtist || album?.artist?.name, // Use backend albumArtist or fallback
        track_number: t.trackNumber || t.track_number || (index + 1),
        cover: album?.cover || t.cover,
        tidal_exists: true,
        tidal_track_id: t.id,
        tidal_artist_id: t.tidal_artist_id || album?.artist?.id,
        tidal_album_id: t.tidal_album_id || album?.id,
      }));

    downloadManager.addToServerQueue(selectedTrackList).then(result => {
      addToast(
        `Added ${result.added} tracks to download queue`,
        "success"
      );
    });
  };

  if (loading && !album) {
    return (
      <div class="space-y-6">
        <button class="btn-surface flex items-center gap-2" onClick={onBack}>
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
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          Back to Search
        </button>
        <div class="p-12 bg-primary/5 border border-primary/20 rounded-lg text-center">
          <div class="flex items-center justify-center gap-3">
            <svg
              class="animate-spin h-6 w-6 text-primary"
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
            <span class="text-base font-medium text-primary">
              Loading album...
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
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          Back to Search
        </button>
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  if (!album && tracks.length === 0) {
    return (
      <div class="space-y-6">
        <button class="btn-surface flex items-center gap-2" onClick={onBack}>
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
              d="M10 19l-7-7m0 0l7-7m-7 7h18"
            />
          </svg>
          Back to Search
        </button>
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-600">Album not found</p>
        </div>
      </div>
    );
  }

  const totalDuration = tracks.reduce((sum, t) => sum + (t.duration || 0), 0);

  return (
    <div class="space-y-6">
      <button class="btn-surface flex items-center gap-2" onClick={onBack}>
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
            d="M10 19l-7-7m0 0l7-7m-7 7h18"
          />
        </svg>
        Back to Search
      </button>

      <div class="flex flex-col md:flex-row gap-6 p-6 bg-surface-alt rounded-lg border border-border-light">
        {album?.cover ? (
          <img
            src={api.getCoverUrl(album.cover, "320")}
            alt={album.title}
            class="w-48 h-48 rounded-lg object-cover shadow-md flex-shrink-0"
          />
        ) : (
          <div class="w-48 h-48 rounded-lg bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white text-6xl font-bold flex-shrink-0 shadow-md">
            {album?.title?.charAt(0) || "?"}
          </div>
        )}

        <div class="flex-1 flex flex-col justify-center space-y-3">
          <h2 class="text-2xl sm:text-3xl font-bold text-text">
            {album?.title || "Unknown Album"}
          </h2>
          <p class="text-lg text-text-muted">
            {album?.artist?.name || "Unknown Artist"}
          </p>
          <div class="flex flex-wrap gap-4 text-sm text-text-muted">
            {album?.releaseDate && (
              <span>{new Date(album.releaseDate).getFullYear()}</span>
            )}
            {tracks.length > 0 && (
              <>
                {album?.releaseDate && <span>•</span>}
                <span>{tracks.length} tracks</span>
              </>
            )}
            {totalDuration > 0 && (
              <>
                <span>•</span>
                <span>{formatTotalDuration(totalDuration)}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {tracks.length > 0 && (
        <div class="space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 bg-surface-alt rounded-lg border border-border-light">
            <div class="flex flex-wrap gap-3">
              <button class="btn-surface text-sm" onClick={selectAllTracks}>
                Select All
              </button>
              <button class="btn-surface text-sm" onClick={deselectAllTracks}>
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
            {tracks.map((track, index) => (
              <label
                key={track.id}
                class="flex items-center gap-3 p-3 bg-surface-alt hover:bg-background-alt rounded-lg border border-border-light cursor-pointer transition-all duration-200"
              >
                <input
                  type="checkbox"
                  checked={selectedTracks.has(track.id)}
                  onChange={() => toggleTrack(track.id)}
                  class="w-4 h-4 text-primary focus:ring-primary rounded"
                />
                <span class="text-sm font-semibold text-text-muted w-8 flex-shrink-0">
                  {index + 1}
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
            ))}
          </div>
        </div>
      )}

      {tracks.length === 0 && (
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
          <p class="text-text-muted">No tracks found for this album</p>
        </div>
      )}
    </div>
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
