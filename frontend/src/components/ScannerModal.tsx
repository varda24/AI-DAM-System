import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../api";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  HardDrive,
  Loader2,
  Search,
  X,
} from "lucide-react";
import "./ScannerModal.css";

type CheckState = "checked" | "unchecked" | "mixed";

interface FolderNode {
  path: string;
  name: string;
  children?: FolderNode[];
  expanded?: boolean;
  loading?: boolean;
}

interface ScanStats {
  folder: string | null;
  included_paths: string[];
  excluded_paths: string[];
  files_scanned: number;
  files_added: number;
  files_updated: number;
  files_skipped: number;
  missing_files_marked: number;
  errors: { path: string; error: string }[];
  scanned_at: string;
}

interface Estimate {
  estimated_files: number;
  estimated_bytes: number;
  basis: string;
}

interface ScannerModalProps {
  close: () => void;
  onSuccess: () => void;
}

function normalizedPath(path: string): string {
  return path.replaceAll("/", "\\").replace(/[\\]+$/, "").toLocaleLowerCase();
}

function isPathInside(path: string, parent: string, includeSelf = true): boolean {
  const childValue = normalizedPath(path);
  const parentValue = normalizedPath(parent);
  if (childValue === parentValue) return includeSelf;
  return childValue.startsWith(`${parentValue}\\`);
}

function parentPath(path: string): string {
  const normalized = path.replaceAll("/", "\\").replace(/[\\]+$/, "");
  const separator = normalized.lastIndexOf("\\");
  if (separator < 0) return normalized;
  if (separator === 2 && /^[a-z]:/i.test(normalized)) return normalized.slice(0, 3);
  return normalized.slice(0, separator) || normalized;
}

function selectedByRules(path: string, included: string[], excluded: string[]): boolean {
  const rules = [
    ...included.map((rulePath) => ({ path: rulePath, selected: true })),
    ...excluded.map((rulePath) => ({ path: rulePath, selected: false })),
  ].filter((rule) => isPathInside(path, rule.path));
  rules.sort((first, second) => normalizedPath(second.path).length - normalizedPath(first.path).length);
  return rules[0]?.selected ?? false;
}

function getCheckState(path: string, included: string[], excluded: string[]): CheckState {
  const selected = selectedByRules(path, included, excluded);
  const hasOppositeDescendant = selected
    ? excluded.some((excludedPath) => isPathInside(excludedPath, path, false))
    : included.some((includedPath) => isPathInside(includedPath, path, false));
  return hasOppositeDescendant ? "mixed" : selected ? "checked" : "unchecked";
}

function updateNode(
  nodes: FolderNode[],
  targetPath: string,
  update: (node: FolderNode) => FolderNode,
): FolderNode[] {
  return nodes.map((node) => {
    if (normalizedPath(node.path) === normalizedPath(targetPath)) return update(node);
    return node.children
      ? { ...node, children: updateNode(node.children, targetPath, update) }
      : node;
  });
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function FolderRow({
  node,
  depth,
  included,
  excluded,
  onToggleSelection,
  onToggleExpand,
}: {
  node: FolderNode;
  depth: number;
  included: string[];
  excluded: string[];
  onToggleSelection: (path: string) => void;
  onToggleExpand: (node: FolderNode) => void;
}) {
  const checkboxRef = useRef<HTMLInputElement>(null);
  const state = getCheckState(node.path, included, excluded);
  useEffect(() => {
    if (checkboxRef.current) checkboxRef.current.indeterminate = state === "mixed";
  }, [state]);

  return (
    <>
      <div className="scan-folder-row" style={{ "--tree-depth": depth } as React.CSSProperties}>
        <button
          type="button"
          className="scan-tree-expander"
          onClick={() => onToggleExpand(node)}
          aria-label={`${node.expanded ? "Collapse" : "Expand"} ${node.name}`}
          title={node.expanded ? "Collapse folder" : "Load and expand folder"}
        >
          {node.loading ? <Loader2 size={15} className="spin" /> : node.expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
        <input
          ref={checkboxRef}
          type="checkbox"
          checked={state === "checked"}
          aria-checked={state === "mixed" ? "mixed" : state === "checked"}
          onChange={() => onToggleSelection(node.path)}
          title={state === "mixed" ? "Some descendants are selected" : state === "checked" ? "Selected recursively" : "Excluded recursively"}
        />
        {node.expanded ? <FolderOpen size={17} /> : <Folder size={17} />}
        <button type="button" className="scan-folder-name" onClick={() => onToggleExpand(node)} title={node.path}>
          <strong>{node.name}</strong>
          <small>{node.path}</small>
        </button>
      </div>
      {node.expanded && node.children?.map((child) => (
        <FolderRow
          key={child.path}
          node={child}
          depth={depth + 1}
          included={included}
          excluded={excluded}
          onToggleSelection={onToggleSelection}
          onToggleExpand={onToggleExpand}
        />
      ))}
      {node.expanded && node.children?.length === 0 && (
        <div className="scan-folder-empty" style={{ "--tree-depth": depth + 1 } as React.CSSProperties}>No subfolders</div>
      )}
    </>
  );
}

export function ScannerModal({ close, onSuccess }: ScannerModalProps) {
  const [roots, setRoots] = useState<FolderNode[]>([]);
  const [includedPaths, setIncludedPaths] = useState<string[]>([]);
  const [excludedPaths, setExcludedPaths] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<FolderNode[]>([]);
  const [searchTruncated, setSearchTruncated] = useState(false);
  const [treeLoading, setTreeLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<ScanStats | null>(null);
  const [estimate, setEstimate] = useState<Estimate>({ estimated_files: 0, estimated_bytes: 0, basis: "currently indexed assets" });
  const [estimateLoading, setEstimateLoading] = useState(false);

  useEffect(() => {
    void axios.get(`${API_BASE_URL}/scanner/local/tree`)
      .then((response) => setRoots(response.data.roots.map((root: FolderNode) => ({ ...root, children: undefined }))))
      .catch((requestError) => {
        console.error(requestError);
        setError("Could not discover local drives.");
      })
      .finally(() => setTreeLoading(false));
  }, []);

  useEffect(() => {
    if (!search.trim()) {
      setSearchResults([]);
      setSearchTruncated(false);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void axios.get(`${API_BASE_URL}/scanner/local/tree/search`, {
        params: { q: search.trim() },
        signal: controller.signal,
      }).then((response) => {
        setSearchResults(response.data.folders.map((folder: FolderNode) => ({ ...folder, children: undefined })));
        setSearchTruncated(Boolean(response.data.truncated));
      }).catch((requestError) => {
        if (!axios.isCancel(requestError)) setError("Folder search failed.");
      });
    }, 450);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [search]);

  useEffect(() => {
    if (includedPaths.length === 0) {
      setEstimate({ estimated_files: 0, estimated_bytes: 0, basis: "currently indexed assets" });
      return;
    }
    const controller = new AbortController();
    setEstimateLoading(true);
    void axios.post(`${API_BASE_URL}/scanner/local/estimate`, {
      included_paths: includedPaths,
      excluded_paths: excludedPaths,
    }, { signal: controller.signal })
      .then((response) => setEstimate(response.data))
      .catch((requestError) => {
        if (!axios.isCancel(requestError)) setEstimate({ estimated_files: 0, estimated_bytes: 0, basis: "currently indexed assets" });
      })
      .finally(() => setEstimateLoading(false));
    return () => controller.abort();
  }, [includedPaths, excludedPaths]);

  async function toggleExpand(node: FolderNode) {
    if (node.expanded) {
      setRoots((current) => updateNode(current, node.path, (value) => ({ ...value, expanded: false })));
      return;
    }
    if (node.children !== undefined) {
      setRoots((current) => updateNode(current, node.path, (value) => ({ ...value, expanded: true })));
      return;
    }
    setRoots((current) => updateNode(current, node.path, (value) => ({ ...value, loading: true })));
    try {
      const response = await axios.get(`${API_BASE_URL}/scanner/local/tree`, { params: { parent_path: node.path } });
      setRoots((current) => updateNode(current, node.path, (value) => ({
        ...value,
        expanded: true,
        loading: false,
        children: response.data.folders.map((folder: FolderNode) => ({ ...folder, children: undefined })),
      })));
    } catch (requestError) {
      console.error(requestError);
      setRoots((current) => updateNode(current, node.path, (value) => ({ ...value, loading: false })));
      setError(`Could not read ${node.path}.`);
    }
  }

  function toggleSelection(path: string) {
    const desired = getCheckState(path, includedPaths, excludedPaths) !== "checked";
    const nextIncluded = includedPaths.filter((rule) => !isPathInside(rule, path));
    const nextExcluded = excludedPaths.filter((rule) => !isPathInside(rule, path));
    const inherited = selectedByRules(parentPath(path), nextIncluded, nextExcluded);
    if (desired !== inherited) {
      if (desired) nextIncluded.push(path);
      else nextExcluded.push(path);
    }
    setIncludedPaths(nextIncluded);
    setExcludedPaths(nextExcluded);
  }

  function selectAll() {
    setIncludedPaths(roots.map((root) => root.path));
    setExcludedPaths([]);
  }

  function deselectAll() {
    setIncludedPaths([]);
    setExcludedPaths([]);
  }

  function reset() {
    deselectAll();
    setSearch("");
    setSearchResults([]);
    setRoots((current) => current.map((root) => ({ ...root, children: undefined, expanded: false, loading: false })));
    setStats(null);
    setError("");
  }

  async function expandAll() {
    const topFolders = roots.filter((root) => !root.expanded);
    await Promise.all(topFolders.map((root) => toggleExpand(root)));
    setRoots((current) => current.map((root) => ({ ...root, expanded: true })));
  }

  function collapseAll() {
    setRoots((current) => current.map((root) => ({ ...root, expanded: false })));
  }

  async function handleScan(event: React.FormEvent) {
    event.preventDefault();
    if (includedPaths.length === 0) {
      setError("Select at least one folder to scan.");
      return;
    }
    try {
      setLoading(true);
      setError("");
      setStats(null);
      const response = await axios.post<ScanStats>(`${API_BASE_URL}/scanner/local`, {
        included_paths: includedPaths,
        excluded_paths: excludedPaths,
      });
      setStats(response.data);
      onSuccess();
    } catch (requestError) {
      console.error(requestError);
      if (axios.isAxiosError(requestError) && requestError.response?.data?.detail) {
        setError(String(requestError.response.data.detail));
      } else {
        setError("Local folder scan failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  function formatResultsFolders(): string[] {
    return searchResults.map((folder) => folder.path);
  }

  return (
    <div className="modal-backdrop" onClick={loading ? undefined : close}>
      <div className="cleanup-modal scanner-modal" onClick={(event) => event.stopPropagation()}>
        <div className="preview-header">
          <div>
            <h3>Select folders to scan</h3>
            <span>Choose included roots and exclude any subfolders before indexing.</span>
          </div>
          <button className="icon-button" onClick={close} disabled={loading} aria-label="Close scanner">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleScan} className="scanner-form folder-selector-form">
          <label className="scan-search-box">
            <Search size={17} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search folders..." disabled={loading} />
          </label>
          <div className="scan-tree-toolbar">
            <button type="button" className="secondary-button compact" onClick={selectAll} disabled={loading || roots.length === 0}>Select All</button>
            <button type="button" className="secondary-button compact" onClick={deselectAll} disabled={loading}>Deselect All</button>
            <button type="button" className="secondary-button compact" onClick={() => void expandAll()} disabled={loading || treeLoading}>Expand All</button>
            <button type="button" className="secondary-button compact" onClick={collapseAll} disabled={loading}>Collapse All</button>
            <button type="button" className="secondary-button compact" onClick={reset} disabled={loading}>Reset</button>
          </div>

          <div className="scan-folder-tree" aria-label="Local folders">
            {treeLoading ? (
              <div className="scan-tree-message"><Loader2 size={18} className="spin" /> Discovering available drives...</div>
            ) : roots.length === 0 ? (
              <div className="scan-tree-message">No local drives are available.</div>
            ) : (
              roots.map((root) => (
                <FolderRow key={root.path} node={root} depth={0} included={includedPaths} excluded={excludedPaths} onToggleSelection={toggleSelection} onToggleExpand={(node) => void toggleExpand(node)} />
              ))
            )}
          </div>

          {search.trim() && (
            <section className="scan-search-results">
              <strong>Search results ({searchResults.length})</strong>
              {searchResults.length === 0 ? <span>No matching folders found.</span> : formatResultsFolders().map((path) => (
                <div className="scan-search-result" key={path}>
                  <Folder size={15} />
                  <span title={path}>{path}</span>
                  <input
                    type="checkbox"
                    checked={getCheckState(path, includedPaths, excludedPaths) === "checked"}
                    ref={(element) => {
                      if (element) element.indeterminate = getCheckState(path, includedPaths, excludedPaths) === "mixed";
                    }}
                    onChange={() => toggleSelection(path)}
                    aria-label={`Select ${path}`}
                  />
                </div>
              ))}
              {searchTruncated && <small>Results are capped. Refine the search to see additional folders.</small>}
            </section>
          )}

          <div className="scan-selection-summary">
            <span>Included roots: <strong>{includedPaths.length}</strong></span>
            <span>Excluded folders: <strong>{excludedPaths.length}</strong></span>
            <span>Estimated indexed files: <strong>{estimateLoading ? "Calculating..." : estimate.estimated_files.toLocaleString()}</strong></span>
            <span>Estimated indexed storage: <strong>{estimateLoading ? "Calculating..." : formatBytes(estimate.estimated_bytes)}</strong></span>
            <small>Estimate uses existing indexed records; new, unindexed files are not included. Selected folders are traversed once during the scan.</small>
          </div>

          {error && (
            <div className="error-banner"><AlertTriangle size={18} /><span>{error}</span><button type="button" onClick={() => setError("")}><X size={16} /></button></div>
          )}

          {stats && (
            <div className="scan-results-card">
              <div className="scan-results-header">
                <CheckCircle size={20} className="success-icon" />
                <div><strong>Scan completed</strong><span>{stats.included_paths.join(", ")}</span></div>
              </div>
              <div className="scan-stats-grid">
                <div><strong>{stats.files_scanned.toLocaleString()}</strong><span>Scanned</span></div>
                <div><strong>{stats.files_added.toLocaleString()}</strong><span>Added</span></div>
                <div><strong>{stats.files_updated.toLocaleString()}</strong><span>Updated</span></div>
                <div><strong>{stats.files_skipped.toLocaleString()}</strong><span>Skipped</span></div>
                <div><strong>{stats.missing_files_marked.toLocaleString()}</strong><span>Marked Missing</span></div>
              </div>
              {stats.errors.length > 0 && <div className="scan-warning-text">{stats.errors.length} file or directory error(s) were recorded.</div>}
            </div>
          )}

          <div className="cleanup-modal-actions">
            <button type="button" className="secondary-button" onClick={close} disabled={loading}>{stats ? "Close" : "Cancel"}</button>
            <button type="submit" className="primary-button" disabled={loading || treeLoading || includedPaths.length === 0}>
              {loading ? <><Loader2 size={16} className="spin" /> Scanning selected folders...</> : <><HardDrive size={16} /> Start Scan</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
