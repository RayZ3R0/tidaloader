import { h } from "preact";
import { useState } from "preact/hooks";
import { PlaylistSearch } from "./PlaylistSearch";
import { MonitoredList } from "./MonitoredList";

export function TidalPlaylists() {
  const [activeTab, setActiveTab] = useState("search");

  return (
    <div class="space-y-4 sm:space-y-6">
      <div class="flex gap-1 sm:gap-2 border-b border-border pb-0 overflow-x-auto scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
        <button
          class={`px-3 sm:px-4 py-2 font-medium rounded-t-lg transition-all duration-200 whitespace-nowrap text-sm flex-shrink-0 ${
            activeTab === "search"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
          }`}
          onClick={() => setActiveTab("search")}
        >
          Search & Add
        </button>
        <button
          class={`px-3 sm:px-4 py-2 font-medium rounded-t-lg transition-all duration-200 whitespace-nowrap text-sm flex-shrink-0 ${
            activeTab === "monitored"
              ? "bg-surface text-primary border-b-2 border-primary -mb-px"
              : "text-text-muted hover:text-text hover:bg-surface-alt"
          }`}
          onClick={() => setActiveTab("monitored")}
        >
          <span class="sm:hidden">Monitored</span>
          <span class="hidden sm:inline">Monitored Playlists</span>
        </button>
      </div>

      <div class="rounded-b-xl">
        {activeTab === "search" ? (
          <PlaylistSearch onSyncStarted={() => setActiveTab("monitored")} />
        ) : (
          <MonitoredList />
        )}
      </div>
    </div>
  );
}
