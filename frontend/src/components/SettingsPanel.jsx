import { h } from "preact";
import { useDownloadStore } from "../stores/downloadStore";

const QUALITY_OPTIONS = [
    {
        value: "HI_RES_LOSSLESS",
        label: "Hi-Res FLAC",
        description: "Up to 24-bit/192kHz",
    },
    { value: "LOSSLESS", label: "FLAC", description: "16-bit/44.1kHz" },
    { value: "MP3_256", label: "MP3 256kbps", description: "Transcoded MP3 (libmp3lame)" },
    { value: "MP3_128", label: "MP3 128kbps", description: "Transcoded MP3 (smaller size)" },
    { value: "OPUS_192VBR", label: "Opus 192kbps VBR", description: "Variable bitrate Opus (192kbps target)" },
    { value: "HIGH", label: "320kbps AAC", description: "High quality AAC" },
    { value: "LOW", label: "96kbps AAC", description: "Low quality AAC" },
];

const TEMPLATE_OPTIONS = [
    { value: "{Artist}/{Album}/{TrackNumber} - {Title}", label: "Artist/Album/Track - Title (Default)" },
    { value: "{Album}/{TrackNumber} - {Title}", label: "Album/Track - Title" },
    { value: "{Artist} - {Title}", label: "Artist - Title" },
    { value: "{Artist}/{Album}/{Title}", label: "Artist/Album/Title" },
];

export function SettingsPanel() {
    const quality = useDownloadStore((state) => state.quality);
    const setQuality = useDownloadStore((state) => state.setQuality);

    const organizationTemplate = useDownloadStore((state) => state.organizationTemplate);
    const setOrganizationTemplate = useDownloadStore((state) => state.setOrganizationTemplate);

    const groupCompilations = useDownloadStore((state) => state.groupCompilations);
    const setGroupCompilations = useDownloadStore((state) => state.setGroupCompilations);

    const runBeets = useDownloadStore((state) => state.runBeets);
    const setRunBeets = useDownloadStore((state) => state.setRunBeets);

    return (
        <div class="space-y-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Audio Quality */}
                <div class="space-y-3">
                    <label for="quality-select" class="block text-sm font-semibold text-text">
                        Audio Quality
                    </label>
                    <select
                        id="quality-select"
                        value={quality}
                        onChange={(e) => setQuality(e.target.value)}
                        class="input-field cursor-pointer w-full"
                    >
                        {QUALITY_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label} - {option.description}
                            </option>
                        ))}
                    </select>
                </div>

                {/* File Organization */}
                <div class="space-y-3">
                    <label for="template-select" class="block text-sm font-semibold text-text">
                        File Organization
                    </label>
                    <select
                        id="template-select"
                        value={organizationTemplate}
                        onChange={(e) => setOrganizationTemplate(e.target.value)}
                        class="input-field cursor-pointer w-full mb-2"
                    >
                        {TEMPLATE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                        {!TEMPLATE_OPTIONS.find(o => o.value === organizationTemplate) && (
                            <option value={organizationTemplate}>Custom Template</option>
                        )}
                    </select>

                    <input
                        type="text"
                        value={organizationTemplate}
                        onInput={(e) => setOrganizationTemplate(e.target.value)}
                        class="input-field w-full text-sm font-mono"
                        placeholder="Custom template..."
                    />
                    <p class="text-xs text-text-muted">
                        Available: &#123;Artist&#125;, &#123;Album&#125;, &#123;Title&#125;, &#123;TrackNumber&#125;, &#123;Year&#125;
                    </p>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-border">
                {/* Toggles */}
                <div class="flex items-center justify-between p-2 rounded-lg hover:bg-surface-alt transition-colors">
                    <div class="space-y-0.5">
                        <label class="text-sm font-semibold text-text cursor-pointer" onClick={() => setGroupCompilations(!groupCompilations)}>Group Compilations</label>
                        <p class="text-xs text-text-muted">Put tracks in "Compilations" folder if Various Artists</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input
                            type="checkbox"
                            checked={groupCompilations}
                            onChange={(e) => setGroupCompilations(e.target.checked)}
                            class="sr-only peer"
                        />
                        <div class="w-11 h-6 bg-surface peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                </div>

                <div class="flex items-center justify-between p-2 rounded-lg hover:bg-surface-alt transition-colors">
                    <div class="space-y-0.5">
                        <label class="text-sm font-semibold text-text cursor-pointer" onClick={() => setRunBeets(!runBeets)}>Beets Integration</label>
                        <p class="text-xs text-text-muted">Run "beet import" after download (requires beets)</p>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input
                            type="checkbox"
                            checked={runBeets}
                            onChange={(e) => setRunBeets(e.target.checked)}
                            class="sr-only peer"
                        />
                        <div class="w-11 h-6 bg-surface peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                </div>
            </div>
        </div>
    );
}
