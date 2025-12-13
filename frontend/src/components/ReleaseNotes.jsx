import { h } from "preact";
import { releaseNotes } from "../data/releaseNotes";

export function ReleaseNotes({ isOpen, onClose }) {
    // If there are no notes, don't render anything
    if (releaseNotes.length === 0) return null;

    if (!isOpen) return null;

    return (
        <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={onClose}>
            <div
                class="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col animate-popout-open"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div class="px-6 py-4 border-b border-border flex justify-between items-center bg-surface-alt/50">
                    <div class="flex items-center gap-3">
                        <div class="p-2 bg-primary/10 rounded-lg text-primary">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                                <line x1="16" y1="13" x2="8" y2="13"></line>
                                <line x1="16" y1="17" x2="8" y2="17"></line>
                                <polyline points="10 9 9 9 8 9"></polyline>
                            </svg>
                        </div>
                        <div>
                            <h2 class="text-xl font-bold text-text">What's New</h2>
                            <p class="text-sm text-text-muted">Version {releaseNotes[0].version}</p>
                        </div>
                    </div>
                    <button onClick={onClose} class="text-text-muted hover:text-text transition-colors">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div class="p-6 overflow-y-auto custom-scrollbar">
                    {releaseNotes.map((release, index) => (
                        <div key={release.version} class={`mb-8 last:mb-0 ${index > 0 ? 'opacity-80' : ''}`}>
                            <div class="flex items-baseline justify-between mb-3">
                                <h3 class="text-lg font-semibold text-text">{release.title}</h3>
                                <span class="text-xs text-text-muted bg-surface-alt px-2 py-1 rounded-full border border-border">
                                    {release.date}
                                </span>
                            </div>
                            <ul class="space-y-2">
                                {release.changes.map((change, i) => (
                                    <li key={i} class="flex items-start gap-3 text-sm text-text-muted leading-relaxed">
                                        <span class="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
                                        <span>{change}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div class="p-4 border-t border-border bg-surface-alt/30 flex justify-end">
                    <button
                        onClick={onClose}
                        class="btn-primary"
                    >
                        Got it!
                    </button>
                </div>
            </div>
        </div>
    );
}
