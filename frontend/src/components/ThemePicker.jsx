import { h } from "preact";
import { useState, useEffect, useRef } from "preact/hooks";
import { useTheme, themeNames } from "../hooks/useTheme";

// Get theme-specific colors without CSS variables
// We match these to the CSS variables defined in style.css for the preview
const themePreviewColors = {
    "light": ["#7fa650", "#f7f4e9", "#ffffff", "#3a4032"],
    "dark": ["#7fa650", "#141612", "#20221c", "#ece8d9"],
    "catppuccin-latte": ["#8839ef", "#eff1f5", "#ffffff", "#4c4f69"],
    "catppuccin-frappe": ["#ca9ee6", "#303446", "#414559", "#c6d0f5"],
    "catppuccin-macchiato": ["#c6a0f6", "#24273a", "#363a4f", "#cad3f5"],
    "catppuccin-mocha": ["#cba6f7", "#1e1e2e", "#313244", "#cdd6f4"],
    "matcha": ["#7fa650", "#f7f4e9", "#ffffff", "#3a4032"],
    "nord": ["#88c0d0", "#2e3440", "#434c5e", "#eceff4"],
    "gruvbox": ["#8ec07c", "#282828", "#1d2021", "#ebdbb2"],
    "dracula": ["#bd93f9", "#282a36", "#44475a", "#f8f8f2"],
    "solarized-light": ["#268bd2", "#fdf6e3", "#fefefe", "#073642"],
    "solarized-dark": ["#268bd2", "#002b36", "#073642", "#fdf6e3"],
    "rose-pine": ["#ebbcba", "#191724", "#26233a", "#e0def4"],
    "tokyo-night": ["#7aa2f7", "#1a1b26", "#2f3549", "#c0caf5"],
    "crimson": ["#e53935", "#1a1a1a", "#2d2d2d", "#f5f5f5"],
    "one-dark": ["#61afef", "#282c34", "#3e4451", "#abb2bf"],
    "one-light": ["#4078f2", "#fafafa", "#e5e5e5", "#383a42"],
    "everforest": ["#a7c080", "#2f383e", "#3c464d", "#d3c6aa"],
    "cotton-candy-dreams": ["#ff5c8d", "#ffe1ed", "#ffecf3", "#69385c"],
    "sea-green": ["#2e8b57", "#0e1a16", "#1a2e28", "#d6f5e3"],
    "kanagawa": ["#7e9cd8", "#1f1f28", "#54546d", "#dcd7ba"]
};

// Local storage key for recent themes
const RECENT_THEMES_KEY = 'recent-themes';
const MAX_RECENT_THEMES = 5;

// SessionStorage key for NyanCat state
const NYAN_CAT_KEY = 'nyan-cat-enabled';

// Group themes by category for better organization
const themeCategories = {
    "Catppuccin": ["catppuccin-latte", "catppuccin-frappe", "catppuccin-macchiato", "catppuccin-mocha"],
    "Light": ["solarized-light", "matcha", "one-light"],
    "Dark": ["one-dark", "tokyo-night", "gruvbox", "dracula", "nord", "solarized-dark", "rose-pine", "everforest", "kanagawa", "crimson", "sea-green", "cotton-candy-dreams"]
};

// NyanCat state management functions
const getNyanCatState = () => {
    try {
        if (typeof sessionStorage !== 'undefined') {
            const stored = sessionStorage.getItem(NYAN_CAT_KEY);
            return stored === 'true';
        }
        return false;
    } catch (error) {
        console.warn('Failed to get NyanCat state from sessionStorage:', error);
        return false;
    }
};

const setNyanCatState = (enabled) => {
    try {
        if (typeof sessionStorage !== 'undefined') {
            sessionStorage.setItem(NYAN_CAT_KEY, enabled.toString());
            // Dispatch custom event to notify other components if needed
            window.dispatchEvent(new CustomEvent('nyanCatStateChange', {
                detail: { enabled }
            }));
        }
    } catch (error) {
        console.warn('Failed to save NyanCat state to sessionStorage:', error);
    }
};

export function ThemePicker() {
    const { theme, setTheme } = useTheme();
    const [isOpen, setIsOpen] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [recentThemes, setRecentThemes] = useState([]);
    const [isNyanCatActive, setIsNyanCatActive] = useState(false);
    const dropdownRef = useRef(null);
    const searchInputRef = useRef(null);

    // Check if current theme is effectively "light"
    const isLightMode = theme === 'light' ||
        theme === 'catppuccin-latte' ||
        theme === 'solarized-light' ||
        theme === 'matcha' ||
        theme === 'one-light' ||
        theme === 'cotton-candy-dreams';

    // Toggle between standard Light and Dark modes
    const toggleLightDark = () => {
        if (isLightMode) {
            setTheme('dark');
        } else {
            setTheme('light');
        }
    };

    // Load recent themes from localStorage
    useEffect(() => {
        if (typeof localStorage === 'undefined') return;

        const storedRecent = localStorage.getItem(RECENT_THEMES_KEY);
        if (storedRecent) {
            try {
                const parsed = JSON.parse(storedRecent);
                // Ensure current theme is first in the list if it exists
                const updatedRecent = parsed.includes(theme)
                    ? [theme, ...parsed.filter(t => t !== theme)]
                    : [theme, ...parsed];

                setRecentThemes(updatedRecent.slice(0, MAX_RECENT_THEMES));
            } catch (e) {
                console.error('Failed to parse recent themes', e);
                // Fallback: at least include current theme
                setRecentThemes([theme]);
            }
        } else {
            // Initialize with current theme
            setRecentThemes([theme]);
        }
    }, []);

    // Load NyanCat state from sessionStorage on mount
    useEffect(() => {
        setIsNyanCatActive(getNyanCatState());
    }, []);

    // Update recent themes when theme changes
    useEffect(() => {
        if (typeof localStorage === 'undefined') return;

        // Always update when theme changes, even on first render
        const updatedRecent = [theme, ...recentThemes.filter(t => t !== theme)].slice(0, MAX_RECENT_THEMES);
        setRecentThemes(updatedRecent);

        // Store in localStorage
        try {
            localStorage.setItem(RECENT_THEMES_KEY, JSON.stringify(updatedRecent));
        } catch (e) {
            console.error('Failed to store recent themes', e);
        }
    }, [theme]);

    // Focus search input when dropdown opens
    useEffect(() => {
        if (isOpen && searchInputRef.current) {
            setTimeout(() => {
                searchInputRef.current?.focus();
            }, 100);
        } else {
            setSearchQuery('');
        }
    }, [isOpen]);

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (
                dropdownRef.current &&
                !dropdownRef.current.contains(event.target)
            ) {
                setIsOpen(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Handle keyboard navigation
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (event) => {
            // Close on escape
            if (event.key === 'Escape') {
                setIsOpen(false);
            }
        };

        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [isOpen]);

    // Toggle the NyanCat Easter egg
    const toggleNyanCat = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const newState = !isNyanCatActive;
        setIsNyanCatActive(newState);
        setNyanCatState(newState);
    };

    // Filter themes based on search query
    const filteredThemes = Object.entries(themeNames)
        .filter(([themeKey]) => themeKey !== 'light' && themeKey !== 'dark') // Filter out hidden basic themes
        .filter(([themeKey, themeName]) =>
            themeName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            themeKey.toLowerCase().includes(searchQuery.toLowerCase())
        );

    // Sort function to organize themes by category
    const sortThemes = (themes) => {
        return [...themes].sort((a, b) => {
            const aName = themeNames[a[0]] || a[1];
            const bName = themeNames[b[0]] || b[1];
            return aName.localeCompare(bName);
        });
    };

    // Group themes: recent first, then by category (when not searching)
    const groupedThemes = () => {
        if (searchQuery) {
            // When searching, just show sorted results
            return sortThemes(filteredThemes);
        }

        // Start with recent themes in their explicit order
        const recentThemeEntries = recentThemes
            .filter(key => themeNames[key] && key !== 'light' && key !== 'dark') // Filter out invalid themes and light/dark
            .map(themeKey => [themeKey, themeNames[themeKey]]);

        // Find themes that aren't in the recent list
        const remainingThemes = filteredThemes
            .filter(([themeKey]) => !recentThemes.includes(themeKey));

        // Sort the remaining themes
        const sortedRemaining = sortThemes(remainingThemes);

        // Return recent themes followed by remaining sorted themes
        return [...recentThemeEntries, ...sortedRemaining];
    };

    // Get the theme category for better descriptions
    const getThemeCategory = (themeKey) => {
        for (const [category, themes] of Object.entries(themeCategories)) {
            if (themes.includes(themeKey)) {
                return category;
            }
        }
        return "Custom";
    };

    return (
        <div class="flex items-center gap-2" ref={dropdownRef}>
            {/* Dedicated Light/Dark Toggle */}
            <button
                onClick={toggleLightDark}
                class="p-2.5 rounded-lg hover:bg-surface-alt text-text-muted hover:text-text 
                transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
                aria-label={isLightMode ? "Switch to Dark Mode" : "Switch to Light Mode"}
                title={isLightMode ? "Switch to Dark Mode" : "Switch to Light Mode"}
            >
                {isLightMode ? (
                    /* Moon Icon */
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                    </svg>
                ) : (
                    /* Sun Icon */
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="5"></circle>
                        <line x1="12" y1="1" x2="12" y2="3"></line>
                        <line x1="12" y1="21" x2="12" y2="23"></line>
                        <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                        <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                        <line x1="1" y1="12" x2="3" y2="12"></line>
                        <line x1="21" y1="12" x2="23" y2="12"></line>
                        <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                        <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
                    </svg>
                )}
            </button>

            <div class="relative">
                {/* Theme Toggle Button with enhanced tooltip */}
                <button
                    onClick={() => setIsOpen(!isOpen)}
                    class="group p-2.5 rounded-lg hover:bg-surface-alt focus:outline-none 
          focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background
          text-text transition-all duration-200 relative"
                    aria-label="Change theme"
                >
                    <div
                        class="w-7 h-7 rounded-md border border-border overflow-hidden grid grid-cols-2 gap-px
          transition-transform duration-200 group-hover:scale-105"
                    >
                        {themePreviewColors[theme] ? themePreviewColors[theme].map((color, i) => (
                            <div
                                key={i}
                                class="w-full h-full"
                                style={{ backgroundColor: color }}
                            />
                        )) : (
                            // Fallback if current theme has no preview colors
                            <div class="w-full h-full col-span-2 bg-primary"></div>
                        )}
                    </div>
                    {/* Enhanced Tooltip */}
                    <span
                        class="absolute hidden group-hover:block -bottom-1 left-1/2 transform -translate-x-1/2 translate-y-full 
          px-3 py-1.5 bg-surface text-sm text-text rounded-lg shadow-lg whitespace-nowrap z-50
          border border-border"
                    >
                        <span class="font-medium">Theme:</span> {themeNames[theme]}
                        <span class="block text-xs text-text-muted mt-0.5">
                            Click to customize
                        </span>
                    </span>
                </button>

                {/* Theme Dropdown - Improved mobile layout */}
                {isOpen && (
                    <div
                        class="absolute right-0 mt-2 w-72 sm:w-64 py-2 bg-surface border border-border 
            rounded-lg shadow-lg z-50 theme-fade-in"
                        role="dialog"
                        aria-label="Theme Picker"
                    >
                        <div class="px-4 py-2 border-b border-border">
                            <div class="flex items-center justify-between">
                                <h3 class="text-sm font-medium">Select Theme</h3>
                                <button
                                    onClick={() => setIsOpen(false)}
                                    class="text-text-muted hover:text-text rounded-full p-1 
                  hover:bg-surface-alt transition-colors"
                                    aria-label="Close theme picker"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <line x1="18" y1="6" x2="6" y2="18"></line>
                                        <line x1="6" y1="6" x2="18" y2="18"></line>
                                    </svg>
                                </button>
                            </div>

                            {/* Search input with icon */}
                            <div class="relative mt-2">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                    </svg>
                                </div>
                                <input
                                    ref={searchInputRef}
                                    type="text"
                                    placeholder="Search themes..."
                                    value={searchQuery}
                                    onInput={(e) => setSearchQuery(e.target.value)}
                                    class="w-full pl-10 pr-8 py-2 bg-surface-alt border border-border rounded-md
                text-sm text-text placeholder:text-text-muted focus:outline-none
                focus:ring-1 focus:ring-primary"
                                    aria-label="Search themes"
                                />
                                {searchQuery && (
                                    <button
                                        onClick={() => setSearchQuery('')}
                                        class="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted
                  hover:text-text focus:outline-none p-1 rounded-full hover:bg-surface"
                                        aria-label="Clear search"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                            <line x1="18" y1="6" x2="6" y2="18"></line>
                                            <line x1="6" y1="6" x2="18" y2="18"></line>
                                        </svg>
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Section headers - Only shown when not searching and when there are recent themes */}
                        {!searchQuery && recentThemes.length > 0 && (
                            <div class="sticky top-0 z-10 px-4 py-1.5 border-b border-border bg-surface">
                                <h4 class="text-xs font-medium text-text-muted">RECENTLY USED</h4>
                            </div>
                        )}

                        <div class="max-h-[min(420px,70vh)] overflow-y-auto py-1 thin-scrollbar">
                            {groupedThemes().map(([themeKey, themeName], index) => {
                                const isRecent = !searchQuery && recentThemes.includes(themeKey);
                                const isFirstNonRecent = !searchQuery && index === recentThemes.length && recentThemes.length > 0;

                                return (
                                    /* Fragment */
                                    <div key={themeKey}>
                                        {/* Separator between recent and other themes */}
                                        {isFirstNonRecent && (
                                            <div class="sticky top-0 z-10 px-4 py-1.5 border-y border-border mt-1 bg-surface">
                                                <h4 class="text-xs font-medium text-text-muted">ALL THEMES</h4>
                                            </div>
                                        )}

                                        <button
                                            onClick={() => {
                                                setTheme(themeKey);
                                                setIsOpen(false);
                                            }}
                                            class={`w-full px-4 py-3 flex items-center gap-3 hover:bg-surface-alt
                      transition-colors duration-200 text-left group
                      ${isRecent ? "bg-surface-alt/50" : ""}
                      ${theme === themeKey ? "bg-primary/10 text-primary" : "text-text"}`}
                                        >
                                            {/* Theme Preview with improved hover effect */}
                                            <div
                                                class={`w-9 h-9 rounded-md border overflow-hidden grid grid-cols-2 gap-px
                      transition-all duration-300 group-hover:scale-105 group-hover:shadow-md
                      ${theme === themeKey ? 'border-primary shadow-sm' : 'border-border'}`}
                                            >
                                                {themePreviewColors[themeKey] && themePreviewColors[themeKey].map((color, i) => (
                                                    <div
                                                        key={i}
                                                        class="w-full h-full"
                                                        style={{ backgroundColor: color }}
                                                    />
                                                ))}
                                            </div>

                                            {/* Theme Name with improved description */}
                                            <div class="flex-1">
                                                <div class="font-medium flex items-center gap-1.5">
                                                    {themeName}
                                                    {theme === themeKey && (
                                                        <span class="flex items-center text-primary">
                                                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                                <path d="M20 6L9 17l-5-5" />
                                                            </svg>
                                                        </span>
                                                    )}
                                                </div>
                                                <div class="text-xs text-text-muted mt-0.5 flex items-center gap-2">
                                                    {isRecent && (
                                                        <span class="flex items-center gap-0.5">
                                                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                                                <circle cx="12" cy="12" r="10" />
                                                                <polyline points="12 6 12 12 16 14" />
                                                            </svg>
                                                            Recent
                                                        </span>
                                                    )}
                                                    <span>{getThemeCategory(themeKey)}</span>
                                                </div>
                                            </div>
                                        </button>
                                    </div>
                                );
                            })}

                            {/* No results message with improved styling */}
                            {filteredThemes.length === 0 && (
                                <div class="px-4 py-8 text-center text-text-muted">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-10 w-10 mx-auto mb-2 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <p class="text-sm">No themes match your search</p>
                                    <button
                                        onClick={() => setSearchQuery('')}
                                        class="text-primary text-sm hover:underline mt-2 focus:outline-none
                    px-3 py-1 border border-primary/30 rounded-md hover:bg-primary/10"
                                    >
                                        Clear search
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Footer with additional features */}
                        <div class="px-4 pt-2 mt-1 border-t border-border">
                            <div class="flex items-center justify-between text-xs">
                                <p class="text-text-muted flex items-center gap-1.5">
                                    <a
                                        href="https://github.com/catppuccin/catppuccin"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="text-primary hover:underline"
                                    >
                                        Catppuccin
                                    </a>
                                    {" "}& more

                                    {/* Cat icon for NyanCat Easter egg */}
                                    <button
                                        onClick={toggleNyanCat}
                                        class={`group relative w-5 h-5 flex items-center justify-center rounded-full 
                    transition-colors duration-300 ${isNyanCatActive ? 'text-pink-500' : 'text-text-muted hover:text-primary'}`}
                                        aria-label={isNyanCatActive ? "Disable NyanCat mode" : "Enable NyanCat mode"}
                                    >
                                        {/* NyanCat SVG or similar icon */}
                                        <svg
                                            xmlns="http://www.w3.org/2000/svg"
                                            viewBox="0 0 24 24"
                                            fill="currentColor"
                                            class={`w-4 h-4 transition-transform duration-300 ${isNyanCatActive ? 'animate-bounce' : 'group-hover:scale-110'}`}
                                        >
                                            <path d="M12 2c2 0 4 1 4 2.5V5c.5 0 1 .21 1 1s-.5 1-1 1v1c0 .18-.37.38-1 .59V11c.63.21 1 .41 1 .59v1.9c2.07.84 4 2 4 5.01 0 .43-.74.76-.95.76l-.89-1.33a.5.5 0 0 0-.83.12c-.27.67-.67 1.14-1.11 1.5-.83.68-1.92 1.11-2.72 1.3-.27.18-.49.24-.5.24.05.32-.15.62-.47.74-.31.12-.66.01-.86-.25-1.12.06-2.2-.14-3.23-.76-.83-.5-1.62-1.25-2.37-2.23a.75.75 0 0 0-1.21.08c-.2.36-.93 1.61-.93 1.61S4 19.5 4 18.5c0-2.42 1.35-3.54 3-4.39V12.6c-.63-.21-1-.41-1-.59V10h-.5C4.67 10 4 9.5 4 8V7c0-1 1-1 1-1V5.5C5 3.75 8 2 12 2m0 1c-2.96 0-5 1.11-5 2.5V8c0 .55.55 1 1 1h8c.55 0 1-.55 1-1V5.5c0-1.39-1.94-2.5-5-2.5m-3 7c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1m6 0c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1Z" />
                                        </svg>
                                        {/* Tooltip for NyanCat */}
                                        <span class="absolute left-1/2 -bottom-1 transform -translate-x-1/2 translate-y-full 
                    w-28 px-2 py-1 bg-surface border border-border rounded text-xxs text-center
                    opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity">
                                            {isNyanCatActive ? "Disable Nyan Mode" : "Enable Nyan Mode"}
                                        </span>
                                    </button>
                                </p>
                                <span class="text-text-muted">{Object.keys(themePreviewColors).length} themes</span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Styles for thin scrollbars and animations */}
                <style>{`
        .thin-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .thin-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .thin-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgb(var(--color-border));
          border-radius: 4px;
        }
        .theme-fade-in {
          animation: themeDropdownFadeIn 0.15s ease-out;
        }
        @keyframes themeDropdownFadeIn {
          from { opacity: 0; transform: translateY(-8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .text-xxs {
          font-size: 0.65rem;
        }
      `}</style>
            </div>
        </div>
    );
}
