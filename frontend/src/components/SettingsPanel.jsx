import { h, Fragment } from "preact";
import { useState, useEffect, useCallback, useRef } from "preact/hooks";
import { useDownloadStore } from "../stores/downloadStore";

const QUALITY_OPTIONS = [
  {
    value: "HI_RES_LOSSLESS",
    label: "Hi-Res FLAC",
    description: "Up to 24-bit/192kHz",
  },
  { value: "LOSSLESS", label: "FLAC", description: "16-bit/44.1kHz" },
  {
    value: "MP3_256",
    label: "MP3 256kbps",
    description: "Transcoded (libmp3lame)",
  },
  {
    value: "MP3_128",
    label: "MP3 128kbps",
    description: "Transcoded (smaller size)",
  },
  {
    value: "OPUS_192VBR",
    label: "Opus 192kbps",
    description: "Variable bitrate (192kbps target)",
  },
  { value: "HIGH", label: "AAC 320kbps", description: "High quality AAC" },
  { value: "LOW", label: "AAC 96kbps", description: "Low quality AAC" },
];

const PREDEFINED_TEMPLATES = [
  "{Artist}/{Album}/{TrackNumber} - {Title}",
  "{Artist}/{Album}/{Title}",
  "{Artist} - {Title}",
  "{Album}/{TrackNumber} - {Title}",
];

// ─── Toast Component ─────────────────────────────────────────────────────
function Toast({ message, type, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 3000);
    return () => clearTimeout(timer);
  }, []);

  const colors = {
    success: "bg-green-500/15 text-green-400 border-green-500/30",
    error: "bg-red-500/15 text-red-400 border-red-500/30",
    warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
    info: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  };

  const icons = {
    success: (
      <svg
        className="w-4 h-4 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M5 13l4 4L19 7"
        />
      </svg>
    ),
    error: (
      <svg
        className="w-4 h-4 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    ),
    warning: (
      <svg
        className="w-4 h-4 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.072 16.5c-.77.833.192 2.5 1.732 2.5z"
        />
      </svg>
    ),
    info: (
      <svg
        className="w-4 h-4 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    ),
  };

  return (
    <div
      className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm font-medium animate-fade-in ${colors[type] || colors.info}`}
    >
      {icons[type] || icons.info}
      <span>{message}</span>
    </div>
  );
}

// ─── Toggle Switch with auto-save ────────────────────────────────────────
function AutoSaveToggle({
  label,
  description,
  checked,
  disabled,
  onToggle,
  savingKey,
  savingState,
}) {
  const isSaving = savingState === savingKey;

  return (
    <div
      className={`flex items-center justify-between p-4 bg-surface-alt rounded-lg border border-border-light transition-colors ${disabled ? "opacity-50" : ""}`}
    >
      <div className="space-y-1 pr-4">
        <span className="text-sm font-medium text-text block">{label}</span>
        <span className="text-xs text-text-muted block">{description}</span>
      </div>
      <div className="flex items-center gap-2">
        {isSaving && (
          <svg
            className="animate-spin h-4 w-4 text-primary"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        <label
          className={`relative inline-flex items-center ${disabled ? "cursor-not-allowed" : "cursor-pointer"}`}
        >
          <input
            type="checkbox"
            className="sr-only peer"
            checked={checked}
            onChange={(e) => onToggle(e.target.checked)}
            disabled={disabled}
          />
          <div className="w-11 h-6 bg-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
        </label>
      </div>
    </div>
  );
}

// ─── Main SettingsPanel ──────────────────────────────────────────────────
export function SettingsPanel() {
  const [syncTime, setSyncTime] = useState("04:00");
  const [template, setTemplate] = useState(
    "{Artist}/{Album}/{TrackNumber} - {Title}",
  );
  const [activeDownloads, setActiveDownloads] = useState(3);
  const [useMusicBrainz, setUseMusicBrainz] = useState(true);
  const [runBeets, setRunBeets] = useState(false);
  const [embedLyrics, setEmbedLyrics] = useState(false);
  const [quality, setQuality] = useState("LOSSLESS");
  const [jellyfinUrl, setJellyfinUrl] = useState("");
  const [jellyfinApiKey, setJellyfinApiKey] = useState("");
  const [jellyfinStatus, setJellyfinStatus] = useState(null);
  const [isCustomMode, setIsCustomMode] = useState(false);

  const [processing, setProcessing] = useState(false);
  const [syncingCovers, setSyncingCovers] = useState(false);
  const [savingToggle, setSavingToggle] = useState(null); // which toggle is auto-saving

  // Toast state
  const [toasts, setToasts] = useState([]);
  const toastIdRef = useRef(0);

  const addToast = useCallback((message, type = "success") => {
    const id = ++toastIdRef.current;
    setToasts((prev) => [...prev.slice(-2), { id, message, type }]); // keep max 3
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Load settings on mount
  useEffect(() => {
    const load = async () => {
      try {
        const s = await useDownloadStore.getState().fetchServerSettings();
        if (s) {
          setSyncTime(s.sync_time || "04:00");
          setTemplate(
            s.organization_template ||
              "{Artist}/{Album}/{TrackNumber} - {Title}",
          );
          setActiveDownloads(s.active_downloads || 3);
          setUseMusicBrainz(
            s.use_musicbrainz !== undefined ? s.use_musicbrainz : true,
          );
          setRunBeets(s.run_beets || false);
          setEmbedLyrics(s.embed_lyrics || false);
          setJellyfinUrl(s.jellyfin_url || "");
          setJellyfinApiKey(s.jellyfin_api_key || "");
          setQuality(s.quality || "LOSSLESS");

          if (
            s.organization_template &&
            !PREDEFINED_TEMPLATES.includes(s.organization_template)
          ) {
            setIsCustomMode(true);
          }
        }
      } catch (e) {
        console.error("Load settings error", e);
        addToast("Failed to load settings", "error");
      }
    };
    load();
  }, []);

  // Auto-save handler for toggles
  const handleToggleSave = async (key, value) => {
    setSavingToggle(key);
    try {
      const result = await useDownloadStore.getState().updateServerSettings({
        [key]: value,
      });

      if (result?.conflict) {
        addToast("Settings changed by another user — reloaded", "warning");
        // Reload all settings to get fresh values
        const s = await useDownloadStore.getState().fetchServerSettings();
        if (s) {
          setUseMusicBrainz(
            s.use_musicbrainz !== undefined ? s.use_musicbrainz : true,
          );
          setRunBeets(s.run_beets || false);
          setEmbedLyrics(s.embed_lyrics || false);
        }
      } else {
        addToast("Setting saved", "success");
      }
    } catch (e) {
      addToast("Failed to save setting", "error");
      // Revert the toggle
      if (key === "use_musicbrainz") setUseMusicBrainz(!value);
      if (key === "run_beets") setRunBeets(!value);
      if (key === "embed_lyrics") setEmbedLyrics(!value);
    } finally {
      setSavingToggle(null);
    }
  };

  // Save button handler for text/number fields
  const handleSave = async () => {
    setProcessing(true);
    try {
      const result = await useDownloadStore.getState().updateServerSettings({
        quality,
        sync_time: syncTime,
        organization_template: template,
        active_downloads: activeDownloads,
        use_musicbrainz: useMusicBrainz,
        run_beets: runBeets,
        embed_lyrics: embedLyrics,
        jellyfin_url: jellyfinUrl,
        jellyfin_api_key: jellyfinApiKey,
      });

      if (result?.conflict) {
        addToast(
          "Settings changed by another user — your changes were not saved. Page reloaded with latest values.",
          "warning",
        );
        const s = await useDownloadStore.getState().fetchServerSettings();
        if (s) {
          setSyncTime(s.sync_time || "04:00");
          setTemplate(
            s.organization_template ||
              "{Artist}/{Album}/{TrackNumber} - {Title}",
          );
          setActiveDownloads(s.active_downloads || 3);
          setUseMusicBrainz(
            s.use_musicbrainz !== undefined ? s.use_musicbrainz : true,
          );
          setRunBeets(s.run_beets || false);
          setEmbedLyrics(s.embed_lyrics || false);
          setJellyfinUrl(s.jellyfin_url || "");
          setJellyfinApiKey(s.jellyfin_api_key || "");
          setQuality(s.quality || "LOSSLESS");
        }
      } else {
        addToast("All settings saved successfully", "success");
      }
    } catch (error) {
      console.error("Failed to save settings:", error);
      addToast("Failed to save settings — please retry", "error");
    } finally {
      setProcessing(false);
    }
  };

  const testJellyfinConnection = async () => {
    setJellyfinStatus("testing");
    try {
      const res = await fetch("/api/system/jellyfin/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: jellyfinUrl, api_key: jellyfinApiKey }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setJellyfinStatus("success");
      } else {
        setJellyfinStatus("error");
      }
    } catch (e) {
      setJellyfinStatus("error");
    }
  };

  const handleSyncCovers = async () => {
    if (
      !confirm(
        "This will force-upload cover images for ALL monitored playlists to Jellyfin. This may take a while. Continue?",
      )
    ) {
      return;
    }

    setSyncingCovers(true);
    try {
      const { api } = await import("../api/client");
      await api.syncJellyfinCovers();
      addToast("Cover sync started in background", "info");
    } catch (e) {
      console.error(e);
      addToast("Failed to start cover sync: " + e.message, "error");
    } finally {
      setSyncingCovers(false);
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto space-y-8 pb-24 relative">
      {/* Toast container */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onDismiss={() => removeToast(toast.id)}
          />
        ))}
      </div>

      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-text">Settings</h1>
        <p className="text-text-muted mt-2">
          Configure application preferences and behavior.
        </p>
      </div>

      {/* System Config */}
      <div className="card p-6 space-y-6">
        <h2 className="text-xl font-semibold text-text flex items-center gap-2">
          <svg
            className="w-5 h-5 text-primary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
            ></path>
          </svg>
          System Configuration
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">
              Concurrent Downloads
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={activeDownloads}
              onChange={(e) => setActiveDownloads(parseInt(e.target.value))}
              className="input-field"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">
              Playlist Sync Time (Daily)
            </label>
            <input
              type="time"
              value={syncTime}
              onChange={(e) => setSyncTime(e.target.value)}
              className="input-field"
            />
            <p className="text-xs text-text-muted">
              Time to run automated playlist synchronization.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-text">
            Organization Template
          </label>
          <div className="space-y-2">
            <select
              className="input-field"
              value={isCustomMode ? "Custom" : template}
              onChange={(e) => {
                if (e.target.value === "Custom") {
                  setIsCustomMode(true);
                } else {
                  setTemplate(e.target.value);
                  setIsCustomMode(false);
                }
              }}
            >
              {PREDEFINED_TEMPLATES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
              <option value="Custom">Custom</option>
            </select>
            {isCustomMode && (
              <input
                type="text"
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
                placeholder="{Artist}/{Album}/{TrackNumber} - {Title}"
                className="input-field animate-fade-in"
              />
            )}
          </div>
          <p className="text-xs text-text-muted">
            Variables: {"{Artist}, {Album}, {Title}, {TrackNumber}, {Year}"}
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-text">
            Default Quality
          </label>
          <select
            value={quality}
            onChange={(e) => setQuality(e.target.value)}
            className="input-field"
          >
            {QUALITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} - {option.description}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Download Features — auto-save toggles */}
      <div className="card p-6 space-y-6">
        <h2 className="text-xl font-semibold text-text flex items-center gap-2">
          <svg
            className="w-5 h-5 text-primary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
            ></path>
          </svg>
          Download Features
          <span className="text-xs text-text-muted font-normal ml-auto">
            Changes save automatically
          </span>
        </h2>

        <div className="space-y-4">
          <AutoSaveToggle
            label="MusicBrainz Tagging"
            description="Fetch accurate metadata (genre, ISRC, MBIDs) from MusicBrainz"
            checked={useMusicBrainz}
            onToggle={(val) => {
              setUseMusicBrainz(val);
              handleToggleSave("use_musicbrainz", val);
            }}
            savingKey="use_musicbrainz"
            savingState={savingToggle}
          />

          <AutoSaveToggle
            label="Beets Tagging"
            description={
              useMusicBrainz
                ? "Disabled when MusicBrainz is enabled"
                : "Run beets importer after download (Experimental)"
            }
            checked={runBeets && !useMusicBrainz}
            disabled={useMusicBrainz}
            onToggle={(val) => {
              setRunBeets(val);
              handleToggleSave("run_beets", val);
            }}
            savingKey="run_beets"
            savingState={savingToggle}
          />

          <AutoSaveToggle
            label="Embed Created Lyrics"
            description="Embed synced lyrics into file metadata"
            checked={embedLyrics}
            onToggle={(val) => {
              setEmbedLyrics(val);
              handleToggleSave("embed_lyrics", val);
            }}
            savingKey="embed_lyrics"
            savingState={savingToggle}
          />
        </div>
      </div>

      {/* Jellyfin Integration */}
      <div className="card p-6 space-y-6">
        <h2 className="text-xl font-semibold text-text flex items-center gap-2">
          <svg
            className="w-5 h-5 text-primary"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
            ></path>
          </svg>
          Jellyfin Integration
        </h2>

        <div className="grid grid-cols-1 gap-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-text">Server URL</label>
            <input
              type="text"
              value={jellyfinUrl}
              onChange={(e) => setJellyfinUrl(e.target.value)}
              placeholder="http://192.168.1.10:8096"
              className="input-field"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-text">API Key</label>
            <div className="flex gap-2">
              <input
                type="password"
                value={jellyfinApiKey}
                onChange={(e) => setJellyfinApiKey(e.target.value)}
                placeholder="Your API Key"
                className="input-field"
              />
              <button
                onClick={testJellyfinConnection}
                disabled={!jellyfinUrl || !jellyfinApiKey}
                className={`px-4 py-2 rounded-lg font-medium transition-colors border ${
                  jellyfinStatus === "success"
                    ? "bg-green-500/20 text-green-500 border-green-500/50"
                    : jellyfinStatus === "error"
                      ? "bg-red-500/20 text-red-500 border-red-500/50"
                      : "bg-surface-alt text-text border-border hover:bg-surface"
                }`}
              >
                {jellyfinStatus === "testing"
                  ? "..."
                  : jellyfinStatus === "success"
                    ? "OK"
                    : jellyfinStatus === "error"
                      ? "Fail"
                      : "Test"}
              </button>
            </div>
          </div>

          <div className="pt-4 border-t border-border-light mt-2">
            <div className="flex justify-between items-center">
              <div className="space-y-1">
                <span className="text-sm font-medium text-text block">
                  Force Metadata Sync
                </span>
                <span className="text-xs text-text-muted block">
                  Re-upload all playlist covers to Jellyfin
                </span>
              </div>
              <button
                onClick={handleSyncCovers}
                disabled={!jellyfinUrl || !jellyfinApiKey || syncingCovers}
                className={`px-4 py-2 rounded-lg font-medium transition-colors border flex items-center gap-2 ${
                  syncingCovers
                    ? "bg-surface-alt text-text-muted cursor-wait"
                    : "bg-surface-alt hover:bg-surface border-border text-text"
                }`}
              >
                <svg
                  className={`w-4 h-4 ${syncingCovers ? "animate-spin" : ""}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  ></path>
                </svg>
                {syncingCovers ? "Syncing..." : "Sync Covers"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end pt-4">
        <button
          onClick={handleSave}
          disabled={processing}
          className="btn-primary flex items-center gap-2"
        >
          {processing ? (
            <div className="flex items-center gap-2">
              <svg
                className="animate-spin h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              <span>Saving...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"
                ></path>
              </svg>
              <span>Save Settings</span>
            </div>
          )}
        </button>
      </div>
    </div>
  );
}
