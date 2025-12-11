
import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../api/client";
import { useToastStore } from "../stores/toastStore";
import { LibraryArtistPage } from "./LibraryArtistPage";

export function LibraryPage() {
    const [artists, setArtists] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedArtist, setSelectedArtist] = useState(null);
    const addToast = useToastStore((state) => state.addToast);

    useEffect(() => {
        loadLibrary();
    }, []);

    const loadLibrary = async (force = false) => {
        setLoading(true);
        try {
            const result = await api.scanLibrary(force);
            // If result is empty or we scanned, fetch the list
            const artistsList = await api.getLibraryArtists();
            setArtists(artistsList);
            if (force) {
                addToast("Library scan complete", "success");
            }
        } catch (err) {
            console.error("Failed to load library:", err);
            addToast("Failed to load library: " + err.message, "error");
        } finally {
            setLoading(false);
        }
    };

    if (selectedArtist) {
        return (
            <LibraryArtistPage
                artistName={selectedArtist.name}
                initialData={selectedArtist}
                onBack={() => setSelectedArtist(null)}
            />
        );
    }

    return (
        <div class="space-y-6 animate-fade-in">
            <div class="flex items-center justify-between">
                <h2 class="text-xl font-bold text-text">Your Library</h2>
                <button
                    onClick={() => loadLibrary(true)}
                    disabled={loading}
                    class="btn-surface flex items-center gap-2 text-sm"
                >
                    <svg
                        class={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                        />
                    </svg>
                    {loading ? "Scanning..." : "Rescan Library"}
                </button>
            </div>

            {loading && artists.length === 0 ? (
                <div class="flex flex-col items-center justify-center py-24 space-y-4">
                    <div class="w-10 h-10 border-3 border-primary border-t-transparent rounded-full animate-spin"></div>
                    <p class="text-text-muted">Scanning library files...</p>
                </div>
            ) : artists.length === 0 ? (
                <div class="text-center py-24 bg-surface-alt/30 rounded-xl border border-border-light border-dashed">
                    <div class="w-16 h-16 mx-auto bg-surface rounded-full flex items-center justify-center mb-4 text-text-muted">
                        <svg class="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                        </svg>
                    </div>
                    <h3 class="text-lg font-medium text-text mb-2">Library is Empty</h3>
                    <p class="text-text-muted max-w-sm mx-auto mb-6">
                        No music files found in your local directory. Download some music from the Search tab to populate your library.
                    </p>
                </div>
            ) : (
                <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                    {artists.map((artist) => (
                        <ArtistCard
                            key={artist.name}
                            artist={artist}
                            onClick={() => setSelectedArtist(artist)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

function ArtistCard({ artist, onClick }) {
    const [picture, setPicture] = useState(artist.picture);
    const [loadingImage, setLoadingImage] = useState(false);

    useEffect(() => {
        // Lazy load Tidal picture if missing
        if (!picture && !artist.image && artist.tidal_id) {
            setLoadingImage(true);
            api.getArtist(artist.tidal_id)
                .then(details => {
                    if (details.artist?.picture) {
                        setPicture(details.artist.picture);
                        // Persist to backend cache
                        api.updateLibraryArtist(artist.name, { picture: details.artist.picture })
                            .catch(e => console.warn("Failed to cache artist picture", e));
                    }
                })
                .catch(err => console.debug(`Failed to fetch picture for ${artist.name}`, err))
                .finally(() => setLoadingImage(false));
        }
    }, [artist]);

    // Determine which image to show
    // Priority: Tidal Picture (URL) > Local Image (Path)
    const imageUrl = picture
        ? api.getCoverUrl(picture, 320)
        : (artist.image ? api.getLocalCoverUrl(artist.image) : null);

    return (
        <div
            onClick={onClick}
            class="group cursor-pointer p-4 rounded-xl bg-surface-alt/50 hover:bg-surface-alt border border-transparent hover:border-border transition-all duration-200"
        >
            <div class="aspect-square mb-3 rounded-full overflow-hidden bg-surface shadow-sm group-hover:shadow-md transition-all relative">
                {imageUrl ? (
                    <img
                        src={imageUrl}
                        alt={artist.name}
                        class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                        onError={(e) => {
                            e.target.style.display = 'none';
                            e.target.nextSibling.style.display = 'flex';
                        }}
                    />
                ) : null}

                {/* Fallback / Loading State */}
                <div
                    class="w-full h-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center text-primary font-bold text-2xl absolute inset-0"
                    style={{ display: imageUrl ? 'none' : 'flex' }}
                >
                    {loadingImage ? (
                        <div class="animate-spin text-primary">⟳</div>
                    ) : (
                        artist.name.charAt(0)
                    )}
                </div>
            </div>
            <div class="text-center">
                <h3 class="font-bold text-text truncate group-hover:text-primary transition-colors">
                    {artist.name}
                </h3>
                <p class="text-xs text-text-muted mt-1">
                    {artist.album_count} albums • {artist.track_count} tracks
                </p>
            </div>
        </div>
    );
}
