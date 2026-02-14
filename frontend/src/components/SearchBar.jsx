import { h } from "preact";
import { useState } from "preact/hooks";
import { api } from "../api/client";
import { downloadManager } from "../utils/downloadManager";
import { useToastStore } from "../stores/toastStore";
import { ArtistPage } from "./ArtistPage";
import { AlbumPage } from "./AlbumPage";
import { PlaylistPage } from "./PlaylistPage";

// Extract playlist UUID from a Tidal URL or raw UUID
function extractPlaylistUuid(input) {
  if (!input) return null;
  const trimmed = input.trim();

  // UUID pattern (8-4-4-4-12 format)
  const uuidPattern =
    /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;

  // Check if it's already a raw UUID
  if (uuidPattern.test(trimmed)) {
    return trimmed;
  }

  // Extract UUID from Tidal playlist URLs like:
  // https://tidal.com/playlist/45771c84-041e-454f-94ee-12b4d6a1374e
  // https://listen.tidal.com/playlist/45771c84-041e-454f-94ee-12b4d6a1374e
  const urlMatch = trimmed.match(
    /tidal\.com\/(?:browse\/)?playlist\/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/i,
  );
  if (urlMatch) {
    return urlMatch[1];
  }

  return null;
}

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("track");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [error, setError] = useState(null);
  const [directPlaylistId, setDirectPlaylistId] = useState(null);

  const addToast = useToastStore((state) => state.addToast);

  const handleSearchTypeChange = async (newType) => {
    const previousType = searchType;
    setSearchType(newType);

    setResults([]);
    setSelected(new Set());
    setError(null);

    if (query.trim() && previousType !== newType) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      handleSearch(newType);
    }
  };

  const handleSearch = async (overrideType) => {
    const activeType = overrideType || searchType;

    if (!query.trim()) {
      setError("Please enter a search query");
      return;
    }

    // For playlists: check if query is a URL or UUID and navigate directly
    if (activeType === "playlist") {
      const extractedUuid = extractPlaylistUuid(query);
      if (extractedUuid) {
        setDirectPlaylistId(extractedUuid);
        setResults([]);
        setError(null);
        addToast("Loading playlist from URL...", "info");
        return;
      }
    }

    setLoading(true);
    setError(null);
    setResults([]);
    setSelected(new Set());

    try {
      let result;
      if (activeType === "track") {
        result = await api.searchTracks(query.trim());
      } else if (activeType === "album") {
        result = await api.searchAlbums(query.trim());
      } else if (activeType === "artist") {
        result = await api.searchArtists(query.trim());
      } else {
        result = await api.searchPlaylists(query.trim());
      }

      setResults(result.items || []);

      if (result.items.length === 0) {
        setError("No results found");
        addToast("No results found for your search", "info");
      } else {
        addToast(
          `Found ${result.items.length} ${activeType}${
            result.items.length !== 1 ? "s" : ""
          }`,
          "success",
        );
      }
    } catch (err) {
      setError(err.message);
      addToast(`Search failed: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const toggleTrack = (trackId) => {
    const newSelected = new Set(selected);
    if (newSelected.has(trackId)) {
      newSelected.delete(trackId);
    } else {
      newSelected.add(trackId);
    }
    setSelected(newSelected);
  };

  const handleAddToQueue = () => {
    const selectedTracks = results
      .filter((r) => selected.has(r.id))
      .map((r) => ({
        tidal_id: r.id,
        title: r.title,
        artist: r.artist,
        album: r.album,
        cover: r.cover,
        track_number: r.trackNumber, // Pass track number from search results
        album_artist: r.albumArtist || r.artist, // Pass album artist
        tidal_exists: true,
        tidal_track_id: r.id,
        tidal_artist_id: r.tidal_artist_id,
        tidal_album_id: r.tidal_album_id,
      }));

    downloadManager.addToServerQueue(selectedTracks).then((result) => {
      addToast(`Added ${result.added} tracks to download queue`, "success");
    });
    setSelected(new Set());
  };

  // If a playlist URL/UUID was provided, render the PlaylistPage directly
  if (directPlaylistId) {
    return (
      <PlaylistPage
        playlistId={directPlaylistId}
        onBack={() => {
          setDirectPlaylistId(null);
          setQuery("");
        }}
      />
    );
  }

  return (
    <div class="space-y-6">
      <div class="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={query}
          onInput={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Search for tracks, albums, artists, or playlists..."
          disabled={loading}
          class="input-field flex-1"
        />
        <button
          onClick={() => handleSearch()}
          disabled={loading || !query.trim()}
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
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          )}
          Search
        </button>
      </div>

      <div class="grid grid-cols-4 gap-1.5 sm:flex sm:gap-3 p-2 sm:p-4 bg-surface-alt rounded-xl border border-border-light">
        {["track", "album", "artist", "playlist"].map((type) => (
          <label
            key={type}
            class={`flex flex-col sm:flex-row items-center justify-center sm:justify-start gap-1 sm:gap-3 px-2 sm:px-4 py-2 sm:py-2 rounded-lg cursor-pointer transition-all duration-200 ${
              searchType === type
                ? "bg-primary text-white shadow-sm"
                : "bg-surface hover:bg-background-alt border border-border"
            }`}
          >
            <input
              type="radio"
              name="type"
              value={type}
              checked={searchType === type}
              onChange={() => handleSearchTypeChange(type)}
              class="hidden"
            />
            <svg
              class="w-4 h-4 sm:w-5 sm:h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              {type === "track" && (
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"
                />
              )}
              {type === "album" && (
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              )}
              {type === "artist" && (
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              )}
              {type === "playlist" && (
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 6h16M4 12h10M4 18h7"
                />
              )}
            </svg>
            <span class="text-[10px] sm:text-sm font-medium capitalize">
              {type}
            </span>
          </label>
        ))}
      </div>

      {error && (
        <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p class="text-sm text-red-600">{error}</p>
        </div>
      )}

      {loading && (
        <div class="p-6 bg-primary/5 border border-primary/20 rounded-lg text-center">
          <div class="flex items-center justify-center gap-3">
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
            <span class="text-sm font-medium text-primary">
              Searching Tidal...
            </span>
          </div>
        </div>
      )}

      {searchType === "track" && results.length > 0 && (
        <TrackResults
          results={results}
          selected={selected}
          onToggle={toggleTrack}
          onAddToQueue={handleAddToQueue}
        />
      )}

      {searchType === "album" && results.length > 0 && (
        <AlbumResults results={results} />
      )}

      {searchType === "artist" && results.length > 0 && (
        <ArtistResults results={results} />
      )}

      {searchType === "playlist" && results.length > 0 && (
        <PlaylistResults results={results} />
      )}
    </div>
  );
}

function TrackResults({ results, selected, onToggle, onAddToQueue }) {
  return (
    <div class="space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h3 class="text-lg font-semibold text-text">
          Found {results.length} tracks
        </h3>
        {selected.size > 0 && (
          <button class="btn-primary" onClick={onAddToQueue}>
            Add {selected.size} to Queue
          </button>
        )}
      </div>

      <div class="space-y-3 max-h-[600px] overflow-y-auto">
        {results.map((track) => (
          <label
            key={track.id}
            class={`search-result-card ${
              selected.has(track.id) ? "selected" : ""
            }`}
          >
            <input
              type="checkbox"
              checked={selected.has(track.id)}
              onChange={() => onToggle(track.id)}
              class="custom-checkbox"
            />
            {track.cover && (
              <img
                src={api.getCoverUrl(track.cover, "80")}
                alt={track.title}
                class="w-14 h-14 rounded-lg object-cover flex-shrink-0 shadow-sm"
              />
            )}
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-text truncate">
                {track.title}
              </p>
              <p class="text-xs text-text-muted truncate mt-1">
                {track.artist}
                {track.album && ` • ${track.album}`}
              </p>
              {track.duration && (
                <p class="text-xs text-text-muted mt-1">
                  {formatDuration(track.duration)}
                </p>
              )}
            </div>
            {track.quality && (
              <span class="px-3 py-1 bg-primary text-white text-xs font-semibold rounded-full flex-shrink-0">
                {track.quality}
              </span>
            )}
          </label>
        ))}
      </div>
    </div>
  );
}

function AlbumResults({ results }) {
  const [selectedAlbumId, setSelectedAlbumId] = useState(null);

  if (selectedAlbumId) {
    return (
      <AlbumPage
        albumId={selectedAlbumId}
        onBack={() => setSelectedAlbumId(null)}
      />
    );
  }

  return (
    <div class="space-y-4">
      <h3 class="text-lg font-semibold text-text">
        Found {results.length} albums
      </h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {results.map((album) => (
          <div
            key={album.id}
            class="card-hover p-3"
            onClick={() => setSelectedAlbumId(album.id)}
          >
            {album.cover && (
              <img
                src={api.getCoverUrl(album.cover, "320")}
                alt={album.title}
                class="w-full aspect-square object-cover rounded-lg mb-3"
              />
            )}
            <div class="space-y-1">
              <p class="text-sm font-semibold text-text line-clamp-2">
                {album.title}
              </p>
              <p class="text-xs text-text-muted truncate">
                {album.artist?.name || "Unknown Artist"}
              </p>
              {album.numberOfTracks && (
                <p class="text-xs text-text-muted">
                  {album.numberOfTracks} tracks
                </p>
              )}
              {album.releaseDate && (
                <p class="text-xs text-text-muted">
                  {new Date(album.releaseDate).getFullYear()}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ArtistResults({ results }) {
  const [selectedArtistId, setSelectedArtistId] = useState(null);

  if (selectedArtistId) {
    return (
      <ArtistPage
        artistId={selectedArtistId}
        onBack={() => setSelectedArtistId(null)}
      />
    );
  }

  return (
    <div class="space-y-4">
      <h3 class="text-lg font-semibold text-text">
        Found {results.length} artists
      </h3>
      <div class="space-y-3">
        {results.map((artist) => (
          <div
            key={artist.id}
            class="flex items-center gap-4 p-4 card-hover"
            onClick={() => setSelectedArtistId(artist.id)}
          >
            {artist.picture ? (
              <img
                src={api.getCoverUrl(artist.picture, "160")}
                alt={artist.name}
                class="w-16 h-16 sm:w-20 sm:h-20 rounded-full object-cover flex-shrink-0"
                onError={(e) => {
                  e.target.style.display = "none";
                }}
              />
            ) : (
              <div class="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white text-2xl sm:text-3xl font-bold flex-shrink-0">
                {artist.name?.charAt(0) || "?"}
              </div>
            )}
            <div class="flex-1 min-w-0">
              <p class="text-base sm:text-lg font-semibold text-text truncate">
                {artist.name || "Unknown Artist"}
              </p>
              {artist.popularity && (
                <p class="text-xs text-text-muted mt-1">
                  Popularity: {artist.popularity}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlaylistResults({ results }) {
  const [selectedPlaylistId, setSelectedPlaylistId] = useState(null);

  if (selectedPlaylistId) {
    return (
      <PlaylistPage
        playlistId={selectedPlaylistId}
        onBack={() => setSelectedPlaylistId(null)}
      />
    );
  }

  return (
    <div class="space-y-4">
      <h3 class="text-lg font-semibold text-text">
        Found {results.length} playlists
      </h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
        {results.map((playlist) => (
          <div
            key={playlist.id}
            class="card-hover p-3"
            onClick={() => setSelectedPlaylistId(playlist.id)}
          >
            {playlist.cover ? (
              <PlaylistCoverImage
                cover={playlist.cover}
                title={playlist.title}
              />
            ) : null}
            <div class="space-y-1">
              <p class="text-sm font-semibold text-text line-clamp-2">
                {playlist.title}
              </p>
              {playlist.creator && (
                <p class="text-xs text-text-muted truncate">
                  By {playlist.creator}
                </p>
              )}
              {playlist.numberOfTracks && (
                <p class="text-xs text-text-muted">
                  {playlist.numberOfTracks} tracks
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlaylistCoverImage({ cover, title }) {
  const variants = api.getCoverUrlVariants(cover);
  const fallbackRef = useState(0)[0];

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
      class="w-full aspect-square object-cover rounded-lg mb-3"
    />
  );
}

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}
