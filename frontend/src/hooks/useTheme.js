import { useState, useEffect } from 'preact/hooks';

export const themeNames = {
    "light": "Light",
    "dark": "Dark",
    "catppuccin-latte": "Catppuccin Latte",
    "catppuccin-frappe": "Catppuccin Frappe",
    "catppuccin-macchiato": "Catppuccin Macchiato",
    "catppuccin-mocha": "Catppuccin Mocha",
    "matcha": "Matcha",
    "nord": "Nord",
    "gruvbox": "Gruvbox",
    "dracula": "Dracula",
    "solarized-light": "Solarized Light",
    "solarized-dark": "Solarized Dark",
    "rose-pine": "Rose Pine",
    "tokyo-night": "Tokyo Night",
    "crimson": "Crimson",
    "kanagawa": "Kanagawa",
    "one-dark": "One Dark",
    "one-light": "One Light",
    "everforest": "Everforest",
    "cotton-candy-dreams": "Cotton Candy",
    "sea-green": "Sea Green"
};

export function useTheme() {
    const [theme, setThemeState] = useState(() => {
        if (typeof localStorage !== 'undefined' && localStorage.getItem('theme')) {
            const savedTheme = localStorage.getItem('theme');
            // Legacy support: map old boolean-like values to new defaults if necessary
            // But based on previous code it was just "dark" or "light", which maps fine.
            return savedTheme;
        }
        if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    });

    const setTheme = (newTheme) => {
        setThemeState(newTheme);
        localStorage.setItem('theme', newTheme);
    };

    useEffect(() => {
        const root = document.documentElement;
        // Remove all known theme classes
        Object.keys(themeNames).forEach(t => root.classList.remove(t));

        // Add current theme class
        // Note: The original 'light' theme might just be the absence of a class, 
        // or we can make it explicit. The previous code removed 'dark' for light mode.
        // For this new system, let's explicit classes for everything EXCEPT potentially 'light' 
        // if 'light' is the default root variables.
        // However, to be cleaner, we can apply the class for consistency if we move default vars to .light
        // But typically root has defaults. Let's assume root = light, and others are classes.
        // IF newTheme is NOT light, add the class.

        if (theme !== 'light') {
            root.classList.add(theme);
        }
    }, [theme]);

    return { theme, setTheme };
}
