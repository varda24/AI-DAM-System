import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "../api";
import { ExternalLink, Fingerprint, Folder, HardDrive, Loader2, RefreshCw } from "lucide-react";
import type { Asset } from "../types";
import "./GoogleDriveView.css";

const MAX_HASH_SIZE_BYTES = 50 * 1024 * 1024;

interface DriveAbout {
  user?: {
    displayName?: string;
    emailAddress?: string;
    permissionId?: string;
  };
}

interface DriveAsset extends Asset {
  source_account_id?: string;
  web_view_link?: string;
  sha256?: string | null;
}

interface DriveFolder {
  id: string;
  name: string;
  mimeType: string;
}

interface DriveMetadataFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  createdTime?: string;
  modifiedTime?: string;
  parents?: string[];
  webViewLink?: string;
}

interface GoogleDriveViewProps {
  onAssetsIndexed: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

export function GoogleDriveView({ onAssetsIndexed }: GoogleDriveViewProps) {
  const [connected, setConnected] = useState(false);
  const [account, setAccount] = useState<DriveAbout["user"]>();
  const [assets, setAssets] = useState<DriveAsset[]>([]);
  const [folders, setFolders] = useState<DriveFolder[]>([]);
  const [remoteFiles, setRemoteFiles] = useState<DriveMetadataFile[]>([]);
  const [folderStack, setFolderStack] = useState<DriveFolder[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [hashingId, setHashingId] = useState<number | null>(null);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void refresh();
  }, []);

  async function loadAssets(parentId = folderStack.at(-1)?.id || "root") {
    const response = await axios.get(`${API_BASE_URL}/google-drive/assets`, {
      params: { parent_id: parentId, page: 1, page_size: 100 },
    });
    setAssets(response.data.items);
  }

  async function loadFolders(parentId = folderStack.at(-1)?.id || "root") {
    const response = await axios.get(`${API_BASE_URL}/google-drive/folders`, {
      params: { parent_id: parentId },
    });
    setFolders(response.data.files || []);
  }

  async function loadRemoteFiles(parentId = folderStack.at(-1)?.id || "root") {
    const response = await axios.get(`${API_BASE_URL}/google-drive/files`, {
      params: { parent_id: parentId, page_size: 100 },
    });
    setRemoteFiles(response.data.files || []);
  }

  async function refresh() {
    try {
      setLoading(true);
      setError("");
      const status = await axios.get(`${API_BASE_URL}/google-drive/status`);
      setConnected(Boolean(status.data.connected));
      if (status.data.connected) {
        const [aboutResponse] = await Promise.all([
          axios.get<DriveAbout>(`${API_BASE_URL}/google-drive/about`),
        ]);
        setAccount(aboutResponse.data.user);
        await Promise.all([loadAssets(), loadFolders(), loadRemoteFiles()]);
      } else {
        setAccount(undefined);
        setAssets([]);
        setFolders([]);
        setRemoteFiles([]);
        setFolderStack([]);
      }
    } catch (requestError) {
      console.error(requestError);
      setError("Could not load Google Drive connection or indexed metadata.");
    } finally {
      setLoading(false);
    }
  }

  function connect() {
    window.open(`${API_BASE_URL}/google-drive/connect`, "_blank", "noopener,noreferrer");
  }

  async function sync() {
    try {
      setSyncing(true);
      setError("");
      setMessage("");
      const response = await axios.post(`${API_BASE_URL}/google-drive/sync`, null, {
        params: {
          max_files: 100,
          page_token: nextPageToken || undefined,
          parent_id: folderStack.at(-1)?.id || "root",
        },
      });
      const result = response.data;
      setNextPageToken(result.next_page_token || null);
      setMessage(
        `Metadata sync: ${result.files_added} added, ${result.files_updated} updated, ` +
          `${result.files_unchanged} unchanged. ${result.content_downloaded ? "Content fetched." : "No file content downloaded."}` +
          (result.next_page_token ? " More files are available; sync the next page manually." : " Reached the end of the Drive listing.")
      );
      await Promise.all([loadAssets(), loadFolders(), loadRemoteFiles()]);
      onAssetsIndexed();
    } catch (requestError) {
      console.error(requestError);
      setError("Google Drive metadata sync failed.");
    } finally {
      setSyncing(false);
    }
  }

  async function hashForDuplicates(asset: DriveAsset) {
    try {
      setHashingId(asset.id);
      setError("");
      setMessage("");
      const response = await axios.post(
        `${API_BASE_URL}/google-drive/assets/${asset.id}/hash`,
      );
      const groups = await axios.post(
        `${API_BASE_URL}/duplicates/detect`,
        null,
        { params: { hash_local_assets: false } },
      );
      setMessage(
        (response.data.cached
          ? "Using the existing Drive content hash; file metadata is unchanged. "
          : `Hashed ${formatBytes(response.data.bytes_hashed)} from Drive. `) +
          `${groups.data.duplicate_groups} exact-duplicate group(s) currently indexed.`
      );
      await loadAssets();
      onAssetsIndexed();
    } catch (requestError) {
      console.error(requestError);
      setError("Could not hash this Drive file. It may be over the size limit or a native Google Workspace file.");
    } finally {
      setHashingId(null);
    }
  }

  const currentAccountId = account?.permissionId || account?.emailAddress;
  const activeFolder = folderStack.at(-1);

  async function openFolder(folder: DriveFolder) {
    const nextStack = [...folderStack, folder];
    setFolderStack(nextStack);
    setNextPageToken(null);
    try {
      await Promise.all([loadAssets(folder.id), loadFolders(folder.id), loadRemoteFiles(folder.id)]);
    } catch (requestError) {
      console.error(requestError);
      setError("Could not load this Google Drive folder.");
    }
  }

  async function goToDriveRoot() {
    setFolderStack([]);
    setNextPageToken(null);
    try {
      await Promise.all([loadAssets("root"), loadFolders("root"), loadRemoteFiles("root")]);
    } catch (requestError) {
      console.error(requestError);
      setError("Could not load the Google Drive root.");
    }
  }

  return (
    <section className="drive-page">
      <header className="page-header">
        <div>
          <h2>Google Drive</h2>
          <p>Read-only connection · metadata indexed into the shared asset library</p>
        </div>
        <div className="header-actions">
          {connected && (
            <button className="primary-button" onClick={() => void sync()} disabled={syncing || loading}>
              {syncing ? <Loader2 size={16} className="spin" /> : <RefreshCw size={16} />}
              {syncing ? "Syncing metadata..." : nextPageToken ? "Sync next 100 files" : "Sync first 100 files"}
            </button>
          )}
          <button className="secondary-button" onClick={() => void refresh()} disabled={loading || syncing} title="Refresh status and indexed files" aria-label="Refresh Google Drive status">
            <RefreshCw size={16} className={loading ? "spin" : ""} />
          </button>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {message && <div className="success-banner">{message}</div>}

      <section className="drive-connection-row">
        <div className="drive-connection-icon"><HardDrive size={22} /></div>
        <div className="drive-connection-details">
          <strong>Google Drive</strong>
          <span>{loading ? "Checking connection..." : connected ? account?.emailAddress || "Connected account" : "Not connected"}</span>
        </div>
        <span className={`asset-status ${connected ? "available" : "missing"}`}>
          <span className="asset-status-dot" /> {connected ? "Connected" : "Disconnected"}
        </span>
        {!connected && !loading && (
          <button className="primary-button" onClick={connect}>Connect Google Drive</button>
        )}
      </section>

      {connected && (
        <section className="drive-index-section">
          <div className="duplicate-section-header">
            <div>
              <h3>{activeFolder?.name || "My Drive"}</h3>
              <p>{remoteFiles.filter((file) => file.mimeType !== "application/vnd.google-apps.folder").length} live Drive files · {assets.length} indexed · sync is capped at 100 per request</p>
            </div>
            <div className="drive-folder-actions">
              <button className="secondary-button compact" onClick={() => void goToDriveRoot()} disabled={!activeFolder}>My Drive</button>
              {activeFolder && <button className="secondary-button compact" onClick={() => {
                const nextStack = folderStack.slice(0, -1);
                setFolderStack(nextStack);
                const parentId = nextStack.at(-1)?.id || "root";
                setNextPageToken(null);
                void Promise.all([loadAssets(parentId), loadFolders(parentId), loadRemoteFiles(parentId)]);
              }}>Up</button>}
            </div>
          </div>
          {loading ? (
            <div className="empty-state">Loading indexed Drive files...</div>
          ) : (
            <>
              <div className="drive-folder-list">
                {folders.map((folder) => (
                  <button type="button" className="drive-folder-row" key={folder.id} onClick={() => void openFolder(folder)}>
                    <Folder size={18} />
                    <strong>{folder.name}</strong>
                    <small>Google Drive folder</small>
                  </button>
                ))}
              </div>
              {remoteFiles.length === 0 ? (
                <div className="empty-state">
                  <HardDrive size={34} />
                  <h3>No files in this Drive folder</h3>
                  <p>Google Drive returned no child files for this folder.</p>
                </div>
              ) : (
                <div className="drive-file-list">
                  {remoteFiles.filter((file) => file.mimeType !== "application/vnd.google-apps.folder").map((file) => {
                const asset = assets.find((candidate) => candidate.drive_file_id === file.id);
                const sameAccount = asset?.source_account_id === currentAccountId;
                const nativeGoogleFile = file.mimeType.startsWith("application/vnd.google-apps.");
                const fileSize = Number(file.size || 0);
                const canHash = Boolean(asset && sameAccount && !nativeGoogleFile && fileSize <= MAX_HASH_SIZE_BYTES);
                return (
                  <article className="drive-file-row" key={file.id}>
                    <div className="drive-file-info">
                      <strong title={file.name}>{file.name}</strong>
                      <span>{file.mimeType}</span>
                      <small>Google Drive · {formatBytes(fileSize)} · Modified {file.modifiedTime ? new Date(file.modifiedTime).toLocaleDateString() : "unknown"}</small>
                      {file.parents?.[0] && <small>Drive parent folder ID: {file.parents[0]}</small>}
                      <small>{asset ? "Indexed in shared library" : "Metadata only; sync this folder to index"}</small>
                    </div>
                    <div className="drive-file-actions">
                      {file.webViewLink && (
                        <a className="secondary-button compact" href={file.webViewLink} target="_blank" rel="noreferrer" title="Open in Google Drive">
                          <ExternalLink size={14} /> Open
                        </a>
                      )}
                      <button
                        className="secondary-button compact"
                        disabled={!canHash || hashingId === asset?.id}
                        onClick={() => asset && void hashForDuplicates(asset)}
                        title={!asset ? "Sync this folder to index before hashing" : nativeGoogleFile ? "Native Workspace content is not fetched" : fileSize > MAX_HASH_SIZE_BYTES ? "Maximum supported size is 50 MiB" : !sameAccount ? "Connect the account that owns this asset" : "Fetch temporarily and calculate SHA-256 and image pHash"}
                      >
                        {asset && hashingId === asset.id ? <Loader2 size={14} className="spin" /> : <Fingerprint size={14} />}
                        {!asset ? "Sync to index" : asset.sha256 ? "Hash cached" : "Hash for duplicates"}
                      </button>
                    </div>
                  </article>
                );
                  })}
                </div>
              )}
            </>
          )}
        </section>
      )}
    </section>
  );
}
