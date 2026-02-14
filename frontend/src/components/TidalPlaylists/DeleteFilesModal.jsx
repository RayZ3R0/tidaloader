import { h } from "preact";
import { useState, useEffect } from "preact/hooks";
import { api } from "../../api/client";
import { useToastStore } from "../../stores/toastStore";

export function DeleteFilesModal({ uuid, playlistName, isOpen, onClose }) {
  const [loading, setLoading] = useState(false);
  const [files, setFiles] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [step, setStep] = useState("selection"); // "selection" | "confirm"
  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    if (isOpen) {
      loadFiles();
      setStep("selection");
      setSelectedFiles(new Set());
    }
  }, [isOpen, uuid]);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const res = await api.getPlaylistFiles(uuid);
      if (res.status === "success") {
        setFiles(res.files);
        // Default select all
        setSelectedFiles(new Set(res.files));
      }
    } catch (e) {
      addToast(`Failed to load files: ${e.message}`, "error");
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const toggleFile = (file) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(file)) {
      newSelected.delete(file);
    } else {
      newSelected.add(file);
    }
    setSelectedFiles(newSelected);
  };

  const toggleAll = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(files));
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you absolutely sure? This cannot be undone.")) {
      return;
    }
    setLoading(true);
    try {
      const filesToDelete = Array.from(selectedFiles);
      const res = await api.deletePlaylistFiles(uuid, filesToDelete);

      if (res.status === "success" || res.status === "partial_success") {
        addToast(`Deleted ${res.deleted_count} files`, "success");
        if (res.errors && res.errors.length > 0) {
          console.error(res.errors);
          addToast(`Some files failed to delete`, "warning");
        }
        onClose();
      }
    } catch (e) {
      addToast(`Delete failed: ${e.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="bg-surface card w-full max-w-2xl max-h-[80vh] flex flex-col animate-scale-in">
        {/* Header */}
        <div class="p-4 border-b border-border flex justify-between items-center">
          <h3 class="text-lg font-bold text-text">
            {step === "selection"
              ? `Delete Files: ${playlistName}`
              : "Confirm Deletion"}
          </h3>
          <button onClick={onClose} class="text-text-muted hover:text-text">
            <svg
              class="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div class="flex-1 overflow-y-auto p-4">
          {loading && step === "selection" ? (
            <div class="flex justify-center p-8">
              <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : step === "selection" ? (
            files.length === 0 ? (
              <div class="text-center p-8 text-text-muted">
                No downloaded files found for this playlist.
              </div>
            ) : (
              <div class="space-y-2">
                <div class="flex items-center justify-between mb-4">
                  <span class="text-sm text-text-muted">
                    {selectedFiles.size} selected
                  </span>
                  <button
                    onClick={toggleAll}
                    class="text-sm text-primary hover:underline"
                  >
                    {selectedFiles.size === files.length
                      ? "Deselect All"
                      : "Select All"}
                  </button>
                </div>
                {files.map((file) => (
                  <label
                    key={file}
                    class="flex items-start gap-3 p-2 hover:bg-surface-alt rounded cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={selectedFiles.has(file)}
                      onChange={() => toggleFile(file)}
                      class="mt-1"
                    />
                    <span class="text-sm text-text break-all font-mono opacity-80 group-hover:opacity-100">
                      {file}
                    </span>
                  </label>
                ))}
              </div>
            )
          ) : (
            <div class="text-center p-8 space-y-4">
              <div class="w-16 h-16 bg-red-100 dark:bg-red-900/30 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg
                  class="w-8 h-8"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              </div>
              <p class="text-lg font-medium text-text">
                Are you absolute sure?
              </p>
              <p class="text-text-muted">
                This will permanently delete{" "}
                <strong>{selectedFiles.size}</strong> files from your disk. This
                action cannot be undone.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div class="p-4 border-t border-border flex justify-end gap-3 bg-surface-alt/50">
          <button
            onClick={onClose}
            class="px-4 py-2 text-text-muted hover:text-text"
          >
            Cancel
          </button>

          {step === "selection" ? (
            <button
              onClick={() => setStep("confirm")}
              disabled={selectedFiles.size === 0 || files.length === 0}
              class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Delete Selected
            </button>
          ) : (
            <button
              onClick={handleDelete}
              disabled={loading}
              class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 flex items-center gap-2 transition-colors shadow-lg shadow-red-900/20"
            >
              {loading && (
                <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              )}
              Confirm Delete
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
