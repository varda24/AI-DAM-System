import { useState } from "react";
import axios from "axios";
import { AlertTriangle, CheckCircle, FolderPlus, HardDrive, Loader2, X } from "lucide-react";

const API_BASE_URL = "http://127.0.0.1:8000/api";

interface ScanStats {
  folder: string;
  files_scanned: number;
  files_added: number;
  files_updated: number;
  files_skipped: number;
  missing_files_marked: number;
  errors: { path: string; error: string }[];
  scanned_at: string;
}

interface ScannerModalProps {
  close: () => void;
  onSuccess: () => void;
}

export function ScannerModal({ close, onSuccess }: ScannerModalProps) {
  const [folderPath, setFolderPath] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<ScanStats | null>(null);

  async function handleScan(event: React.FormEvent) {
    event.preventDefault();
    const path = folderPath.trim();

    if (!path) {
      setError("Please enter a local directory path.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      setStats(null);

      const response = await axios.post<ScanStats>(`${API_BASE_URL}/scanner/local`, {
        folder_path: path,
      });

      setStats(response.data);
      onSuccess();
    } catch (err: any) {
      console.error(err);
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setError(String(err.response.data.detail));
      } else {
        setError("Failed to scan directory. Please verify that the path exists and is accessible.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="cleanup-modal scanner-modal" onClick={(e) => e.stopPropagation()}>
        <div className="preview-header">
          <div>
            <h3>Scan Local Directory</h3>
            <span>Index media and documents into AI-DAM</span>
          </div>
          <button className="icon-button" onClick={close} disabled={loading}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleScan} className="scanner-form">
          <div className="scanner-input-group">
            <label htmlFor="folder-path-input">
              <FolderPlus size={18} />
              <span>Target Directory Path</span>
            </label>
            <input
              id="folder-path-input"
              type="text"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              placeholder="e.g. C:\Users\YourName\Pictures or D:\Photos"
              disabled={loading}
              autoFocus
            />
            <small>Provide an absolute filesystem path. The scanner will recurse through subfolders safely without altering files.</small>
          </div>

          {error && (
            <div className="error-banner">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button type="button" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}

          {stats && (
            <div className="scan-results-card">
              <div className="scan-results-header">
                <CheckCircle size={20} className="success-icon" />
                <div>
                  <strong>Scan Completed Successfully</strong>
                  <span>{stats.folder}</span>
                </div>
              </div>

              <div className="scan-stats-grid">
                <div>
                  <strong>{stats.files_scanned.toLocaleString()}</strong>
                  <span>Scanned</span>
                </div>
                <div>
                  <strong>{stats.files_added.toLocaleString()}</strong>
                  <span>Added</span>
                </div>
                <div>
                  <strong>{stats.files_updated.toLocaleString()}</strong>
                  <span>Updated</span>
                </div>
                <div>
                  <strong>{stats.missing_files_marked.toLocaleString()}</strong>
                  <span>Marked Missing</span>
                </div>
              </div>

              {stats.files_skipped > 0 && (
                <div className="scan-warning-text">
                  Skipped {stats.files_skipped} unreadable file(s) due to permissions or OS locks.
                </div>
              )}
            </div>
          )}

          <div className="cleanup-modal-actions">
            <button type="button" className="secondary-button" onClick={close} disabled={loading}>
              {stats ? "Close" : "Cancel"}
            </button>
            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 size={16} className="spin" /> Scanning Directory...
                </>
              ) : (
                <>
                  <HardDrive size={16} /> Start Scan
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
