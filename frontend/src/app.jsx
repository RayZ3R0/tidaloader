import { h } from "preact";
import { useState } from "preact/hooks";
import { Router } from "preact-router";
import logo from "./assets/tsunami.svg";
import { useAuthStore } from "./store/authStore";
import { Login } from "./components/Login";
import { SearchBar } from "./components/SearchBar";
import { TroiGenerator } from "./components/TroiGenerator";
import { DownloadQueuePopout } from "./components/DownloadQueuePopout";
import { SettingsPanel } from "./components/SettingsPanel";
import { LibraryPage } from "./components/LibraryPage";
import { Toast } from "./components/Toast";

import { ThemePicker } from "./components/ThemePicker";

import { ReleaseNotes } from "./components/ReleaseNotes";
import { releaseNotes } from "./data/releaseNotes";
import { useEffect } from "preact/hooks";

export function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const clearCredentials = useAuthStore((state) => state.clearCredentials);
  const [activeTab, setActiveTab] = useState("search");
  const [showSettings, setShowSettings] = useState(false);
  const [showReleaseNotes, setShowReleaseNotes] = useState(false);

  useEffect(() => {
    try {
      if (releaseNotes.length > 0) {
        const latestVersion = releaseNotes[0].version;
        const lastSeen = localStorage.getItem("last-seen-version");
        if (lastSeen !== latestVersion) {
          setShowReleaseNotes(true);
        }
      }
    } catch (e) {
      console.warn("Failed to check release notes version", e);
    }
  }, []);

  const handleCloseReleaseNotes = () => {
    setShowReleaseNotes(false);
    if (releaseNotes.length > 0) {
      localStorage.setItem("last-seen-version", releaseNotes[0].version);
    }
  };

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div class="min-h-screen bg-background">
      {/* Header with logout button */}
      <header class="bg-surface border-b border-border-light px-4 py-3 shadow-sm">
        <div class="max-w-7xl mx-auto flex justify-between items-center">
          <div class="flex items-center gap-3">
            <div class="flex items-center justify-center w-10 h-10 bg-primary rounded-xl overflow-hidden">
              <img src={logo} alt="Tidaloader Logo" class="w-8 h-8 object-contain" />
            </div>
            <h1 class="text-xl sm:text-2xl font-bold text-text">Tidaloader</h1>
          </div>
          <div class="flex items-center gap-3">
            <button
              onClick={() => setShowReleaseNotes(true)}
              class="hidden sm:flex items-center gap-2 px-3 py-2 text-sm font-medium text-text-muted hover:text-text hover:bg-surface-alt rounded-lg transition-all duration-200"
              title="What's New"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              <span>What's New</span>
            </button>
            <ThemePicker />
            <button
              onClick={clearCredentials}
              class="flex items-center gap-2 px-4 py-2 bg-surface-alt hover:bg-background-alt border border-border text-text-muted hover:text-text rounded-lg text-sm transition-all duration-200"
            >
              <svg
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              <span class="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </header>

      <ReleaseNotes
        isOpen={showReleaseNotes}
        onClose={handleCloseReleaseNotes}
      />
      <Toast />
      <DownloadQueuePopout />
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <header class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h1 class="text-2xl sm:text-3xl font-bold text-text">
            Tidaloader
          </h1>
          <button
            class="btn-surface flex items-center gap-2 self-start sm:self-auto"
            onClick={() => setShowSettings(!showSettings)}
          >
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
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            Settings
          </button>
        </header>

        {showSettings && (
          <div class="card p-6 mb-6 animate-slide-up">
            <SettingsPanel />
          </div>
        )}

        <nav class="flex gap-2 mb-6 border-b border-border pb-0">
          <button
            class={`px-6 py-3 font-medium rounded-t-lg transition-all duration-200 ${activeTab === "search"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
              }`}
            onClick={() => setActiveTab("search")}
          >
            Custom Search
          </button>
          <button
            class={`px-6 py-3 font-medium rounded-t-lg transition-all duration-200 ${activeTab === "troi"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
              }`}
            onClick={() => setActiveTab("troi")}
          >
            Troi Playlist
          </button>
          <button
            class={`px-6 py-3 font-medium rounded-t-lg transition-all duration-200 ${activeTab === "library"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
              }`}
            onClick={() => setActiveTab("library")}
          >
            My Library
          </button>
        </nav>

        <main class="card p-6 mb-6 min-h-[400px]">
          {activeTab === "search" && <SearchBar />}
          {activeTab === "troi" && <TroiGenerator />}
          {activeTab === "library" && <LibraryPage />}
        </main>
      </div>
    </div>
  );
}
