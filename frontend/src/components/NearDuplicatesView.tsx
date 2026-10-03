import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../api";
import { AlertTriangle, CheckCircle2, Eye, Images, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import type { VisualSimilarGroup } from "../types";

interface NearDuplicatesViewProps {
  onPreviewAsset: (assetId: number) => void;
}

export function NearDuplicatesView({ onPreviewAsset }: NearDuplicatesViewProps) {
  const [groups, setGroups] = useState<VisualSimilarGroup[]>([]);
  const [totalSimilar, setTotalSimilar] = useState(0);
  const [totalGroups, setTotalGroups] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void fetchSimilarImages();
  }, [page]);

  async function fetchSimilarImages() {
    try {
      setLoading(true);
      setError("");
      const response = await axios.get<{
        total_groups: number;
        total_similar_images: number;
        page: number;
        total_pages: number;
        groups: VisualSimilarGroup[];
      }>(`${API_BASE_URL}/similarity/images`, { params: { page, page_size: 25 } });

      setGroups(response.data.groups);
      setTotalSimilar(response.data.total_similar_images);
      setTotalGroups(response.data.total_groups);
      setTotalPages(response.data.total_pages);
    } catch (err) {
      console.error(err);
      setError("Failed to load visually similar images.");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyzeHashes() {
    try {
      setAnalyzing(true);
      setError("");
      setMessage("");

      const response = await axios.post<{
        images_considered: number;
        images_analyzed: number;
      }>(`${API_BASE_URL}/similarity/analyze`);

      setMessage(
        `Perceptual hash analysis complete. Evaluated ${response.data.images_considered} image(s) and generated ${response.data.images_analyzed} pHash fingerprint(s).`
      );
      setPage(1);
      await fetchSimilarImages();
    } catch (err) {
      console.error(err);
      setError("Visual similarity hash calculation failed.");
    } finally {
      setAnalyzing(false);
    }
  }

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${units[i]}`;
  }

  return (
    <section className="near-duplicates-page">
      <section className="page-header">
        <div>
          <h2>Visual Near-Duplicates (pHash)</h2>
          <p>
            Find visually similar or resized images based on perceptual hashing (Hamming distance ≤ 8).
            {totalSimilar > 0 && ` (${totalSimilar} similar photos found in ${totalGroups} groups)`}
          </p>
        </div>
        <div className="header-actions">
          <button className="primary-button" onClick={handleAnalyzeHashes} disabled={analyzing || loading}>
            {analyzing ? <Loader2 size={16} className="spin" /> : <Images size={16} />}
            {analyzing ? "Generating pHashes..." : "1. Analyze Visual Similarity"}
          </button>
          <button className="secondary-button" onClick={fetchSimilarImages} disabled={loading}>
            <RefreshCw size={16} /> Refresh
          </button>
        </div>
      </section>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
          <button onClick={() => setError("")}>×</button>
        </div>
      )}

      {message && (
        <div className="success-banner">
          <CheckCircle2 size={18} />
          <span>{message}</span>
          <button onClick={() => setMessage("")}>×</button>
        </div>
      )}

      <div className="safety-notice">
        <ShieldCheck size={18} />
        <div>
          <strong>Review-Only Interface</strong>
          <span>This view displays visually similar images for comparison. No files are automatically deleted.</span>
        </div>
      </div>

      {loading ? (
        <div className="empty-state">
          <Loader2 size={42} className="spin" />
          <h3>Loading Visual Similarity Groups</h3>
          <p>Please wait while perceptual hash matches are compiled.</p>
        </div>
      ) : groups.length === 0 ? (
        <div className="empty-state">
          <Images size={42} />
          <h3>No Visual Near-Duplicates Found</h3>
          <p>Click "1. Analyze Visual Similarity" to compute pHash fingerprints across your indexed images.</p>
        </div>
      ) : (
        <div className="similarity-groups-list">
          {groups.map((group) => (
            <article key={group.id} className="similarity-group-card">
              <div className="group-card-header">
                <div>
                  <h3>Similar Image Group #{group.id}</h3>
                  <span>{group.asset_count} visually matching photos</span>
                </div>
              </div>

              <div className="similarity-grid-items">
                {group.assets.map((asset) => (
                  <div
                    key={asset.id}
                    className="similar-asset-card"
                    onDoubleClick={() => asset.source === "local_pc" && onPreviewAsset(asset.id)}
                  >
                    <div className="similar-img-wrapper">
                      {asset.source === "local_pc" ? (
                        <img src={`${API_BASE_URL}/assets/${asset.id}/preview`} alt={asset.name} />
                      ) : (
                        <a className="drive-similar-link" href={asset.web_view_link || undefined} target="_blank" rel="noreferrer">
                          Open Drive asset
                        </a>
                      )}
                      {asset.source === "local_pc" && <button
                        className="preview-badge-btn center"
                        onClick={() => onPreviewAsset(asset.id)}
                        title="Preview Image"
                      >
                        <Eye size={14} /> View
                      </button>}
                    </div>

                    <div className="similar-asset-info">
                      <strong title={asset.name}>{asset.name}</strong>
                      <span className="path" title={asset.path}>
                        {asset.source || "local_pc"} · {asset.path}
                      </span>
                      <div className="meta-row">
                        <small>{formatBytes(asset.size_bytes)}</small>
                        <code title="Perceptual Hash (pHash)">pHash: {asset.perceptual_hash}</code>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
      {totalPages > 1 && (
        <div className="pagination">
          <button disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button>
          <span>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage((current) => current + 1)}>Next</button>
        </div>
      )}
    </section>
  );
}
