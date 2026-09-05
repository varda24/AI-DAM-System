import { useEffect, useState } from "react";
import axios from "axios";
import { AlertTriangle, CheckCircle, Edit3, Eye, Loader2, RefreshCw, UserCheck, Users } from "lucide-react";
import type { Asset, PersonCluster } from "../types";

const API_BASE_URL = "http://127.0.0.1:8000/api";

interface PeopleViewProps {
  onPreviewAsset: (asset: Asset) => void;
}

export function PeopleView({ onPreviewAsset }: PeopleViewProps) {
  const [clusters, setClusters] = useState<PersonCluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [clustering, setClustering] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [editingClusterId, setEditingClusterId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState("");

  useEffect(() => {
    void fetchClusters();
  }, []);

  async function fetchClusters() {
    try {
      setLoading(true);
      setError("");
      const response = await axios.get<{ total_clusters: number; clusters: PersonCluster[] }>(
        `${API_BASE_URL}/people/clusters`
      );
      setClusters(response.data.clusters);
    } catch (err) {
      console.error(err);
      setError("Failed to load person clusters.");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyzeFaces() {
    try {
      setAnalyzing(true);
      setError("");
      setMessage("");
      const response = await axios.post<{
        images_found: number;
        images_analyzed: number;
        faces_detected: number;
      }>(`${API_BASE_URL}/people/analyze`);

      setMessage(
        `Face detection complete. Analyzed ${response.data.images_analyzed} image(s) and detected ${response.data.faces_detected} face(s).`
      );
      await fetchClusters();
    } catch (err) {
      console.error(err);
      setError("Face analysis failed. Please ensure InsightFace is installed.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleClusterPeople() {
    try {
      setClustering(true);
      setError("");
      setMessage("");
      const response = await axios.post<{
        faces_considered: number;
        clusters_created: number;
      }>(`${API_BASE_URL}/people/cluster`);

      setMessage(
        `Person clustering complete. Formed ${response.data.clusters_created} cluster(s) from ${response.data.faces_considered} face embedding(s).`
      );
      await fetchClusters();
    } catch (err) {
      console.error(err);
      setError("Person clustering failed.");
    } finally {
      setClustering(false);
    }
  }

  async function saveClusterLabel(clusterId: number) {
    try {
      setError("");
      const response = await axios.patch(`${API_BASE_URL}/people/clusters/${clusterId}`, {
        label: editLabel,
      });

      setClusters((prev) =>
        prev.map((c) => (c.id === clusterId ? { ...c, label: response.data.label } : c))
      );
      setEditingClusterId(null);
      setEditLabel("");
    } catch (err) {
      console.error(err);
      setError("Failed to update cluster label.");
    }
  }

  return (
    <section className="people-page">
      <section className="page-header">
        <div>
          <h2>People & Face Recognition</h2>
          <p>Detect facial features using AI and group photos by identified individuals.</p>
        </div>
        <div className="header-actions">
          <button className="secondary-button" onClick={handleAnalyzeFaces} disabled={analyzing || loading}>
            {analyzing ? <Loader2 size={16} className="spin" /> : <Users size={16} />}
            {analyzing ? "Analyzing Faces..." : "1. Detect Faces"}
          </button>
          <button className="primary-button" onClick={handleClusterPeople} disabled={clustering || loading}>
            {clustering ? <Loader2 size={16} className="spin" /> : <UserCheck size={16} />}
            {clustering ? "Clustering..." : "2. Cluster People"}
          </button>
          <button className="icon-button header-refresh" onClick={fetchClusters} title="Refresh Clusters">
            <RefreshCw size={18} />
          </button>
        </div>
      </section>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
          <button onClick={() => setError("")}>
            <XIcon />
          </button>
        </div>
      )}

      {message && (
        <div className="success-banner">
          <CheckCircle size={18} />
          <span>{message}</span>
          <button onClick={() => setMessage("")}>
            <XIcon />
          </button>
        </div>
      )}

      {loading ? (
        <div className="empty-state">
          <Loader2 size={42} className="spin" />
          <h3>Loading Person Clusters</h3>
          <p>Please wait while face embeddings and clusters are retrieved.</p>
        </div>
      ) : clusters.length === 0 ? (
        <div className="empty-state">
          <Users size={42} />
          <h3>No Person Clusters Formed</h3>
          <p>Click "1. Detect Faces" to extract face embeddings from images, then "2. Cluster People" to group them.</p>
        </div>
      ) : (
        <div className="people-clusters-grid">
          {clusters.map((cluster) => (
            <article className="person-cluster-card" key={cluster.id}>
              <div className="cluster-card-header">
                <div>
                  {editingClusterId === cluster.id ? (
                    <div className="label-edit-form">
                      <input
                        type="text"
                        value={editLabel}
                        onChange={(e) => setEditLabel(e.target.value)}
                        placeholder="Enter person name..."
                        autoFocus
                      />
                      <button className="primary-button compact" onClick={() => saveClusterLabel(cluster.id)}>
                        Save
                      </button>
                      <button className="secondary-button compact" onClick={() => setEditingClusterId(null)}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="label-display">
                      <h3>{cluster.label || `Person Cluster #${cluster.id}`}</h3>
                      <button
                        className="icon-button edit-btn"
                        onClick={() => {
                          setEditingClusterId(cluster.id);
                          setEditLabel(cluster.label || "");
                        }}
                        title="Edit Name"
                      >
                        <Edit3 size={15} />
                      </button>
                    </div>
                  )}
                  <div className="cluster-meta-badges">
                    <span className="badge face-count">{cluster.face_count} Face(s)</span>
                    {cluster.confidence !== null && (
                      <span className="badge confidence">Confidence: {Math.round(cluster.confidence * 100)}%</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="cluster-photo-gallery">
                {cluster.assets && cluster.assets.length > 0 ? (
                  cluster.assets.map((asset) => (
                    <div
                      key={asset.id}
                      className="cluster-photo-thumb"
                      onDoubleClick={() => onPreviewAsset(asset as Asset)}
                    >
                      <img src={`${API_BASE_URL}/assets/${asset.id}/preview`} alt={asset.name} />
                      <div className="thumb-hover-overlay">
                        <button
                          className="preview-badge-btn"
                          onClick={() => onPreviewAsset(asset as Asset)}
                          title="Preview Asset"
                        >
                          <Eye size={14} /> Preview
                        </button>
                      </div>
                      <span className="thumb-name">{asset.name}</span>
                    </div>
                  ))
                ) : (
                  <div className="no-photos-text">Associated asset IDs: {cluster.asset_ids.join(", ")}</div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function XIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
