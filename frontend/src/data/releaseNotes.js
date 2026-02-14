export const releaseNotes = [
    {
        version: "1.4.0",
        date: "2026-02-14",
        title: "Settings System Overhaul & Multi-User Support + Performance Boost",
        changes: [
            "Major Backend Upgrade: Migrated settings storage from config.json to SQLite for improved reliability and performance.",
            "Multi-User Safety: Implemented optimistic concurrency control with version tracking to prevent conflicts when multiple users modify settings simultaneously.",
            "Enhanced User Experience: Auto-save functionality for toggle switches (MusicBrainz, Beets, Lyrics) with inline saving indicators.",
            "Visual Feedback: Added toast notifications for save success, errors, and conflict resolution.",
            "Centralized Quality Setting: Download quality preference now syncs across all browsers and users instead of being stored per-browser.",
            "Conflict Resolution: When settings are changed by another user, you'll receive a clear warning with the option to reload the latest values.",
            "Improved Settings Architecture: Backend proxy pattern ensures backward compatibility while enabling modern database-backed configuration.",
            "Database Migration: Automatic one-time migration from config.json to SQLite on first startup with backup creation.",
            "Queue Pagination: Completed tracks now display accurate total counts and support infinite scroll to view all download history (previously limited to 50 items).",
            "Clear View Button: 'Clear View' button now only clears the UI display while preserving all download history in the database.",
            "Performance Boost: Fixed 11s delay in queue processing by optimizing sticky endpoint logic with fail-fast validation.",
            "Bug Fix: Resolved issue where download quality setting was ignored on app startup."
        ]
    },
    {
        version: "1.3.3",
        date: "2026-01-19",
        title: "Spotify Polling Fix",
        changes: [
            "Fixed Spotify playlist import progress polling by aligning backend service with polling router."
        ]
    },
    {
        version: "1.3.2",
        date: "2026-01-19",
        title: "Spotify Monitoring & Enhancements",
        changes: [
            "New Feature: Monitored Playlists for Spotify! Search, subscribe, and auto-sync Spotify playlists.",
            "Revised Manual Import: Dedicated tab for Spotify URL imports with secure polling connections.",
            "Jellyfin Sync: Added 'Sync Covers' button to force re-upload playlist covers without full rescans.",
            "Enhanced Spotify Search: Search by playlist name directly from the UI.",
            "Backend Stability: Fixed circular dependencies and improved endpoint validation logic.",
            "Fixed connection dropouts during manual playlist imports."
        ]
    },
    {
        version: "1.3.1",
        date: "2026-01-01",
        title: "Standardized Lyrics & Compatibility Fixes",
        changes: [
            "Improved Tagging: Synced lyrics are now correctly embedded in SYNCEDLYRICS (FLAC/Opus) and SYLT (MP3) tags.",
            "Enhanced Plain Lyrics: Unsynced lyrics now use standard LYRICS (FLAC/Opus) and USLT (MP3) metadata frames.",
            "Fixed non-standard lyrics tagging that caused issues with external media servers."
        ]
    },
    {
        version: "1.3.0",
        date: "2026-01-01",
        title: "Jellyfin Integration & Enhanced Settings",
        changes: [
            "New Feature: Jellyfin Server Integration! Sync cover art and metadata to your Jellyfin library.",
            "Automated ListenBrainz sync per Jellyfin user for seamless integration.",
            "Dynamic cover art generator for ListenBrainz playlists with customizable themes.",
            "Enhanced M3U8 playlists with source metadata headers for better compatibility.",
            "Improved Settings UI with organized card-based sections and manual save workflow.",
            "MusicBrainz Tagging now integrated in the new Settings layout.",
            "MusicBrainz and Beets tagging are mutually exclusive for optimal metadata quality."
        ]
    },
    {
        version: "1.2.7",
        date: "2025-12-31",
        title: "MusicBrainz Integration & Quality Improvements",
        changes: [
            "New Feature: MusicBrainz Integration! Fetch accurate metadata (genre, ISRC, MBIDs, Label) for all downloads.",
            "Fixed HI_RES quality fallback: Now validates stream URLs to prevent XML errors and auto-falls back to LOSSLESS.",
            "Increased download timeouts to 30 minutes for large FLAC albums.",
            "Cleaned up Vorbis comments (FLAC/Opus) by removing non-standard YEAR tags.",
            "Temporarily disabled Library feature pending improvements."
        ]
    },
    {
        version: "1.2.6",
        date: "2025-12-21",
        title: "Mobile Responsive UI",
        changes: [
            "Complete mobile responsiveness overhaul - all pages now work great on phones and tablets.",
            "Redesigned navigation tabs with compact labels and horizontal scrolling on mobile.",
            "Improved Release Notes modal with full-screen mobile layout and proper safe areas.",
            "Enhanced Download Queue popout with better mobile button sizing and panel layout.",
            "Fixed Search type selector (Track/Album/Artist/Playlist) with 4-column grid on mobile.",
            "Improved Tidal Playlists 'Official only' toggle with mobile-friendly stacked layout.",
            "Better Theme Picker dropdown with full-width bottom sheet on mobile devices.",
            "Optimized Library grid, Settings panel, and all component spacing for small screens."
        ]
    },
    {
        version: "1.2.5",
        date: "2025-12-20",
        title: "Spotify M3U8 Playlist Generation",
        changes: [
            "Added M3U8 playlist generation for Spotify imports - compatible with Navidrome/Jellyfin.",
            "M3U8 only includes validated tracks that have been downloaded, ensuring accuracy.",
            "Added playlist name input field for custom naming of generated playlists."
        ]
    },
    {
        version: "1.2.4",
        date: "2025-12-20",
        title: "Spotify 100-Track Limit Bypass",
        changes: [
            "Replaced guest token API with SpotAPI library for unlimited playlist fetching.",
            "Spotify playlists now fetch all tracks without the previous 100-track limitation.",
            "Improved reliability using Spotify's partner API endpoint."
        ]
    },
    {
        version: "1.2.3",
        date: "2025-12-20",
        title: "Spotify Playlist Integration",
        changes: [
            "Introduced native support for Spotify playlist URLs with an interactive 'Fetch then Check' workflow.",
            "Implemented guest token extraction to bypass the 100-track limit for public playlists.",
            "Added a dedicated Spotify Playlists tab with bulk validation and advanced selection tools.",
            "Enhanced track matching algorithm with Romaji fallback for improved accuracy on Japanese titles."
        ]
    },
    {
        version: "1.2.2",
        date: "2025-12-20",
        title: "Direct Playlist URL Support",
        changes: [
            "Implemented direct navigation support for Tidal playlist URLs and UUIDs in the search bar.",
            "Resolved discovery issues for user-created playlists not indexed in public search."
        ]
    },
    {
        version: "1.2.1",
        date: "2025-12-19",
        title: "Playlist File Management",
        changes: [
            "Added ability to delete downloaded playlist files directly from the UI.",
            "Added comprehensive safety checks and confirmation dialogs to prevent accidental deletion.",
            "Minor UI improvements for playlist management."
        ]
    },
    {
        version: "1.2.0",
        date: "2025-12-19",
        title: "Monitored Playlists & API Cleanup",
        changes: [
            "New Feature: Monitored Playlists! Subscribe to Tidal playlists and automatically keep them in sync.",
            "Added support for Daily, Weekly, and Monthly auto-sync frequencies for monitored playlists.",
            "Playlists now generate standard .m3u8 files for Navidrome/Jellyfin.",
            "Refined Tidal API client: Removed legacy fallback systems for a more robust and secure connection.",
            "Improved backend stability with enhanced error handling and cleanup.",
            "Added dedicated 'Tidal Playlists' tab for managing your monitored collections."
        ]
    },
    {
        version: "1.1.0",
        date: "2025-12-14",
        title: "Extended ListenBrainz Integration",
        changes: [
            "Renamed 'Weekly Jams' tab to 'Listenbrainz Playlists' to reflect broader support.",
            "Added support for 'Weekly Exploration' and 'Year in Review' (Discoveries & Missed) playlists.",
            "Implemented a new 'Fetch then Check' workflow: Fetch playlists instantly and validate tracks on demand.",
            "Overhauled the UI with album art display, better status indicators, and selective download queuing.",
            "Added 'Check All' functionality to batch validate playlist tracks against Tidal."
        ]
    },
    {
        version: "1.0.4",
        date: "2025-12-14",
        title: "Download Manager Authentication Fix",
        changes: [
            "Fixed DownloadManager to properly respect the user's authentication state."
        ]
    },
    {
        version: "1.0.3",
        date: "2025-12-14",
        title: "Weekly Jams & Core Optimizations",
        changes: [
            "Replaced Troi with direct ListenBrainz integration for 'Weekly Jams', reducing image size by a lot.",
            "Major Docker optimization: Image size slashed by removing OS dependencies and using static binaries.",
            "Fixed annoying browser 'Sign in' popups during playlist generation.",
            "Improved backend stability and request handling."
        ]
    },
    {
        version: "1.0.2",
        date: "2025-12-14",
        title: "Easter egg",
        changes: [
            "Added cool nyan cat easter egg"
        ]
    },
    {
        version: "1.0.1",
        date: "2025-12-13",
        title: "Playlist Download Support",
        changes: [
            "Added support for downloading playlists thanks to @Oduanir."
        ]
    },
    {
        version: "1.0.0",
        date: "2025-12-13",
        title: "Themes Update & Proper Versioning",
        changes: [
            "New 'Tsunami' icon and branding!",
            "Added a dedicated Light/Dark mode toggle for quick switching.",
            "Introduced a new cohesive definition for themes.",
            "Improved contrast and visibility for multiple themes (Kanagawa, Dracula, Nord, etc.).",
            "Fixed 'White Screen' issues with theme colors.",
            "Added this release notes system!",
            "Added versioning to the app."
        ]
    }
];
