import { useEffect, useState } from "react";
import axios from "axios";
import { AlertTriangle, Check, CheckCircle2, Eye, FolderHeart, Sparkles, Tag } from "lucide-react";
import type { ApprovedCollection, Asset, CollectionSuggestion } from "../types";

const API_BASE_URL = "http://127.0.0.1:8000/api";

interface CollectionsViewProps {
  onPreviewAsset: (asset: Asset) => void;
}

export function CollectionsView({ onPreviewAsset }: CollectionsViewProps) {
  const [suggestions, setSuggestions] = useState<CollectionSuggestion[]>([]);
  const [approvedCollections, setApprovedCollections] = useState<ApprovedCollection[]>([]);
  const [loading, setLoading] = useState(false);
  const [approvingName, setApprovingName] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void loadData();
  }, []);

  async function loadData() {
    try {
      setLoading(true);
      setError("");

      const [sugRes, appRes] = await Promise.all([
        axios.get<{ suggestions: CollectionSuggestion[] }>(`${API_BASE_URL}/collections/suggestions`),
        axios.get<{ items: ApprovedCollection[] }>(`${API_BASE_URL}/collections`),
      ]);

      setSuggestions(sugRes.data.suggestions);
      setApprovedCollections(appRes.data.items);
    } catch (err) {
      console.error(err);
      setError("Failed to load collection data.");
    } finally {
      setLoading(false);
    }
  }

  async function approveSuggestion(suggestion: CollectionSuggestion) {
    try {
      setApprovingName(suggestion.name);
      setError("");
      setMessage("");

      const response = await axios.post(`${API_BASE_URL}/collections/approve`, {
        name: suggestion.name,
        description: suggestion.description,
        asset_ids: suggestion.asset_ids,
      });

      setMessage(`Collection "${response.data.name}" approved successfully with ${response.data.asset_count} items!`);
      await loadData();
    } catch (err) {
      console.error(err);
      setError("Failed to approve collection suggestion.");
    } finally {
      setApprovingName(null);
    }
  }

  return (
    <section className="collections-page">
      <section className="page-header">
        <div>
          <h2>Smart Collections & Events</h2>
          <p>AI-suggested event groupings and custom approved collections.</p>
        </div>
        <button className="secondary-button" onClick={loadData} disabled={loading}>
          <Sparkles size={16} /> Refresh Suggestions
        </button>
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

      <div className="collections-layout">
        {/* Section 1: AI Suggestions */}
        <section className="collection-section">
          <div className="section-title-row">
            <Sparkles size={20} className="ai-sparkle-icon" />
            <div>
              <h3>AI Event Suggestions</h3>
              <p>Generated automatically based on image captions and capture dates.</p>
            </div>
          </div>

          {suggestions.length === 0 ? (
            <div className="empty-state">
              <Sparkles size={36} />
              <h3>No AI Suggestions Yet</h3>
              <p>Run AI Image Analysis from the AI Images tab to generate event recommendations.</p>
            </div>
          ) : (
            <div className="suggestion-cards-list">
              {suggestions.map((suggestion, index) => (
                <article key={`${suggestion.name}-${index}`} className="suggestion-card">
                  <div className="suggestion-header">
                    <div>
                      <h4>{suggestion.name}</h4>
                      <p>{suggestion.description}</p>
                    </div>
                    <div className="suggestion-badge">
                      <span>Confidence: {Math.round(suggestion.confidence * 100)}%</span>
                    </div>
                  </div>

                  {suggestion.matched_keywords && suggestion.matched_keywords.length > 0 && (
                    <div className="keyword-tags">
                      <Tag size={13} />
                      {suggestion.matched_keywords.map((kw) => (
                        <span key={kw} className="kw-badge">
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="suggestion-preview-strip">
                    {suggestion.asset_ids.slice(0, 6).map((id) => (
                      <div
                        key={id}
                        className="strip-photo"
                        onDoubleClick={() =>
                          onPreviewAsset({
                            id,
                            name: `Asset ${id}`,
                            path: "",
                            file_type: "image",
                            mime_type: "image/*",
                          } as Asset)
                        }
                      >
                        <img src={`${API_BASE_URL}/assets/${id}/preview`} alt={`Asset ${id}`} />
                        <button
                          className="strip-preview-overlay"
                          onClick={() =>
                            onPreviewAsset({
                              id,
                              name: `Asset ${id}`,
                              path: "",
                              file_type: "image",
                              mime_type: "image/*",
                            } as Asset)
                          }
                          title="Preview Asset"
                        >
                          <Eye size={14} />
                        </button>
                      </div>
                    ))}
                    {suggestion.asset_ids.length > 6 && (
                      <div className="more-count">+{suggestion.asset_ids.length - 6} more</div>
                    )}
                  </div>

                  <div className="suggestion-footer">
                    <span>{suggestion.asset_count} items total</span>
                    <button
                      className="primary-button compact"
                      onClick={() => approveSuggestion(suggestion)}
                      disabled={approvingName === suggestion.name}
                    >
                      <Check size={15} />
                      {approvingName === suggestion.name ? "Approving..." : "Approve Collection"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        {/* Section 2: Approved Collections */}
        <section className="collection-section">
          <div className="section-title-row">
            <FolderHeart size={20} className="approved-icon" />
            <div>
              <h3>Approved Collections</h3>
              <p>Confirmed event collections saved in your library.</p>
            </div>
          </div>

          {approvedCollections.length === 0 ? (
            <div className="empty-state">
              <FolderHeart size={36} />
              <h3>No Approved Collections</h3>
              <p>Approve any AI suggestion above to create a persistent collection.</p>
            </div>
          ) : (
            <div className="approved-collections-grid">
              {approvedCollections.map((col) => (
                <article key={col.id} className="approved-collection-card">
                  <div className="col-card-icon">
                    <FolderHeart size={24} />
                  </div>
                  <div className="col-card-info">
                    <h4>{col.name}</h4>
                    <p>{col.description || "User-approved collection."}</p>
                    <div className="col-card-meta">
                      <span>{col.asset_count} asset(s)</span>
                      <span>Created {new Date(col.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
