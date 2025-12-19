export const releaseNotes = [
    {
        version: "1.2.0",
        date: "2025-12-19",
        title: "Monitored Playlists & API Cleanup",
        changes: [
            "New Feature: Monitored Playlists! Subscribe to Tidal playlists and automatically keep them in sync.",
            "Added support for Daily, Weekly, and Monthly auto-sync frequencies for monitored playlists.",
            "Playlists now generate standard .m3u8 files for easy playback in your favorite media player.",
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
