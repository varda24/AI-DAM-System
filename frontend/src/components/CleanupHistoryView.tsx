import { useEffect, useState } from "react";
import axios from "axios";
import { AlertTriangle, CheckCircle2, History, Info, Loader2, RefreshCw, RotateCcw, X } from "lucide-react";
import type { CleanupOperationDetail, CleanupOperationRecord } from "../types";

const API_BASE_URL = "http://127.0.0.1:8000/api";

export function CleanupHistoryView() {
  const [operations, setOperations] = useState<CleanupOperationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [restoringId, setRestoringId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [selectedOpDetail, setSelectedOpDetail] = useState<CleanupOperationDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    void fetchHistory();
  }, []);

  async function fetchHistory() {
    try {
      setLoading(true);
      setError("");
      const response = await axios.get<{ operations: CleanupOperationRecord[] }>(
        `${API_BASE_URL}/cleanup/history`
      );
      setOperations(response.data.operations);
    } catch (err) {
      console.error(err);
      setError("Failed to load cleanup operation history.");
    } finally {
      setLoading(false);
    }
  }

  async function viewOperationDetails(operationId: number) {
    try {
      setDetailLoading(true);
      setError("");
      const response = await axios.get<CleanupOperationDetail>(
        `${API_BASE_URL}/cleanup/${operationId}`
      );
      setSelectedOpDetail(response.data);
    } catch (err) {
      console.error(err);
      setError("Failed to load operation details.");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleRestore(operationId: number) {
    if (!window.confirm(`Are you sure you want to restore all files from operation #${operationId} to their original locations?`)) {
      return;
    }

    try {
      setRestoringId(operationId);
      setError("");
      setMessage("");

      const response = await axios.post<{
        operation_id: number;
        restored_files: number;
        failed_files: number;
      }>(`${API_BASE_URL}/cleanup/${operationId}/restore`);

      setMessage(
        `Restore completed for operation #${operationId}. Restored ${response.data.restored_files} file(s) successfully.${
          response.data.failed_files > 0 ? ` (${response.data.failed_files} failed)` : ""
        }`
      );

      if (selectedOpDetail && selectedOpDetail.id === operationId) {
        await viewOperationDetails(operationId);
      }
      await fetchHistory();
    } catch (err: any) {
      console.error(err);
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setError(String(err.response.data.detail));
      } else {
        setError("Failed to restore files from cleanup operation.");
      }
    } finally {
      setRestoringId(null);
    }
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
  }

  return (
    <section className="cleanup-history-page">
      <section className="page-header">
        <div>
          <h2>Cleanup Audit & File Restoration</h2>
          <p>Review past file cleanup operations and restore moved items from the AI-DAM recovery directory.</p>
        </div>
        <button className="secondary-button" onClick={fetchHistory} disabled={loading}>
          <RefreshCw size={16} /> Refresh
        </button>
      </section>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
          <button onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}

      {message && (
        <div className="success-banner">
          <CheckCircle2 size={18} />
          <span>{message}</span>
          <button onClick={() => setMessage("")}>
            <X size={16} />
          </button>
        </div>
      )}

      {loading ? (
        <div className="empty-state">
          <Loader2 size={42} className="spin" />
          <h3>Loading Cleanup Audit Log</h3>
          <p>Retrieving past operation history...</p>
        </div>
      ) : operations.length === 0 ? (
        <div className="empty-state">
          <History size={42} />
          <h3>No Cleanup History Found</h3>
          <p>Perform a file cleanup from the Duplicates tab to generate audit records.</p>
        </div>
      ) : (
        <div className="history-table-wrapper">
          <table className="asset-table">
            <thead>
              <tr>
                <th>Operation ID</th>
                <th>Status</th>
                <th>Action</th>
                <th>Assets Moved</th>
                <th>Storage Size</th>
                <th>Created At</th>
                <th>Completed At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {operations.map((op) => (
                <tr key={op.id}>
                  <td>
                    <strong>#{op.id}</strong>
                  </td>
                  <td>
                    <span className={`status-pill ${op.status.toLowerCase()}`}>{op.status}</span>
                  </td>
                  <td>{op.action}</td>
                  <td>{op.asset_count} item(s)</td>
                  <td>{formatBytes(op.total_size_bytes)}</td>
                  <td>{op.created_at ? new Date(op.created_at).toLocaleString() : "-"}</td>
                  <td>{op.completed_at ? new Date(op.completed_at).toLocaleString() : "-"}</td>
                  <td>
                    <div className="table-action-btns">
                      <button
                        className="secondary-button compact"
                        onClick={() => viewOperationDetails(op.id)}
                        disabled={detailLoading}
                      >
                        <Info size={14} /> Inspect
                      </button>
                      <button
                        className="primary-button compact"
                        onClick={() => handleRestore(op.id)}
                        disabled={restoringId === op.id || op.status === "RESTORED"}
                      >
                        {restoringId === op.id ? (
                          <Loader2 size={14} className="spin" />
                        ) : (
                          <RotateCcw size={14} />
                        )}
                        Restore
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Operation Detail Modal */}
      {selectedOpDetail && (
        <div className="modal-backdrop" onClick={() => setSelectedOpDetail(null)}>
          <div className="cleanup-modal" onClick={(e) => e.stopPropagation()}>
            <div className="preview-header">
              <div>
                <h3>Cleanup Operation #{selectedOpDetail.id} Details</h3>
                <span>
                  Created {selectedOpDetail.created_at ? new Date(selectedOpDetail.created_at).toLocaleString() : ""}
                </span>
              </div>
              <button className="icon-button" onClick={() => setSelectedOpDetail(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="cleanup-summary">
              <div>
                <strong>{selectedOpDetail.asset_count}</strong>
                <span>Items in operation</span>
              </div>
              <div>
                <strong>{formatBytes(selectedOpDetail.total_size_bytes)}</strong>
                <span>Total Storage</span>
              </div>
            </div>

            <div className="cleanup-preview-list">
              {selectedOpDetail.items.map((item) => (
                <div className="cleanup-preview-item" key={item.id}>
                  <div>
                    <strong>Original: {item.original_path}</strong>
                    {item.recovery_path && <span>Recovery: {item.recovery_path}</span>}
                    {item.error_message && <small className="error-text">Error: {item.error_message}</small>}
                  </div>
                  <div className="item-meta-right">
                    <span>{formatBytes(item.size_bytes)}</span>
                    <span className={`status-pill ${item.status.toLowerCase()}`}>{item.status}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="cleanup-modal-actions">
              <button className="secondary-button" onClick={() => setSelectedOpDetail(null)}>
                Close
              </button>
              <button
                className="primary-button"
                onClick={() => handleRestore(selectedOpDetail.id)}
                disabled={restoringId === selectedOpDetail.id}
              >
                <RotateCcw size={15} /> Restore All Items
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
