import { h } from "preact";
import { useState } from "preact/hooks";
import { ManualImport } from "./spotify/ManualImport";
import { SpotifySearch } from "./spotify/SpotifySearch";
import { MonitoredPlaylists } from "./spotify/MonitoredPlaylists";

export function SpotifyDownloader() {
  const [activeTab, setActiveTab] = useState("manual"); // manual, search, monitored

  return (
    <div class="space-y-6">
      <div class="border-b border-border-light">
        <nav class="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab("manual")}
            class={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === "manual"
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text hover:border-border"
            }`}
          >
            Manual Import
          </button>
          <button
            onClick={() => setActiveTab("search")}
            class={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === "search"
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text hover:border-border"
            }`}
          >
            Search & Add
          </button>
          <button
            onClick={() => setActiveTab("monitored")}
            class={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === "monitored"
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text hover:border-border"
            }`}
          >
            Monitored Playlists
          </button>
        </nav>
      </div>

      <div class="min-h-[400px]">
        {activeTab === "manual" && <ManualImport />}
        {activeTab === "search" && <SpotifySearch />}
        {activeTab === "monitored" && <MonitoredPlaylists />}
      </div>
    </div>
  );
}

// Temporary placeholders until we implement them in TICKET-06 and TICKET-07
/*
function SpotifySearch() {
    return <div class="p-8 text-center text-text-muted">Search & Add Interface Coming Soon...</div>;
}

function MonitoredPlaylists() {
    return <div class="p-8 text-center text-text-muted">Monitored Playlists Interface Coming Soon...</div>;
}
*/
