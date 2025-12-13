import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";

export function ArtistPage({ artistId, onBack }) {
  const [loading, setLoading] = useState(true);
  const [artist, setArtist] = useState(null);
  const [topTracks, setTopTracks] = useState([]);
  const [albums, setAlbums] = useState([]);
  const [selectedTracks, setSelectedTracks] = useState(new Set());
  const [selectedAlbums, setSelectedAlbums] = useState(new Set());
  const [modalAlbum, setModalAlbum] = useState(null);
  const [error, setError] = useState(null);

  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    loadArtistData();
  }, [artistId]);

  const loadArtistData = async () => {
    setLoading(true);
    setError(null);

    try {
      console.log(`Loading artist data for ID: ${artistId}`);
      const result = await api.get(`/artist/${artistId}`);

      setArtist(result.artist || {});
      setTopTracks(result.tracks || []);
      setAlbums(result.albums || []);

      if (result.tracks) {
        setSelectedTracks(new Set(result.tracks.map((t) => t.id)));
      }

      console.log(
        `Loaded: ${result.tracks?.length || 0} tracks, ${result.albums?.length || 0
        } albums`
      );
    } catch (err) {
      console.error("Failed to load artist:", err);
      setError(err.message);
      addToast(`Failed to load artist: ${err.message}`, "error");
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

  const toggleAlbum = (albumId) => {
    const newSelected = new Set(selectedAlbums);
    if (newSelected.has(albumId)) {
      newSelected.delete(albumId);
    } else {
      newSelected.add(albumId);
    }
    setSelectedAlbums(newSelected);
  };

  const selectAllTracks = () => {
    setSelectedTracks(new Set(topTracks.map((t) => t.id)));
  };

  const deselectAllTracks = () => {
    setSelectedTracks(new Set());
  };

  const selectAllAlbums = () => {
    setSelectedAlbums(new Set(albums.map((a) => a.id)));
  };

  const deselectAllAlbums = () => {
    setSelectedAlbums(new Set());
  };

  const handleDownloadTracks = () => {
    const tracks = topTracks
      .filter((t) => selectedTracks.has(t.id))
      .map((t) => ({
        tidal_id: t.id,
        title: t.title,
        artist: t.artist?.name || artist.name,
        album: t.album?.title,
        cover: t.album?.cover,
        track_number: t.trackNumber,
        tidal_exists: true,
        tidal_track_id: t.id,
        tidal_artist_id: t.artist?.id || artistId,
        tidal_album_id: t.album?.id,
        album_artist: t.album?.artist?.name, // From Top Tracks album info
      }));

    downloadManager.addToServerQueue(tracks).then(result => {
      addToast(`Added ${result.added} tracks to download queue`, "success");
    });
  };

  const handleDownloadAlbums = async () => {
    const albumsToDownload = albums.filter((a) => selectedAlbums.has(a.id));

    if (albumsToDownload.length === 0) {
      addToast("No albums selected", "warning");
      return;
    }

    setLoading(true);
    let totalTracks = 0;

    try {
      for (const album of albumsToDownload) {
        console.log(`Fetching tracks for album: ${album.title}`);
        const result = await api.get(`/album/${album.id}/tracks`);

        const tracks = (result.items || []).map((t, index) => ({
          tidal_id: t.id,
          title: t.title,
          artist: t.artist || album.artist?.name || artist.name,
          album: album.title,
          cover: album.cover,
          track_number: t.trackNumber || index + 1,
          tidal_exists: true,
          tidal_track_id: t.id,
          tidal_artist_id: t.tidal_artist_id || t.artist?.id,
          tidal_album_id: t.tidal_album_id || album.id,
          album_artist: album.artist?.name,
        }));

        const res = await downloadManager.addToServerQueue(tracks);
        totalTracks += res.added;
      }

      addToast(
        `Added ${totalTracks} tracks from ${albumsToDownload.length} albums to queue`,
        "success"
      );
      setSelectedAlbums(new Set());
    } catch (err) {
      addToast(`Failed to fetch album tracks: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadDiscography = async () => {
    if (albums.length === 0) {
      addToast("No albums found for this artist", "warning");
      return;
    }

    setLoading(true);
    let totalTracks = 0;

    try {
      addToast(
        `Downloading entire discography (${albums.length} albums)...`,
        "info"
      );

      for (const album of albums) {
        console.log(`Fetching tracks for album: ${album.title}`);
        const result = await api.get(`/album/${album.id}/tracks`);

        const tracks = (result.items || []).map((t, index) => ({
          tidal_id: t.id,
          title: t.title,
          artist: t.artist || album.artist?.name || artist.name,
          album: album.title,
          cover: album.cover,
          track_number: t.trackNumber || index + 1,
          tidal_exists: true,
          tidal_track_id: t.id,
          tidal_artist_id: t.tidal_artist_id || t.artist?.id,
          tidal_album_id: t.tidal_album_id || album.id,
          album_artist: album.artist?.name,
        }));

        const res = await downloadManager.addToServerQueue(tracks);
        totalTracks += res.added;

        await new Promise((resolve) => setTimeout(resolve, 200));
      }

      addToast(
        `Added entire discography: ${totalTracks} tracks from ${albums.length} albums`,
        "success"
      );
    } catch (err) {
      addToast(`Failed to fetch discography: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  if (loading && !artist) {
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
              Loading artist...
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

  if (!artist) {
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
          <p class="text-sm text-red-600">Artist not found</p>
        </div>
      </div>
    );
  }

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
        {artist.picture ? (
          <img
            src={api.getCoverUrl(artist.picture, "320")}
            alt={artist.name}
            class="w-48 h-48 rounded-full object-cover shadow-md flex-shrink-0"
          />
        ) : (
          <div class="w-48 h-48 rounded-full bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white text-6xl font-bold flex-shrink-0 shadow-md">
            {artist.name?.charAt(0) || "?"}
          </div>
        )}

        <div class="flex-1 flex flex-col justify-center space-y-3">
          <h2 class="text-2xl sm:text-3xl font-bold text-text">
            {artist.name}
          </h2>
          {artist.popularity && (
            <p class="text-base text-text-muted">
              Popularity: {artist.popularity}
            </p>
          )}
          {albums.length > 0 && (
            <button
              class="btn-primary self-start"
              onClick={handleDownloadDiscography}
              disabled={loading}
            >
              Download Entire Discography ({albums.length} albums)
            </button>
          )}
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {topTracks.length > 0 && (
          <div class={`space-y-4 hidden md:block ${albums.length > 0 ? 'lg:col-span-5' : 'lg:col-span-12'}`}>
            <div class="flex items-center justify-between">
              <h3 class="text-xl font-bold text-text">
                Top Tracks ({topTracks.length})
              </h3>
            </div>

            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 bg-surface-alt rounded-lg border border-border-light">
              <div class="flex flex-wrap gap-2">
                <button class="btn-surface text-xs px-3 py-1.5" onClick={selectAllTracks}>
                  Select All
                </button>
                <button class="btn-surface text-xs px-3 py-1.5" onClick={deselectAllTracks}>
                  Deselect
                </button>
              </div>
              {selectedTracks.size > 0 && (
                <button class="btn-primary text-xs px-3 py-1.5" onClick={handleDownloadTracks}>
                  Add {selectedTracks.size} to Queue
                </button>
              )}
            </div>

            <div class="space-y-4">
              <div class={`grid gap-2 ${albums.length > 0 ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-1' : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'}`}>
                {topTracks.map((track) => {
                  const isSelected = selectedTracks.has(track.id);
                  return (
                    <div
                      key={track.id}
                      onClick={() => toggleTrack(track.id)}
                      class={`
                      group relative flex items-center gap-2.5 p-2 rounded-lg transition-all duration-200 cursor-pointer border
                      ${isSelected
                          ? "bg-primary/5 border-primary/30"
                          : "bg-surface-alt/30 hover:bg-surface-alt border-transparent hover:border-border"}
                    `}
                    >
                      <div class="relative flex-shrink-0">
                        {track.album?.cover ? (
                          <img
                            src={api.getCoverUrl(track.album.cover, "80")}
                            alt={track.title}
                            class={`w-10 h-10 rounded-md object-cover shadow-sm transition-transform duration-200 ${isSelected ? "opacity-100" : "group-hover:opacity-90"}`}
                          />
                        ) : (
                          <div class="w-10 h-10 rounded-md bg-surface flex items-center justify-center text-text-muted">
                            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                            </svg>
                          </div>
                        )}
                      </div>

                      <div class="flex-1 min-w-0 pr-1">
                        <p class={`text-sm font-semibold truncate leading-tight transition-colors duration-200 ${isSelected ? "text-primary" : "text-text group-hover:text-primary"}`}>
                          {track.title}
                        </p>
                        <div class="flex items-center gap-1.5 text-[11px] text-text-muted mt-0.5 leading-tight">
                          <span class="truncate max-w-[100px]" title={track.album?.title}>{track.album?.title || "Unknown"}</span>
                          {track.duration && (
                            <>
                              <span class="text-border">•</span>
                              <span>{formatDuration(track.duration)}</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Selection Checkmark */}
                      {isSelected && (
                        <div class="flex-shrink-0 text-primary">
                          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}

                      {!isSelected && track.audioQuality && track.audioQuality !== "LOSSLESS" && (
                        <div class="flex-shrink-0 self-center">
                          <span class="px-1 py-0.5 bg-surface text-[9px] font-bold text-text-muted uppercase rounded border border-border/50">
                            {track.audioQuality === "HI_RES" ? "Hi-Res" : "High"}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {albums.length > 0 && (
          <div class={`space-y-4 ${topTracks.length > 0 ? 'lg:col-span-7' : 'lg:col-span-12'}`}>
            <div class="flex items-center justify-between">
              <h3 class="text-xl font-bold text-text">
                Albums ({albums.length})
              </h3>
            </div>

            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 bg-surface-alt rounded-lg border border-border-light">
              <div class="flex flex-wrap gap-2">
                <button class="btn-surface text-xs px-3 py-1.5" onClick={selectAllAlbums}>
                  Select All
                </button>
                <button class="btn-surface text-xs px-3 py-1.5" onClick={deselectAllAlbums}>
                  Deselect
                </button>
              </div>
              {selectedAlbums.size > 0 && (
                <button
                  class="btn-primary text-xs px-3 py-1.5"
                  onClick={handleDownloadAlbums}
                  disabled={loading}
                >
                  Add {selectedAlbums.size} Albums to Queue
                </button>
              )}
            </div>

            <div class={`grid gap-4 ${topTracks.length > 0 ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5'}`}>
              {albums.map((album) => {
                const isSelected = selectedAlbums.has(album.id);
                return (
                  <div
                    key={album.id}
                    onClick={() => toggleAlbum(album.id)}
                    class={`
                      group relative p-3 rounded-xl cursor-pointer transition-all duration-200 border
                      ${isSelected
                        ? "bg-primary/5 border-primary/30 shadow-sm ring-1 ring-primary/20"
                        : "bg-surface-alt/30 border-transparent hover:bg-surface-alt hover:border-border/50"}
                    `}
                  >
                    <div class="relative w-full aspect-square mb-3">
                      {album.cover ? (
                        <img
                          src={api.getCoverUrl(album.cover, "320")}
                          alt={album.title}
                          class="w-full h-full object-cover rounded-lg shadow-sm"
                        />
                      ) : (
                        <div class="w-full h-full rounded-lg bg-surface flex items-center justify-center">
                          <span class="text-text-muted text-xs">No Cover</span>
                        </div>
                      )}

                      {/* Selection Overlay Badge */}
                      <div class={`
                        absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center shadow-md transition-all duration-200
                        ${isSelected
                          ? "bg-primary text-white scale-100 opacity-100"
                          : "bg-black/40 text-white/50 scale-90 opacity-0 group-hover:opacity-100"}
                      `}>
                        {isSelected ? (
                          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <div class="w-4 h-4 rounded-full border-2 border-white/50"></div>
                        )}
                      </div>

                      {/* Inspect Button - Desktop Only */}
                      <div
                        onClick={(e) => { e.stopPropagation(); setModalAlbum(album); }}
                        class="hidden md:flex absolute bottom-2 left-2 w-8 h-8 rounded-full bg-black/40 hover:bg-primary hover:text-white backdrop-blur-sm items-center justify-center text-white/80 transition-all transform scale-90 hover:scale-100 opacity-0 group-hover:opacity-100 z-10"
                        title="View Tracks"
                      >
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                        </svg>
                      </div>
                    </div>

                    <div class="space-y-1">
                      <p class={`text-sm font-semibold line-clamp-2 leading-tight transition-colors ${isSelected ? "text-primary" : "text-text"}`}>
                        {album.title}
                      </p>
                      <div class="flex items-center gap-2 text-xs text-text-muted">
                        {album.releaseDate && (
                          <span>{new Date(album.releaseDate).getFullYear()}</span>
                        )}
                        {album.numberOfTracks && (
                          <>
                            <span class="w-1 h-1 rounded-full bg-border"></span>
                            <span>{album.numberOfTracks} tracks</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {topTracks.length === 0 && albums.length === 0 && (
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
          <p class="text-text-muted">
            No tracks or albums found for this artist
          </p>
        </div>
      )}
      {modalAlbum && (
        <AlbumTracksModal
          album={modalAlbum}
          onClose={() => setModalAlbum(null)}
        />
      )}
    </div>
  );
}

function AlbumTracksModal({ album, onClose }) {
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    const fetchTracks = async () => {
      try {
        const result = await api.get(`/album/${album.id}/tracks`);
        const items = result.items || [];
        setTracks(items);
        // Select all by default
        setSelectedIds(new Set(items.map(t => t.id)));
      } catch (err) {
        addToast(`Failed to load tracks: ${err.message}`, "error");
        onClose();
      } finally {
        setLoading(false);
      }
    };
    fetchTracks();
  }, [album.id]);

  const toggleTrack = (id) => {
    const newSet = new Set(selectedIds);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedIds(newSet);
  };

  const handleDownload = () => {
    const tracksToDownload = tracks
      .filter(t => selectedIds.has(t.id))
      .map((t, index) => ({
        tidal_id: t.id,
        title: t.title,
        artist: t.artist || album.artist?.name,
        album: album.title,
        cover: album.cover,
        track_number: t.trackNumber || index + 1,
        tidal_exists: true,
        tidal_track_id: t.id,
        tidal_artist_id: t.tidal_artist_id || album.artist?.id,
        tidal_album_id: t.tidal_album_id || album.id,
        album_artist: t.albumArtist || album.artist?.name, // Use backend albumArtist or fallback to album.artist
      }));

    downloadManager.addToServerQueue(tracksToDownload).then(res => {
      addToast(`Added ${res.added} tracks to queue`, "success");
      onClose();
    });
  };

  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div class="w-full max-w-3xl bg-surface border border-border rounded-xl shadow-2xl flex flex-col max-h-[85vh] animate-scale-up overflow-hidden">

        {/* Header */}
        <div class="p-4 border-b border-border/50 flex items-center justify-between bg-surface-alt/50">
          <div class="flex items-center gap-4">
            {album.cover && (
              <img
                src={api.getCoverUrl(album.cover, "160")}
                alt={album.title}
                class="w-16 h-16 rounded-lg shadow-sm object-cover"
              />
            )}
            <div>
              <h3 class="text-lg font-bold text-text line-clamp-1">{album.title}</h3>
              <p class="text-xs text-text-muted">
                {tracks.length} tracks
                {album.releaseDate && !isNaN(new Date(album.releaseDate)) && ` • ${new Date(album.releaseDate).getFullYear()}`}
              </p>
            </div>
          </div>
          <button onClick={onClose} class="p-2 hover:bg-surface-alt rounded-full text-text-muted hover:text-text transition-colors">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Toolbar */}
        <div class="p-3 border-b border-border/50 flex items-center justify-between bg-surface">
          <div class="flex gap-2">
            <button
              onClick={() => setSelectedIds(new Set(tracks.map(t => t.id)))}
              class="text-xs font-medium px-3 py-1.5 rounded-md hover:bg-surface-alt text-text transition-colors"
            >
              Select All
            </button>
            <button
              onClick={() => setSelectedIds(new Set())}
              class="text-xs font-medium px-3 py-1.5 rounded-md hover:bg-surface-alt text-text transition-colors"
            >
              Deselect
            </button>
          </div>
          {selectedIds.size > 0 && (
            <button
              onClick={handleDownload}
              class="btn-primary text-xs px-4 py-1.5 flex items-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Add {selectedIds.size} Tracks
            </button>
          )}
        </div>

        {/* Track List */}
        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar bg-surface/50">
          {loading ? (
            <div class="flex flex-col items-center justify-center py-12 space-y-3">
              <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
              <p class="text-sm text-text-muted">Loading tracks...</p>
            </div>
          ) : (
            <div class="grid gap-2">
              {tracks.map((track) => {
                const isSelected = selectedIds.has(track.id);
                return (
                  <div
                    key={track.id}
                    onClick={() => toggleTrack(track.id)}
                    class={`
                      flex items-center gap-2 p-2 rounded-lg cursor-pointer border transition-all duration-150
                      ${isSelected
                        ? "bg-primary/5 border-primary/30"
                        : "bg-surface hover:bg-surface-alt border-transparent hover:border-border"}
                    `}
                  >
                    <span class="w-6 text-center text-xs text-text-muted font-medium flex-shrink-0">
                      {track.trackNumber}
                    </span>

                    <div class="relative flex-shrink-0 mr-1">
                      {album.cover ? (
                        <img
                          src={api.getCoverUrl(album.cover, "80")}
                          alt={album.title}
                          class={`w-10 h-10 rounded-md object-cover shadow-sm transition-opacity duration-200 ${isSelected ? "opacity-100" : "opacity-90"}`}
                        />
                      ) : (
                        <div class="w-10 h-10 rounded-md bg-surface-alt flex items-center justify-center text-text-muted">
                          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                          </svg>
                        </div>
                      )}
                    </div>

                    <div class="flex-1 min-w-0">
                      <p class={`text-sm font-medium truncate ${isSelected ? "text-primary" : "text-text"}`}>
                        {track.title}
                      </p>
                      <div class="flex items-center gap-2 text-[10px] text-text-muted">
                        <span>{formatDuration(track.duration)}</span>
                        {track.audioQuality && track.audioQuality !== "LOSSLESS" && (
                          <span class="px-1 py-0.5 rounded border border-border/50 text-[9px]">
                            {track.audioQuality}
                          </span>
                        )}
                      </div>
                    </div>

                    <div class={`w-5 h-5 rounded-full border flex items-center justify-center transition-colors ${isSelected ? "bg-primary border-primary text-white" : "border-text-muted/30 text-transparent"}`}>
                      <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}
