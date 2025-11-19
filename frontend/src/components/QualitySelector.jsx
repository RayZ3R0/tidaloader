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
  { value: "OPUS_192VBR", label: "Opus 192kbps VBR ", description: "Variable bitrate Opus (192kbps target)" },
  { value: "HIGH", label: "320kbps AAC", description: "High quality AAC" },
  { value: "LOW", label: "96kbps AAC", description: "Low quality AAC" },
];

export function QualitySelector() {
  const quality = useDownloadStore((state) => state.quality);
  const setQuality = useDownloadStore((state) => state.setQuality);

  return (
    <div class="space-y-3">
      <label for="quality-select" class="block text-sm font-semibold text-text">
        Audio Quality
      </label>
      <select
        id="quality-select"
        value={quality}
        onChange={(e) => setQuality(e.target.value)}
        class="input-field cursor-pointer"
      >
        {QUALITY_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label} - {option.description}
          </option>
        ))}
      </select>
    </div>
  );
}
