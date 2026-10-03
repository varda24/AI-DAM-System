import { FileText, RefreshCw, ScanText, ShieldCheck, AlertTriangle, Clock3, CircleHelp } from "lucide-react";
import type { Asset } from "../types";

export interface DocumentAnalysis {
  id: number;
  asset_id: number;
  document_type: string | null;
  confidence: number | null;
  extracted_text: string | null;
  extracted_name: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  document_status: string;
  ocr_used: boolean;
  page_count: number | null;
  status: string;
  error_message: string | null;
  analyzed_at: string | null;
  name?: string | null;
  path?: string | null;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

function statusMeta(status: string) {
  switch (status) {
    case "VALID":
      return { icon: <ShieldCheck size={16} />, label: "Valid", className: "valid" };
    case "EXPIRING SOON":
      return { icon: <Clock3 size={16} />, label: "Expiring Soon", className: "warning" };
    case "EXPIRED":
      return { icon: <AlertTriangle size={16} />, label: "Expired", className: "expired" };
    default:
      return { icon: <CircleHelp size={16} />, label: "Unknown", className: "unknown" };
  }
}

function confidenceLabel(value: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 100)}%`;
}

export default function DocumentIntelligence({
  asset,
  analysis,
  loading,
  onAnalyze,
  onReanalyze,
}: {
  asset: Asset;
  analysis: DocumentAnalysis | null;
  loading: boolean;
  onAnalyze: (assetId: number) => void;
  onReanalyze: (assetId: number) => void;
}) {
  const status = statusMeta(analysis?.document_status || "UNKNOWN");

  return (
    <section className="asset-analysis-result" style={{ marginTop: 16 }}>
      <div className="analysis-result-heading">
        <FileText size={16} />
        <h4>Document Intelligence</h4>
      </div>

      {!analysis ? (
        <div style={{ display: "grid", gap: 10 }}>
          <p style={{ margin: 0 }}>
            Analyze this document to extract its type, text, dates and validity status.
          </p>
          <button
            className="primary-button"
            type="button"
            onClick={() => onAnalyze(asset.id)}
            disabled={loading || asset.is_missing}
          >
            {loading ? <RefreshCw size={16} className="spin" /> : <ScanText size={16} />}
            {loading ? "Analyzing document..." : "Analyze Document"}
          </button>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 10px",
                borderRadius: 999,
                fontSize: 12,
                fontWeight: 700,
                background:
                  status.className === "valid"
                    ? "rgba(34, 197, 94, 0.12)"
                    : status.className === "warning"
                      ? "rgba(245, 158, 11, 0.14)"
                      : status.className === "expired"
                        ? "rgba(239, 68, 68, 0.12)"
                        : "rgba(100, 116, 139, 0.12)",
                color:
                  status.className === "valid"
                    ? "#15803d"
                    : status.className === "warning"
                      ? "#b45309"
                      : status.className === "expired"
                        ? "#b91c1c"
                        : "#475569",
              }}
            >
              {status.icon}
              {status.label}
            </span>
            <button
              className="secondary-button compact"
              type="button"
              onClick={() => onReanalyze(asset.id)}
              disabled={loading}
            >
              <RefreshCw size={13} className={loading ? "spin" : ""} />
              {loading ? "Analyzing..." : "Re-analyze"}
            </button>
          </div>

          {analysis.error_message && (
            <div className="error-banner" style={{ margin: 0 }}>
              <AlertTriangle size={15} />
              <span>{analysis.error_message}</span>
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
              gap: 8,
            }}
          >
            <Metric label="Document Type" value={analysis.document_type || "Unknown"} />
            <Metric label="Confidence" value={confidenceLabel(analysis.confidence)} />
            <Metric label="Pages" value={analysis.page_count?.toString() || "-"} />
            <Metric label="OCR" value={analysis.ocr_used ? "Used" : "Not required"} />
            <Metric label="Issue Date" value={formatDate(analysis.issue_date)} />
            <Metric label="Expiry Date" value={formatDate(analysis.expiry_date)} />
            <Metric label="Extracted Name" value={analysis.extracted_name || "-"} />
          </div>

          <div>
            <strong style={{ display: "block", marginBottom: 6 }}>Extracted Text</strong>
            <div
              style={{
                maxHeight: 190,
                overflow: "auto",
                padding: 10,
                borderRadius: 8,
                border: "1px solid rgba(100,116,139,0.18)",
                background: "rgba(148,163,184,0.06)",
                whiteSpace: "pre-wrap",
                fontSize: 12,
                lineHeight: 1.55,
              }}
            >
              {analysis.extracted_text?.trim() || "No text was extracted from this document."}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "9px 10px",
        borderRadius: 8,
        border: "1px solid rgba(100,116,139,0.16)",
        background: "rgba(148,163,184,0.05)",
        minWidth: 0,
      }}
    >
      <span style={{ display: "block", fontSize: 11, opacity: 0.7, marginBottom: 3 }}>{label}</span>
      <strong style={{ display: "block", fontSize: 13, overflowWrap: "anywhere" }}>{value}</strong>
    </div>
  );
}
