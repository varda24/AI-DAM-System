import { useEffect, useState } from "react";
import axios from "axios";
import { API_BASE_URL } from "./api";
import {
  AlertTriangle,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  ExternalLink,
  Eye,
  File,
  FileText,
  Folder,
  FolderPlus,
  Grid2X2,
  HardDrive,
  History,
  Image,
  Images,
  List,
  RefreshCw,
  Search,
  Sparkles,
  Users,
  Video,
  X,
} from "lucide-react";
import "./App.css";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  VideoAnalysis,
  VideoSimilarityResponse,
} from "./types";

import { ScannerModal } from "./components/ScannerModal";
import { GoogleDriveView } from "./components/GoogleDriveView";
import { PeopleView } from "./components/PeopleView";
import { CollectionsView } from "./components/CollectionsView";
import { NearDuplicatesView } from "./components/NearDuplicatesView";
import { CleanupHistoryView } from "./components/CleanupHistoryView";
import DocumentIntelligence from "./components/DocumentIntelligence";
import VideoIntelligence from "./components/VideoIntelligence";
import type {
  AIAnalysis,
  AnalysisProgress,
  Asset,
  CleanupPreview,
  DocumentAnalysis,
  OCRDiagnostics,
  DuplicateGroup,
  DuplicateSummary,
  FaceAnalysisResult,
  StorageSummary,
  StorageSnapshot,
  StorageHistoryResponse,
  StorageHistorySummary,
} from "./types";

export type ViewMode = "list" | "grid";
export type MainView =
  | "browser"
  | "google-drive"
  | "duplicates"
  | "storage"
  | "ai-images"
  | "documents"
  | "people"
  | "collections"
  | "near-duplicates"
  | "cleanup-history";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "-";
}

function getFileIcon(type: string, size = 20) {
  return type === "image" ? (
    <Image size={size} />
  ) : type === "video" ? (
    <Video size={size} />
  ) : type === "document" ? (
    <FileText size={size} />
  ) : (
    <File size={size} />
  );
}

function isPreviewable(asset: Asset) {
  return Boolean(
    asset.mime_type?.startsWith("image/") ||
      asset.mime_type?.startsWith("video/") ||
      asset.mime_type === "application/pdf"
  );
}

function App() {
  const [mainView, setMainView] = useState<MainView>("browser");
  const [showScannerModal, setShowScannerModal] = useState(false);

  const [aiAnalyses, setAiAnalyses] = useState<AIAnalysis[]>([]);
  const [aiSearch, setAiSearch] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiAnalyzingId, setAiAnalyzingId] = useState<number | null>(null);
  const [assetAiAnalyses, setAssetAiAnalyses] = useState<Record<number, AIAnalysis>>({});
  const [faceAnalyzingId, setFaceAnalyzingId] = useState<number | null>(null);
  const [faceResults, setFaceResults] = useState<Record<number, FaceAnalysisResult>>({});
  const [analysisProgress, setAnalysisProgress] = useState<AnalysisProgress | null>(null);

  const [assets, setAssets] = useState<Asset[]>([]);
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [folders, setFolders] = useState<
    { path: string; name: string; source: string }[]
  >([]);
  const [folderLoading, setFolderLoading] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [previewAsset, setPreviewAsset] = useState<Asset | null>(null);

  const [duplicateGroups, setDuplicateGroups] = useState<DuplicateGroup[]>([]);
  const [duplicateSummary, setDuplicateSummary] = useState<DuplicateSummary | null>(null);
  const [selectedCleanupIds, setSelectedCleanupIds] = useState<number[]>([]);
  const [cleanupPreview, setCleanupPreview] = useState<CleanupPreview | null>(null);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [cleanupMessage, setCleanupMessage] = useState("");

  const [storageSummary, setStorageSummary] = useState<StorageSummary | null>(null);
  const [storageLoading, setStorageLoading] = useState(false);

  const [storageHistory, setStorageHistory] = useState<StorageSnapshot[]>([]);
  const [storageHistorySummary, setStorageHistorySummary] =
    useState<StorageHistorySummary | null>(null);
  const [storageHistoryDays, setStorageHistoryDays] = useState<7 | 30 | 90 | 365>(30);
  const [storageHistoryLoading, setStorageHistoryLoading] = useState(false);
  const [videoAnalysis, setVideoAnalysis] =
  useState<VideoAnalysis | null>(null);

  const [videoAnalysisLoading, setVideoAnalysisLoading] =
    useState(false);

  const [videoSimilarity, setVideoSimilarity] =
    useState<VideoSimilarityResponse | null>(null);

  const [videoSimilarityLoading, setVideoSimilarityLoading] =
    useState(false);

  const [documentAnalyses, setDocumentAnalyses] =
    useState<DocumentAnalysis[]>([]);
  const [documentAnalysis, setDocumentAnalysis] =
    useState<DocumentAnalysis | null>(null);
  const [documentAnalysisLoading, setDocumentAnalysisLoading] =
    useState(false);
  const [documentListLoading, setDocumentListLoading] =
    useState(false);
  const [ocrDiagnostics, setOcrDiagnostics] =
    useState<OCRDiagnostics | null>(null);
  const [documentStatusFilter, setDocumentStatusFilter] =
    useState("ALL");
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [fileType, setFileType] = useState("");
  const [sortBy, setSortBy] = useState("modified_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [includeMissing, setIncludeMissing] = useState(false);
  const [sourceFilter, setSourceFilter] = useState("local_pc");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [loading, setLoading] = useState(false);
  const [duplicateLoading, setDuplicateLoading] = useState(false);
  const [error, setError] = useState("");

  function navigateTo(view: MainView) {
    setError("");
    setMainView(view);
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (mainView === "browser") void fetchAssets();
  }, [mainView, page, pageSize, search, fileType, sortBy, sortOrder, includeMissing, currentFolder, sourceFilter]);

  useEffect(() => {
    if (mainView !== "browser") return;
    if (sourceFilter !== "local_pc") {
      setFolders([]);
      setFolderLoading(false);
      return;
    }

    void fetchFolders(currentFolder);
  }, [mainView, currentFolder, includeMissing, sourceFilter]);

  useEffect(() => {
    if (mainView === "duplicates") void fetchDuplicateData();
  }, [mainView]);

  useEffect(() => {
    if (mainView === "storage") void fetchStorageSummary();
  }, [mainView]);

  useEffect(() => {
    if (mainView === "ai-images") void fetchAIImages(aiSearch);
  }, [mainView, aiSearch]);

  useEffect(() => {
    if (mainView === "storage") void fetchStorageHistory(storageHistoryDays);
  }, [mainView, storageHistoryDays]);

  useEffect(() => {
    if (mainView === "documents") {
      void fetchDocumentAnalyses();
      void fetchOCRDiagnostics();
    }
  }, [mainView]);

  useEffect(() => {
    void fetchAnalysisProgress();
    const timer = window.setInterval(() => void fetchAnalysisProgress(), 5000);
    return () => window.clearInterval(timer);
  }, []);

  async function fetchAssets() {
    try {
      setLoading(true);
      setError("");
      const response = await axios.get(`${API_BASE_URL}/assets`, {
        params: {
          page,
          page_size: pageSize,
          search: search || undefined,
          file_type: fileType || undefined,
          source: sourceFilter || undefined,
          sort_by: sortBy,
          sort_order: sortOrder,
          include_missing: includeMissing,
          folder: sourceFilter === "local_pc" ? currentFolder || undefined : undefined,
        },
      });
      setAssets(response.data.items);
      setTotal(response.data.total);
      setTotalPages(response.data.total_pages);
    } catch (err) {
      console.error(err);
      setError("Failed to load assets.");
    } finally {
      setLoading(false);
    }
  }
  async function analyzeVideo(assetId: number) {
  try {
    setVideoAnalysisLoading(true);
    setError("");

    const response = await axios.post<VideoAnalysis>(
      `${API_BASE_URL}/videos/${assetId}/analyze`,
    );

    setVideoAnalysis(response.data);
  } catch (err) {
    console.error(err);
    setError("Failed to analyze video.");
  } finally {
    setVideoAnalysisLoading(false);
  }
}


async function reanalyzeVideo(assetId: number) {
  try {
    setVideoAnalysisLoading(true);
    setError("");

    const response = await axios.post<VideoAnalysis>(
      `${API_BASE_URL}/videos/${assetId}/reanalyze`,
    );

    setVideoAnalysis(response.data);
  } catch (err) {
    console.error(err);
    setError("Failed to re-analyze video.");
  } finally {
    setVideoAnalysisLoading(false);
  }
}


async function loadVideoAnalysis(assetId: number) {
  try {
    setVideoAnalysisLoading(true);

    const response = await axios.get<VideoAnalysis>(
      `${API_BASE_URL}/videos/${assetId}`,
    );

    setVideoAnalysis(response.data);
  } catch {
    setVideoAnalysis(null);
  } finally {
    setVideoAnalysisLoading(false);
  }
}


async function detectSimilarVideos(
  assetIds: number[],
) {
  if (assetIds.length < 2) {
    setError(
      "Select at least two videos for similarity detection.",
    );
    return;
  }

  try {
    setVideoSimilarityLoading(true);
    setError("");

    const response =
      await axios.post<VideoSimilarityResponse>(
        `${API_BASE_URL}/videos/similarity/detect`,
        null,
        {
          params: {
            asset_ids: assetIds.join(","),
            threshold: 0.80,
            sample_count: 8,
          },
        },
      );

    setVideoSimilarity(response.data);
  } catch (err) {
    console.error(err);
    setError(
      "Failed to detect similar videos.",
    );
  } finally {
    setVideoSimilarityLoading(false);
  }
}
  async function fetchDocumentAnalyses() {
    try {
      setDocumentListLoading(true);
      const response = await axios.get<{
        total: number;
        limit: number;
        offset: number;
        documents: DocumentAnalysis[];
      }>(`${API_BASE_URL}/documents`);
      setDocumentAnalyses(response.data.documents);
    } catch (err) {
      console.error(err);
      setError("Failed to load document intelligence results.");
    } finally {
      setDocumentListLoading(false);
    }
  }

  async function fetchOCRDiagnostics() {
    try {
      const response = await axios.get<OCRDiagnostics>(`${API_BASE_URL}/documents/ocr-status`);
      setOcrDiagnostics(response.data);
    } catch (err) {
      console.error(err);
      setOcrDiagnostics(null);
    }
  }

  async function loadDocumentAnalysis(assetId: number) {
    try {
      setDocumentAnalysisLoading(true);
      const response = await axios.get<DocumentAnalysis>(
        `${API_BASE_URL}/documents/${assetId}`
      );
      setDocumentAnalysis(response.data);
    } catch (err) {
      setDocumentAnalysis(null);
      if (!(axios.isAxiosError(err) && err.response?.status === 404)) {
        setError("Failed to load document analysis.");
      }
    } finally {
      setDocumentAnalysisLoading(false);
    }
  }

  async function submitDocumentAnalysis(assetId: number, reanalyze = false) {
    try {
      setDocumentAnalysisLoading(true);
      setError("");
      const action = reanalyze ? "reanalyze" : "analyze";
      const response = await axios.post<DocumentAnalysis>(
        `${API_BASE_URL}/documents/${assetId}/${action}`
      );
      setDocumentAnalysis(response.data);
      await fetchDocumentAnalyses();
    } catch (err) {
      console.error(err);
      setError(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Document analysis failed."
      );
    } finally {
      setDocumentAnalysisLoading(false);
    }
  }

  async function fetchFolders(parent: string | null = null) {
    try {
      setFolderLoading(true);

      const response = await axios.get<{
        parent: string | null;
        folders: { path: string; name: string; source: string }[];
        total: number;
      }>(`${API_BASE_URL}/assets/folders`, {
        params: {
          parent: parent || undefined,
          source: "local_pc",
          include_missing: includeMissing,
        },
      });

      setFolders(response.data.folders);
    } catch (err) {
      console.error(err);
      setError("Failed to load folders.");
    } finally {
      setFolderLoading(false);
    }
  }

  function openFolder(folderPath: string) {
    setCurrentFolder(folderPath);
    setPage(1);
    handleSelectAsset(null);
  }

  function goToRoot() {
    setCurrentFolder(null);
    setPage(1);
    handleSelectAsset(null);
  }

  function goToParentFolder() {
    if (!currentFolder) return;

    const normalized = currentFolder.replace(/[\\/]+$/, "");
    const lastSeparator = Math.max(
      normalized.lastIndexOf("\\"),
      normalized.lastIndexOf("/")
    );

    if (lastSeparator <= 2) {
      goToRoot();
      return;
    }

    setCurrentFolder(normalized.slice(0, lastSeparator));
    setPage(1);
    handleSelectAsset(null);
  }

  function handleSelectAsset(asset: Asset | null) {
    setVideoAnalysis(null);
    setVideoSimilarity(null);
    setDocumentAnalysis(null);
    setSelectedAsset(asset);
    if (asset && asset.file_type === "video") {
      void loadVideoAnalysis(asset.id);
    }
    if (asset && (asset.file_type === "document" || asset.file_type === "image")) {
      void loadDocumentAnalysis(asset.id);
    }
  }

  async function openPreviewAsset(assetId: number) {
    const indexedAsset = assets.find((asset) => asset.id === assetId);

    if (indexedAsset) {
      setPreviewAsset(indexedAsset);
      return;
    }

    try {
      const response = await axios.get<Asset>(`${API_BASE_URL}/assets/${assetId}`);
      setPreviewAsset(response.data);
    } catch (err) {
      console.error(err);
      setError("Failed to load asset details for preview.");
    }
  }

  async function fetchDuplicateData() {
    try {
      setError("");
      const [summary, groups] = await Promise.all([
        axios.get<DuplicateSummary>(`${API_BASE_URL}/duplicates/summary`),
        axios.get<{ groups: DuplicateGroup[] }>(`${API_BASE_URL}/duplicates`),
      ]);
      setDuplicateSummary(summary.data);
      setDuplicateGroups(groups.data.groups);
    } catch (err) {
      console.error(err);
      setError("Failed to load duplicate information.");
    }
  }

  async function detectDuplicates() {
    try {
      setDuplicateLoading(true);
      setError("");
      await axios.post(`${API_BASE_URL}/duplicates/detect`);
      await fetchDuplicateData();
    } catch (err) {
      console.error(err);
      setError("Duplicate detection failed.");
    } finally {
      setDuplicateLoading(false);
    }
  }

  async function fetchStorageSummary() {
    try {
      setStorageLoading(true);
      setError("");
      const response = await axios.get<StorageSummary>(`${API_BASE_URL}/storage/summary`);
      setStorageSummary(response.data);
    } catch (err) {
      console.error(err);
      setError("Failed to load storage intelligence.");
    } finally {
      setStorageLoading(false);
    }
  }

  async function fetchStorageHistory(days: 7 | 30 | 90 | 365 = storageHistoryDays) {
    try {
      setStorageHistoryLoading(true);
      setError("");

      const [historyResponse, summaryResponse] = await Promise.all([
        axios.get<StorageHistoryResponse>(
          `${API_BASE_URL}/storage/history`,
          { params: { source: "local_pc", days } },
        ),
        axios.get<StorageHistorySummary>(
          `${API_BASE_URL}/storage/history/summary`,
          { params: { source: "local_pc", days } },
        ),
      ]);

      setStorageHistory(historyResponse.data.snapshots);
      setStorageHistorySummary(summaryResponse.data);
    } catch (err) {
      console.error(err);
      setError("Failed to load storage history.");
    } finally {
      setStorageHistoryLoading(false);
    }
  }

  async function fetchAIImages(query = "") {
    try {
      setAiLoading(true);
      setError("");
      const response = await axios.get(`${API_BASE_URL}/ai/images/search`, {
        params: { q: query.trim() },
      });
      setAiAnalyses(response.data.items);
    } catch (err) {
      console.error(err);
      setError("Failed to load AI image information.");
    } finally {
      setAiLoading(false);
    }
  }

  async function fetchAnalysisProgress() {
    try {
      const response = await axios.get<AnalysisProgress>(`${API_BASE_URL}/analysis-jobs/progress`);
      setAnalysisProgress(response.data);
    } catch (err) {
      console.error(err);
    }
  }

  async function analyzeImage(assetId: number) {
    try {
      setAiAnalyzingId(assetId);
      setError("");
      const response = await axios.post<AIAnalysis>(`${API_BASE_URL}/ai/images/analyze/${assetId}`);
      setAssetAiAnalyses((current) => ({ ...current, [assetId]: response.data }));
      await fetchAIImages(aiSearch);
    } catch (err) {
      console.error(err);
      setError(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Image analysis failed."
      );
    } finally {
      setAiAnalyzingId(null);
    }
  }

  async function analyzeAssetFaces(assetId: number) {
    try {
      setFaceAnalyzingId(assetId);
      setError("");
      const response = await axios.post<FaceAnalysisResult>(`${API_BASE_URL}/people/analyze/${assetId}`);
      setFaceResults((current) => ({ ...current, [assetId]: response.data }));
    } catch (err) {
      console.error(err);
      setError(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Face analysis failed."
      );
    } finally {
      setFaceAnalyzingId(null);
    }
  }

  function toggleCleanupAsset(id: number) {
    setSelectedCleanupIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  }

  async function previewCleanup() {
    if (!selectedCleanupIds.length) {
      setError("Select at least one file for cleanup.");
      return;
    }
    try {
      setCleanupLoading(true);
      setError("");
      setCleanupMessage("");
      const response = await axios.post(`${API_BASE_URL}/cleanup/preview`, {
        asset_ids: selectedCleanupIds,
      });
      setCleanupPreview(response.data);
    } catch (err) {
      console.error(err);
      setError("Failed to create cleanup preview.");
    } finally {
      setCleanupLoading(false);
    }
  }

  async function executeCleanup() {
    if (
      !selectedCleanupIds.length ||
      !window.confirm(
        `Move ${selectedCleanupIds.length} selected file(s) to the AI-DAM recovery area?`
      )
    )
      return;
    try {
      setCleanupLoading(true);
      setError("");
      const response = await axios.post(`${API_BASE_URL}/cleanup/execute`, {
        asset_ids: selectedCleanupIds,
      });
      setCleanupMessage(
        `Cleanup completed. ${response.data.moved_files} file(s) moved to recovery.`
      );
      setSelectedCleanupIds([]);
      setCleanupPreview(null);
      await fetchDuplicateData();
    } catch (err) {
      console.error(err);
      setError("Cleanup operation failed.");
    } finally {
      setCleanupLoading(false);
    }
  }

  const previewUrl = (id: number) => `${API_BASE_URL}/assets/${id}/preview`;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <HardDrive size={24} />
          <div>
            <h1>AI-DAM System</h1>
            <span>Digital Asset Management</span>
          </div>
        </div>

        <div className="topbar-right">
          <button
            className="primary-button scanner-trigger-btn"
            onClick={() => setShowScannerModal(true)}
          >
            <FolderPlus size={18} /> Scan Folder
          </button>

          <nav className="main-nav">
            <button
              className={`nav-button ${mainView === "browser" ? "active" : ""}`}
              onClick={() => navigateTo("browser")}
            >
              <Folder size={18} /> Browser
            </button>
            <button
              className={`nav-button ${mainView === "google-drive" ? "active" : ""}`}
              onClick={() => navigateTo("google-drive")}
            >
              <HardDrive size={18} /> Google Drive
            </button>
            <button
              className={`nav-button ${mainView === "duplicates" ? "active" : ""}`}
              onClick={() => navigateTo("duplicates")}
            >
              <Copy size={18} /> Duplicates
            </button>
            <button
              className={`nav-button ${mainView === "storage" ? "active" : ""}`}
              onClick={() => navigateTo("storage")}
            >
              <HardDrive size={18} /> Storage
            </button>
            <button
              className={`nav-button ${mainView === "ai-images" ? "active" : ""}`}
              onClick={() => navigateTo("ai-images")}
            >
              <Image size={18} /> AI Images
            </button>
            <button
              className={`nav-button ${mainView === "documents" ? "active" : ""}`}
              onClick={() => navigateTo("documents")}
            >
              <FileText size={18} /> Documents
            </button>
            <button
              className={`nav-button ${mainView === "people" ? "active" : ""}`}
              onClick={() => navigateTo("people")}
            >
              <Users size={18} /> People
            </button>
            <button
              className={`nav-button ${mainView === "collections" ? "active" : ""}`}
              onClick={() => navigateTo("collections")}
            >
              <Sparkles size={18} /> Collections
            </button>
            <button
              className={`nav-button ${mainView === "near-duplicates" ? "active" : ""}`}
              onClick={() => navigateTo("near-duplicates")}
            >
              <Images size={18} /> Near-Duplicates
            </button>
            <button
              className={`nav-button ${mainView === "cleanup-history" ? "active" : ""}`}
              onClick={() => navigateTo("cleanup-history")}
            >
              <History size={18} /> Cleanup History
            </button>
          </nav>
        </div>
      </header>

      <main className="content">
        {error && (
          <div className="error-banner">
            <AlertTriangle size={18} />
            <span>{error}</span>
            <button onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}

        {mainView === "browser" ? (
          <Browser
            assets={assets}
            loading={loading}
            total={total}
            totalPages={totalPages}
            page={page}
            pageSize={pageSize}
            searchInput={searchInput}
            fileType={fileType}
            sourceFilter={sourceFilter}
            sortBy={sortBy}
            includeMissing={includeMissing}
            viewMode={viewMode}
            selectedAsset={selectedAsset}
            setSearchInput={setSearchInput}
            setFileType={setFileType}
            setSourceFilter={(source: string) => {
              setSourceFilter(source);
              setCurrentFolder(null);
              setPage(1);
              setSelectedAsset(null);
            }}
            setSortBy={setSortBy}
            setSortOrder={setSortOrder}
            setPageSize={setPageSize}
            setIncludeMissing={setIncludeMissing}
            setViewMode={setViewMode}
            setPage={setPage}
            onSelectAsset={handleSelectAsset}
            fetchAssets={fetchAssets}
            setPreviewAsset={setPreviewAsset}
            currentFolder={currentFolder}
            folders={folders}
            folderLoading={folderLoading}
            openFolder={openFolder}
            goToRoot={goToRoot}
            goToParentFolder={goToParentFolder}
            analyzeImage={analyzeImage}
            aiAnalyzingId={aiAnalyzingId}
            assetAiAnalyses={assetAiAnalyses}
            analyzeFaces={analyzeAssetFaces}
            faceAnalyzingId={faceAnalyzingId}
            faceResults={faceResults}
            videoAnalysis={videoAnalysis}
            videoAnalysisLoading={videoAnalysisLoading}
            videoSimilarity={videoSimilarity}
            videoSimilarityLoading={videoSimilarityLoading}
            analyzeVideo={analyzeVideo}
            reanalyzeVideo={reanalyzeVideo}
            detectSimilarVideos={detectSimilarVideos}
            documentAnalysis={documentAnalysis}
            documentAnalysisLoading={documentAnalysisLoading}
            analysisProgress={analysisProgress}
            analyzeDocument={(assetId: number) => void submitDocumentAnalysis(assetId)}
            reanalyzeDocument={(assetId: number) => void submitDocumentAnalysis(assetId, true)}
          />
        ) : mainView === "google-drive" ? (
          <GoogleDriveView
            onAssetsIndexed={() => {
              void fetchAssets();
              void fetchDuplicateData();
            }}
          />
        ) : mainView === "duplicates" ? (
          <Duplicates
            groups={duplicateGroups}
            summary={duplicateSummary}
            loading={duplicateLoading}
            selectedIds={selectedCleanupIds}
            cleanupMessage={cleanupMessage}
            cleanupLoading={cleanupLoading}
            setCleanupMessage={setCleanupMessage}
            toggleAsset={toggleCleanupAsset}
            previewCleanup={previewCleanup}
            detectDuplicates={detectDuplicates}
            fetchDuplicateData={fetchDuplicateData}
            previewAsset={openPreviewAsset}
          />
        ) : mainView === "storage" ? (
          <StoragePage
            summary={storageSummary}
            loading={storageLoading}
            refresh={fetchStorageSummary}
            history={storageHistory}
            historySummary={storageHistorySummary}
            historyDays={storageHistoryDays}
            setHistoryDays={setStorageHistoryDays}
            historyLoading={storageHistoryLoading}
            refreshHistory={() => fetchStorageHistory(storageHistoryDays)}
          />
        ) : mainView === "ai-images" ? (
          <AIImages
            analyses={aiAnalyses}
            query={aiSearch}
            loading={aiLoading}
            analyzingId={aiAnalyzingId}
            setQuery={setAiSearch}
            analyze={analyzeImage}
            preview={openPreviewAsset}
          />
        ) : mainView === "documents" ? (
          <DocumentsPage
            analyses={documentAnalyses}
            loading={documentListLoading}
            statusFilter={documentStatusFilter}
            setStatusFilter={setDocumentStatusFilter}
            refresh={fetchDocumentAnalyses}
            ocrDiagnostics={ocrDiagnostics}
          />
        ) : mainView === "people" ? (
          <PeopleView onPreviewAsset={openPreviewAsset} />
        ) : mainView === "collections" ? (
          <CollectionsView onPreviewAsset={openPreviewAsset} />
        ) : mainView === "near-duplicates" ? (
          <NearDuplicatesView onPreviewAsset={openPreviewAsset} />
        ) : (
          <CleanupHistoryView />
        )}
      </main>

      {showScannerModal && (
        <ScannerModal
          close={() => setShowScannerModal(false)}
          onSuccess={() => {
            void fetchAssets();
            void fetchAIImages();
            void fetchDocumentAnalyses();
            void fetchStorageSummary();
            void fetchDuplicateData();
            void fetchAnalysisProgress();
          }}
        />
      )}

      {previewAsset && (
        <Preview
          asset={previewAsset}
          url={previewUrl(previewAsset.id)}
          close={() => setPreviewAsset(null)}
        />
      )}

      {cleanupPreview && (
        <CleanupModal
          preview={cleanupPreview}
          loading={cleanupLoading}
          close={() => setCleanupPreview(null)}
          execute={executeCleanup}
        />
      )}
    </div>
  );
}

function Browser({
  assets,
  loading,
  total,
  totalPages,
  page,
  pageSize,
  searchInput,
  fileType,
  sourceFilter,
  sortBy,
  includeMissing,
  viewMode,
  selectedAsset,
  setSearchInput,
  setFileType,
  setSourceFilter,
  setSortBy,
  setSortOrder,
  setPageSize,
  setIncludeMissing,
  setViewMode,
  setPage,
  onSelectAsset,
  fetchAssets,
  setPreviewAsset,
  currentFolder,
  folders,
  folderLoading,
  openFolder,
  goToRoot,
  goToParentFolder,
  analyzeImage,
  aiAnalyzingId,
  assetAiAnalyses,
  analyzeFaces,
  faceAnalyzingId,
  faceResults,
  videoAnalysis,
  videoAnalysisLoading,
  videoSimilarity,
  videoSimilarityLoading,
  analyzeVideo,
  reanalyzeVideo,
  detectSimilarVideos,
  documentAnalysis,
  documentAnalysisLoading,
  analyzeDocument,
  reanalyzeDocument,
  analysisProgress,
}: any) {
  return (
    <>
      <section className="page-header">
        <div>
          <h2>Asset Browser</h2>
          <p>Browse indexed assets by source. Drive content is fetched only when requested.</p>
        </div>
        <button className="secondary-button" onClick={fetchAssets}>
          <RefreshCw size={17} /> Refresh
        </button>
      </section>

      {analysisProgress && (
        <section className="folder-navigator" aria-label="Analysis processing progress">
          <strong>AI processing</strong>
          <span>{analysisProgress.totals.PENDING} pending</span>
          <span>{analysisProgress.totals.PROCESSING} processing</span>
          <span>{analysisProgress.totals.ANALYZED} analyzed</span>
          {analysisProgress.totals.FAILED > 0 && <span>{analysisProgress.totals.FAILED} failed</span>}
        </section>
      )}

      <section className="folder-navigator" style={{ display: sourceFilter === "local_pc" ? undefined : "none" }}>
        <div className="folder-toolbar">
          <div className="folder-navigation-actions">
            <button
              className="secondary-button compact"
              onClick={goToParentFolder}
              disabled={!currentFolder}
              title={currentFolder ? "Go to parent folder" : "Already at Local PC root"}
            >
              <ChevronLeft size={15} />
              Up
            </button>

            <button
              className="secondary-button compact"
              onClick={goToRoot}
              title="Show all indexed folders"
            >
              <HardDrive size={15} />
              Home
            </button>
          </div>

          <div className="folder-location">
            <div className="folder-location-title">
              <Folder size={16} />
              <strong>{currentFolder ? "Current Folder" : "Local PC"}</strong>
            </div>
            <div className="folder-location-path" title={currentFolder || "Local PC"}>
              {currentFolder || "All indexed local folders"}
            </div>
          </div>

          <div className="folder-breadcrumbs" aria-label="Folder breadcrumbs">
            <button
              className="breadcrumb-button"
              onClick={goToRoot}
            >
              Local PC
            </button>

            {currentFolder &&
              (() => {
                const normalized = currentFolder.replace(/[\\/]+$/, "");
                const separator = normalized.includes("\\") ? "\\" : "/";
                const driveMatch = normalized.match(/^([A-Za-z]:)(?:[\\/]|$)/);
                const drive = driveMatch?.[1];
                const remainder = drive
                  ? normalized.slice(2).replace(/^[\\/]+/, "")
                  : normalized;
                const parts = remainder.split(/[\\/]+/).filter(Boolean);
                const breadcrumbs: { label: string; path: string }[] = [];

                if (drive) {
                  breadcrumbs.push({ label: drive, path: `${drive}\\` });
                }

                parts.forEach((part: string) => {
                  const previous = breadcrumbs[breadcrumbs.length - 1]?.path || "";
                  const base = previous.endsWith("\\") || previous.endsWith("/")
                    ? previous
                    : previous
                      ? `${previous}${separator}`
                      : "";
                  breadcrumbs.push({
                    label: part,
                    path: `${base}${part}`,
                  });
                });

                return breadcrumbs.map((crumb, index) => (
                  <span className="breadcrumb-item" key={`${crumb.path}-${index}`}>
                    <span className="breadcrumb-separator">›</span>
                    <button
                      className={`breadcrumb-button ${
                        index === breadcrumbs.length - 1 ? "current" : ""
                      }`}
                      onClick={() => openFolder(crumb.path)}
                      title={crumb.path}
                    >
                      {crumb.label}
                    </button>
                  </span>
                ));
              })()}
          </div>
        </div>

        <div className="folder-section-heading">
          <div>
            <h3>Folders</h3>
            <p>
              {folders.length
                ? `${folders.length} indexed subfolder${folders.length === 1 ? "" : "s"}`
                : "Folders available from the current location"}
            </p>
          </div>
          {currentFolder && (
            <span className="folder-scope-badge" title={currentFolder}>
              Scoped to current folder
            </span>
          )}
        </div>

        <div className="folder-list">
          {folderLoading ? (
            <div className="folder-empty">
              <RefreshCw size={17} className="spin" />
              <span>Loading folders...</span>
            </div>
          ) : folders.length === 0 ? (
            <div className="folder-empty">
              <Folder size={22} />
              <span>No indexed subfolders</span>
              <small>
                {currentFolder
                  ? "This folder has no indexed child folders."
                  : "Scan a local folder to discover folders here."}
              </small>
            </div>
          ) : (
            folders.map((folder: { path: string; name: string; source: string }) => (
              <button
                key={folder.path}
                type="button"
                className="folder-card"
                onClick={() => openFolder(folder.path)}
                title={`Open ${folder.path}`}
              >
                <span className="folder-card-icon">
                  <Folder size={25} />
                </span>
                <span className="folder-card-content">
                  <strong>{folder.name}</strong>
                  <small>{folder.path}</small>
                </span>
                <ChevronRight size={17} className="folder-card-arrow" />
              </button>
            ))
          )}
        </div>
      </section>

      <section className="toolbar">
        <div className="search-box">
          <Search size={18} />
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search files or paths..."
          />
        </div>
        <select
          value={sourceFilter}
          onChange={(event) => setSourceFilter(event.target.value)}
          aria-label="Filter by source"
        >
          <option value="local_pc">Local PC</option>
          <option value="google_drive">Google Drive</option>
          <option value="">All sources</option>
        </select>
        <select
          value={fileType}
          onChange={(event) => {
            setFileType(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All types</option>
          <option value="image">Images</option>
          <option value="video">Videos</option>
          <option value="document">Documents</option>
          <option value="other">Other</option>
        </select>
        <select
          value={sortBy}
          onChange={(event) => {
            setSortBy(event.target.value);
            setPage(1);
          }}
        >
          <option value="modified_at">Modified</option>
          <option value="name">Name</option>
          <option value="size_bytes">Size</option>
          <option value="created_at">Created</option>
          <option value="accessed_at">Accessed</option>
          <option value="file_type">File Type</option>
        </select>
        <button
          className="icon-button"
          onClick={() => setSortOrder((current: string) => (current === "asc" ? "desc" : "asc"))}
        >
          <ArrowDown size={18} />
        </button>
        <select
          value={pageSize}
          onChange={(event) => {
            setPageSize(Number(event.target.value));
            setPage(1);
          }}
        >
          <option value={25}>25 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
          <option value={200}>200 / page</option>
        </select>
        <label className="checkbox-control">
          <input
            type="checkbox"
            checked={includeMissing}
            onChange={(event) => {
              setIncludeMissing(event.target.checked);
              setPage(1);
            }}
          />{" "}
          Include missing
        </label>
        <div className="view-switch">
          <button className={viewMode === "list" ? "active" : ""} onClick={() => setViewMode("list")}>
            <List size={18} />
          </button>
          <button className={viewMode === "grid" ? "active" : ""} onClick={() => setViewMode("grid")}>
            <Grid2X2 size={18} />
          </button>
        </div>
      </section>

      <div className="results-info">
        <span>
          {total.toLocaleString()} assets
          {currentFolder && sourceFilter === "local_pc"
            ? ` in ${currentFolder}`
            : sourceFilter === "local_pc"
              ? " across Local PC"
              : sourceFilter === "google_drive"
                ? " in Google Drive"
                : " across connected sources"}
        </span>
        {loading && <span>Loading...</span>}
      </div>

      {viewMode === "list" ? (
        <section className="asset-table-wrapper">
          <table className="asset-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Size</th>
                <th>Modified</th>
                <th>Actions</th>
                <th>Path</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset: Asset) => (
                <tr
                  key={asset.id}
                  className={selectedAsset?.id === asset.id ? "selected" : ""}
                  onClick={() => onSelectAsset(asset)}
                  onDoubleClick={() => asset.source === "local_pc" && isPreviewable(asset) && setPreviewAsset(asset)}
                >
                  <td>
                    <div className="file-name-cell">
                      {getFileIcon(asset.file_type)}
                      <span>{asset.name}</span>
                    </div>
                  </td>
                  <td>{asset.file_type}</td>
                  <td>{formatBytes(asset.size_bytes)}</td>
                  <td>{formatDate(asset.modified_at)}</td>
                  <td>
                    <div className="asset-action-buttons">
                    {asset.source === "local_pc" && isPreviewable(asset) && (
                      <button
                        className="secondary-button compact table-preview-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPreviewAsset(asset);
                        }}
                      >
                        <Eye size={13} /> Preview
                      </button>
                    )}
                    {asset.source === "local_pc" && asset.file_type === "image" && (
                      <button
                        className="primary-button compact"
                        disabled={aiAnalyzingId === asset.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void analyzeImage(asset.id);
                        }}
                      >
                        <Sparkles size={13} />
                        {aiAnalyzingId === asset.id ? "Analyzing..." : "Analyze with AI"}
                      </button>
                    )}
                    {asset.source === "local_pc" && asset.file_type === "image" && (
                      <button
                        className="secondary-button compact"
                        disabled={faceAnalyzingId === asset.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void analyzeFaces(asset.id);
                        }}
                      >
                        <Users size={13} />
                        {faceAnalyzingId === asset.id ? "Analyzing..." : "Analyze Faces"}
                      </button>
                    )}
                    </div>
                  </td>
                  <td className="path-cell" title={asset.path}>
                    {asset.path}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : (
        <section className="asset-grid">
          {assets.map((asset: Asset) => (
            <article
              key={asset.id}
              className={`asset-card ${selectedAsset?.id === asset.id ? "selected" : ""}`}
              onClick={() => onSelectAsset(asset)}
              onDoubleClick={() => asset.source === "local_pc" && isPreviewable(asset) && setPreviewAsset(asset)}
            >
              <div className="asset-card-icon">{getFileIcon(asset.file_type)}</div>
              <div className="asset-card-name">{asset.name}</div>
              <div className="asset-card-meta">
                <span>{asset.file_type}</span>
                <span>{formatBytes(asset.size_bytes)}</span>
              </div>
              {asset.source === "local_pc" && isPreviewable(asset) && (
                <button
                  className="secondary-button compact card-preview-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPreviewAsset(asset);
                  }}
                >
                  <Eye size={13} /> Preview
                </button>
              )}
              {asset.source === "local_pc" && asset.file_type === "image" && (
                <div className="asset-action-buttons">
                  <button
                    className="primary-button compact"
                    disabled={aiAnalyzingId === asset.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      void analyzeImage(asset.id);
                    }}
                  >
                    <Sparkles size={13} /> {aiAnalyzingId === asset.id ? "Analyzing..." : "Analyze with AI"}
                  </button>
                  <button
                    className="secondary-button compact"
                    disabled={faceAnalyzingId === asset.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      void analyzeFaces(asset.id);
                    }}
                  >
                    <Users size={13} /> {faceAnalyzingId === asset.id ? "Analyzing..." : "Analyze Faces"}
                  </button>
                </div>
              )}
            </article>
          ))}
        </section>
      )}

      {assets.length === 0 && !loading && (
        <State text="No assets found" subtext="Try changing your search or filters." />
      )}

      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage((current: number) => current - 1)}>
          <ChevronLeft size={18} /> Previous
        </button>
        <span>
          Page {page} of {totalPages || 1}
        </span>
        <button
          disabled={page >= totalPages || totalPages === 0}
          onClick={() => setPage((current: number) => current + 1)}
        >
          Next <ChevronRight size={18} />
        </button>
      </div>

      {selectedAsset && (
        <aside className="details-panel">
          <div className="details-header">
            <div className="details-header-title">
              <span>Selected Asset</span>
              <h3>Asset Details</h3>
            </div>
            <button
              className="icon-button"
              onClick={() => onSelectAsset(null)}
              title="Close details"
              aria-label="Close asset details"
            >
              <X size={18} />
            </button>
          </div>

          <div className="details-identity">
            <div className="details-icon">{getFileIcon(selectedAsset.file_type, 30)}</div>
            <div className="details-identity-text">
              <h4 title={selectedAsset.name}>{selectedAsset.name}</h4>
              <span>
                {selectedAsset.extension
                  ? selectedAsset.extension.toUpperCase().replace(/^\./, "")
                  : selectedAsset.file_type}
                {" · "}
                {formatBytes(selectedAsset.size_bytes)}
              </span>
            </div>
          </div>

          <div className="details-status-row">
            <span className={selectedAsset.is_missing ? "asset-status missing" : "asset-status available"}>
              <span className="asset-status-dot" />
              {selectedAsset.is_missing ? "Missing from disk" : "Available"}
            </span>
            <span className="asset-source-badge">{selectedAsset.source}</span>
          </div>

          <section className="details-section">
            <div className="details-section-heading">
              <strong>File Information</strong>
            </div>
            <dl className="details-list">
              <div className="detail-row">
                <dt>ID</dt>
                <dd>{selectedAsset.id}</dd>
              </div>
              <div className="detail-row">
                <dt>File Type</dt>
                <dd className="capitalize-value">{selectedAsset.file_type}</dd>
              </div>
              <div className="detail-row">
                <dt>Extension</dt>
                <dd>{selectedAsset.extension || "-"}</dd>
              </div>
              <div className="detail-row">
                <dt>MIME Type</dt>
                <dd>{selectedAsset.mime_type || "-"}</dd>
              </div>
              <div className="detail-row">
                <dt>Size</dt>
                <dd>{formatBytes(selectedAsset.size_bytes)}</dd>
              </div>
            </dl>
          </section>

          <section className="details-section">
            <div className="details-section-heading">
              <strong>Dates</strong>
            </div>
            <dl className="details-list">
              <div className="detail-row">
                <dt>Created</dt>
                <dd>{formatDate(selectedAsset.created_at)}</dd>
              </div>
              <div className="detail-row">
                <dt>Modified</dt>
                <dd>{formatDate(selectedAsset.modified_at)}</dd>
              </div>
              <div className="detail-row">
                <dt>Accessed</dt>
                <dd>{formatDate(selectedAsset.accessed_at)}</dd>
              </div>
              <div className="detail-row">
                <dt>Last Scanned</dt>
                <dd>{formatDate(selectedAsset.last_scanned_at)}</dd>
              </div>
            </dl>
          </section>

          <section className="details-section">
            <div className="details-section-heading">
              <strong>Location</strong>
            </div>
            <div className="details-path-card">
              <code title={selectedAsset.path}>{selectedAsset.path}</code>
              <button
                className="secondary-button compact"
                type="button"
                onClick={() => {
                  void navigator.clipboard?.writeText(selectedAsset.path);
                }}
                title="Copy full path"
              >
                <Copy size={14} /> Copy Path
              </button>
            </div>
          </section>

          <div className="details-actions">
            {selectedAsset.source === "local_pc" && isPreviewable(selectedAsset) && (
              <button
                className="primary-button details-action-button"
                onClick={() => setPreviewAsset(selectedAsset)}
                disabled={selectedAsset.is_missing}
              >
                <Eye size={16} /> Open Preview
              </button>
            )}

            {selectedAsset.source === "google_drive" && selectedAsset.web_view_link && (
              <a
                className="primary-button details-action-button"
                href={selectedAsset.web_view_link}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={16} /> Open in Google Drive
              </a>
            )}

            {selectedAsset.source === "local_pc" && selectedAsset.file_type === "image" && !selectedAsset.is_missing && (
              <div className="details-analysis-actions">
                <button
                  className="primary-button"
                  disabled={aiAnalyzingId === selectedAsset.id}
                  onClick={() => void analyzeImage(selectedAsset.id)}
                >
                  <Sparkles size={16} />
                  {aiAnalyzingId === selectedAsset.id ? "Analyzing image..." : "Analyze with AI"}
                </button>
                <button
                  className="secondary-button"
                  disabled={faceAnalyzingId === selectedAsset.id}
                  onClick={() => void analyzeFaces(selectedAsset.id)}
                >
                  <Users size={16} />
                  {faceAnalyzingId === selectedAsset.id ? "Analyzing faces..." : "Analyze Faces"}
                </button>
              </div>
            )}
          </div>

          {assetAiAnalyses[selectedAsset.id] && (
            <section className="asset-analysis-result">
              <div className="analysis-result-heading">
                <Sparkles size={16} />
                <h4>AI Analysis</h4>
              </div>
              <p>{assetAiAnalyses[selectedAsset.id].caption || "No caption returned."}</p>
              <span>Category: {assetAiAnalyses[selectedAsset.id].category || "other"}</span>
              <div className="ai-tags">
                {assetAiAnalyses[selectedAsset.id].tags.map((tag: string) => (
                  <small key={tag}>{tag}</small>
                ))}
              </div>
            </section>
          )}

          {faceResults[selectedAsset.id] && (
            <section className="asset-analysis-result">
              <div className="analysis-result-heading">
                <Users size={16} />
                <h4>Face Analysis</h4>
              </div>
              <p>
                {faceResults[selectedAsset.id].faces_detected
                  ? `${faceResults[selectedAsset.id].faces_detected} face(s) detected.`
                  : "No faces detected."}
              </p>
              {faceResults[selectedAsset.id].faces.map(
                (face: { face_index: number; confidence: number }) => (
                  <span key={face.face_index}>
                    Face {face.face_index + 1}: {Math.round(face.confidence * 100)}% confidence
                  </span>
                )
              )}
            </section>
          )}

          {selectedAsset.file_type === "video" && (
            <VideoIntelligence
              asset={selectedAsset}
              analysis={videoAnalysis}
              analysisLoading={videoAnalysisLoading}
              similarity={videoSimilarity}
              similarityLoading={videoSimilarityLoading}
              onAnalyze={analyzeVideo}
              onReanalyze={reanalyzeVideo}
              onDetectSimilarity={detectSimilarVideos}
            />
          )}
          {(selectedAsset.file_type === "document" || selectedAsset.file_type === "image") && (
            <DocumentIntelligence
              asset={selectedAsset}
              analysis={documentAnalysis}
              loading={documentAnalysisLoading}
              onAnalyze={analyzeDocument}
              onReanalyze={reanalyzeDocument}
            />
          )}
        </aside>
      )}
    </>
  );
}

function Duplicates({
  groups,
  summary,
  loading,
  selectedIds,
  cleanupMessage,
  cleanupLoading,
  setCleanupMessage,
  toggleAsset,
  previewCleanup,
  detectDuplicates,
  fetchDuplicateData,
  previewAsset,
}: any) {
  return (
    <section className="duplicates-page">
      <section className="page-header">
        <div>
          <h2>Exact Duplicates</h2>
          <p>Files with identical SHA-256 content hashes.</p>
        </div>
        <button className="primary-button" onClick={detectDuplicates} disabled={loading}>
          <RefreshCw size={17} className={loading ? "spin" : ""} />
          {loading ? "Detecting..." : "Detect Duplicates"}
        </button>
      </section>

      <div className="summary-grid">
        <Summary
          label="Duplicate Groups"
          value={summary ? summary.duplicate_groups.toLocaleString() : "-"}
          icon={<Copy size={22} />}
        />
        <Summary
          label="Duplicate Files"
          value={summary ? summary.duplicate_files.toLocaleString() : "-"}
          icon={<File size={22} />}
        />
        <Summary
          label="Potential Savings"
          value={summary ? formatBytes(summary.potential_savings_bytes) : "-"}
          icon={<HardDrive size={22} />}
        />
      </div>

      {cleanupMessage && (
        <div className="success-banner">
          <span>{cleanupMessage}</span>
          <button onClick={() => setCleanupMessage("")}>
            <X size={16} />
          </button>
        </div>
      )}

      {selectedIds.length > 0 && (
        <div className="cleanup-toolbar">
          <div>
            <strong>{selectedIds.length} file(s) selected</strong>
            <span>These files will be moved to recovery, not permanently deleted.</span>
          </div>
          <button className="secondary-button" onClick={previewCleanup} disabled={cleanupLoading}>
            {cleanupLoading ? "Preparing..." : "Preview Cleanup"}
          </button>
        </div>
      )}

      <div className="duplicate-section-header">
        <div>
          <h3>Duplicate Groups</h3>
          <p>Each group contains files with exactly the same content.</p>
        </div>
        <button className="secondary-button" onClick={fetchDuplicateData}>
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {groups.length === 0 ? (
        <State text="No duplicate groups" subtext="Run duplicate detection to analyze indexed files." />
      ) : (
        <div className="duplicate-groups">
          {groups.map((group: DuplicateGroup) => (
            <article className="duplicate-group" key={group.id}>
              <div className="duplicate-group-header">
                <div>
                  <h3>Duplicate Group #{group.id}</h3>
                  <div className="duplicate-stats">
                    <span>{group.file_count} files</span>
                    <span>Each file: {formatBytes(group.file_size_bytes)}</span>
                    <span>Savings: {formatBytes(group.potential_savings_bytes)}</span>
                  </div>
                </div>
                <code title={group.sha256}>SHA-256: {group.sha256.slice(0, 16)}...</code>
              </div>
              <div className="duplicate-files">
                {group.assets.map((asset) => (
                  <div
                    className={
                      selectedIds.includes(asset.id)
                        ? "duplicate-file selected-for-cleanup"
                        : "duplicate-file"
                    }
                    key={asset.id}
                  >
                    <label className="cleanup-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(asset.id)}
                        disabled={asset.source !== "local_pc"}
                        title={asset.source !== "local_pc" ? "Cloud assets cannot be moved by local cleanup" : "Select local asset for cleanup"}
                        onChange={() => toggleAsset(asset.id)}
                      />
                    </label>
                    <div className="duplicate-file-icon">{getFileIcon(asset.file_type)}</div>
                    <div className="duplicate-file-info">
                      <strong>{asset.name}</strong>
                      <span title={asset.path}>{asset.path}</span>
                      <small>Source: {asset.source || "local_pc"}</small>
                      <small>Modified: {formatDate(asset.modified_at)}</small>
                    </div>
                    <div className="duplicate-file-actions">
                      {asset.source === "local_pc" ? <button
                        className="secondary-button compact"
                        onClick={() => void previewAsset(asset.id)}
                      >
                        <Eye size={13} /> Preview
                      </button> : asset.web_view_link ? (
                        <a className="secondary-button compact" href={asset.web_view_link} target="_blank" rel="noreferrer">
                          <ExternalLink size={13} /> Open in Drive
                        </a>
                      ) : null}
                      <span className="duplicate-file-size">{formatBytes(asset.size_bytes)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function StoragePage({
  summary,
  loading,
  refresh,
  history,
  historySummary,
  historyDays,
  setHistoryDays,
  historyLoading,
  refreshHistory,
}: {
  summary: StorageSummary | null;
  loading: boolean;
  refresh: () => void;
  history: StorageSnapshot[];
  historySummary: StorageHistorySummary | null;
  historyDays: 7 | 30 | 90 | 365;
  setHistoryDays: (days: 7 | 30 | 90 | 365) => void;
  historyLoading: boolean;
  refreshHistory: () => void;
}) {
  const totalBytes = summary?.total_bytes ?? 0;
  const totalFiles = summary?.total_files ?? 0;
  const averageFileSize = totalFiles > 0 ? totalBytes / totalFiles : 0;
  const recoveryRate = totalBytes > 0
    ? ((summary?.duplicate_savings_bytes ?? 0) / totalBytes) * 100
    : 0;
  const largestCategory = summary?.by_file_type.length
    ? summary.by_file_type.reduce(
        (largest, current) => (current.size_bytes > largest.size_bytes ? current : largest),
        summary.by_file_type[0],
      )
    : undefined;
  const maxTypeBytes = Math.max(
    ...(summary?.by_file_type.map((item) => item.size_bytes) ?? [0]),
    1,
  );

  const formatHistoryDate = (value: string) => {
    const date = new Date(value);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  };

  const historyChartData = history.map((snapshot) => ({
    date: formatHistoryDate(snapshot.captured_at),
    storage: snapshot.total_bytes,
    files: snapshot.total_files,
    image_bytes: snapshot.image_bytes,
    video_bytes: snapshot.video_bytes,
    document_bytes: snapshot.document_bytes,
    other_bytes: snapshot.other_bytes,
  }));

  const ranges = [
    { label: "7D", value: 7 as const },
    { label: "30D", value: 30 as const },
    { label: "90D", value: 90 as const },
    { label: "1Y", value: 365 as const },
  ];

  const formatStorageChange = (value: number) => {
    if (value === 0) return "No change";
    return `${value > 0 ? "+" : "-"}${formatBytes(Math.abs(value))}`;
  };

  const formatFileChange = (value: number) => {
    if (value === 0) return "No change";
    return `${value > 0 ? "+" : "-"}${Math.abs(value).toLocaleString()} files`;
  };

  return (
    <section className="storage-page">
      <div className="page-header">
        <div>
          <h2>Storage Intelligence</h2>
          <p>Understand where storage is going and where optimization is possible.</p>
        </div>
        <button
          className="secondary-button"
          onClick={() => {
            refresh();
            refreshHistory();
          }}
          disabled={loading || historyLoading}
        >
          <RefreshCw size={17} className={loading || historyLoading ? "spin" : ""} />
          {loading || historyLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {loading && !summary ? (
        <div className="storage-loading">
          <RefreshCw size={22} className="spin" />
          <div>
            <strong>Calculating storage intelligence</strong>
            <span>Reading indexed asset statistics...</span>
          </div>
        </div>
      ) : summary ? (
        <>
          <div className="summary-grid storage-summary-grid">
            <Summary label="Total Files" value={totalFiles.toLocaleString()} icon={<File size={22} />} />
            <Summary label="Total Storage" value={formatBytes(totalBytes)} icon={<HardDrive size={22} />} />
            <Summary
              label="Potential Recovery"
              value={formatBytes(summary.duplicate_savings_bytes)}
              icon={<Copy size={22} />}
            />
          </div>

          <div className="storage-insight-grid">
            <section className="storage-insight-card">
              <span>Average file size</span>
              <strong>{formatBytes(averageFileSize)}</strong>
              <small>Based on all indexed, non-missing assets.</small>
            </section>
            <section className="storage-insight-card">
              <span>Duplicate rate</span>
              <strong>{recoveryRate > 0 && recoveryRate < 0.1 ? "<0.1" : recoveryRate.toFixed(1)}%</strong>
              <small>Percentage of indexed storage represented by recoverable duplicate data.</small>
            </section>
            <section className="storage-insight-card">
              <span>Largest storage category</span>
              <strong>{largestCategory?.file_type ?? "No data yet"}</strong>
              <small>
                {largestCategory
                  ? `${formatBytes(largestCategory.size_bytes)} across ${largestCategory.file_count.toLocaleString()} files.`
                  : "Storage category information will appear after indexing."}
              </small>
            </section>
          </div>

          <div className="storage-grid">
            <section className="storage-panel">
              <div className="storage-panel-header">
                <div>
                  <h3>Storage by File Type</h3>
                  <p>Space consumption across the indexed library.</p>
                </div>
              </div>
              <div className="storage-type-list">
                {summary.by_file_type.length === 0 ? (
                  <div className="storage-empty">No storage category data is available.</div>
                ) : (
                  summary.by_file_type.map((item) => {
                    const percentage = totalBytes > 0 ? (item.size_bytes / totalBytes) * 100 : 0;
                    const barWidth = (item.size_bytes / maxTypeBytes) * 100;
                    return (
                      <div className="storage-type-row" key={item.file_type}>
                        <div className="storage-type-main">
                          <div className="storage-type-name">
                            {getFileIcon(item.file_type)}
                            <div>
                              <strong>{item.file_type}</strong>
                              <span>{item.file_count.toLocaleString()} files</span>
                            </div>
                          </div>
                          <div className="storage-type-values">
                            <strong>{formatBytes(item.size_bytes)}</strong>
                            <span>{percentage.toFixed(1)}%</span>
                          </div>
                        </div>
                        <div className="storage-progress-track" aria-label={`${percentage.toFixed(1)} percent of storage`}>
                          <div className="storage-progress-fill" style={{ width: `${Math.min(barWidth, 100)}%` }} />
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </section>

            <section className="storage-panel">
              <div className="storage-panel-header">
                <div>
                  <h3>Largest Files</h3>
                  <p>Top 20 indexed files by storage consumption.</p>
                </div>
              </div>
              <div className="storage-file-list">
                {summary.largest_files.length === 0 ? (
                  <div className="storage-empty">No large files are available.</div>
                ) : (
                  summary.largest_files.map((asset, index) => (
                    <div className="storage-ranked-row" key={asset.id}>
                      <span className="storage-rank">{String(index + 1).padStart(2, "0")}</span>
                      <StorageFile asset={asset} />
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>

          <section className="storage-panel old-files-panel">
            <div className="storage-panel-header">
              <div>
                <h3>Older Files</h3>
                <p>Indexed files not modified for more than 30 days. Review before taking any action.</p>
              </div>
              <span className="storage-panel-badge">{summary.old_files.length.toLocaleString()} found</span>
            </div>
            {summary.old_files.length === 0 ? (
              <div className="storage-empty">No files currently match this criterion.</div>
            ) : (
              <div className="storage-file-list">
                {summary.old_files.map((asset) => (
                  <StorageFile asset={asset} key={asset.id} showDate />
                ))}
              </div>
            )}
          </section>

          <section className="storage-optimization">
            <div className="storage-optimization-icon">
              <Sparkles size={22} />
            </div>
            <div>
              <strong>Optimization opportunity</strong>
              <p>
                {summary.duplicate_savings_bytes > 0
                  ? `${formatBytes(summary.duplicate_savings_bytes)} could potentially be recovered by reviewing duplicate groups.`
                  : "No duplicate-storage recovery opportunity is currently reported."}
                {summary.old_files.length > 0 ? " Older files are also available for manual review." : ""}
              </p>
            </div>
          </section>

          <section className="storage-history-section">
            <div className="storage-history-header">
              <div>
                <h3>Storage Trends & Historical Analytics</h3>
                <p>Track how indexed storage and file counts change over time.</p>
              </div>
              <div className="storage-range-selector">
                {ranges.map((range) => (
                  <button
                    key={range.value}
                    className={historyDays === range.value ? "storage-range-button active" : "storage-range-button"}
                    onClick={() => setHistoryDays(range.value)}
                    disabled={historyLoading}
                  >
                    {range.label}
                  </button>
                ))}
              </div>
            </div>

            {historyLoading ? (
              <div className="storage-history-loading">
                <RefreshCw size={21} className="spin" />
                <span>Loading historical storage data...</span>
              </div>
            ) : history.length === 0 ? (
              <div className="storage-history-empty">
                <HardDrive size={30} />
                <strong>No historical snapshots yet</strong>
                <span>Storage history will appear after snapshots are recorded.</span>
              </div>
            ) : (
              <>
                <div className="storage-history-kpis">
                  <div className="storage-history-kpi">
                    <span>Storage change</span>
                    <strong>{formatStorageChange(historySummary?.change_bytes ?? 0)}</strong>
                    <small>
                      {historySummary?.change_percent !== undefined
                        ? `${historySummary.change_percent >= 0 ? "+" : ""}${historySummary.change_percent.toFixed(2)}%`
                        : "0.00%"}
                    </small>
                  </div>
                  <div className="storage-history-kpi">
                    <span>File count change</span>
                    <strong>{formatFileChange(historySummary?.change_files ?? 0)}</strong>
                    <small>Compared with the first snapshot in this range.</small>
                  </div>
                  <div className="storage-history-kpi">
                    <span>Snapshots</span>
                    <strong>{history.length.toLocaleString()}</strong>
                    <small>{historyDays === 365 ? "Last 1 year" : `Last ${historyDays} days`}</small>
                  </div>
                  <div className="storage-history-kpi">
                    <span>Current duplicate recovery</span>
                    <strong>{formatBytes(historySummary?.current_duplicate_savings_bytes ?? 0)}</strong>
                    <small>Potential savings in the latest snapshot.</small>
                  </div>
                </div>

                {history.length === 1 && (
                  <div className="storage-history-note">
                    <strong>One snapshot recorded.</strong>
                    <span>A second snapshot is required before a meaningful historical trend can be calculated.</span>
                  </div>
                )}

                <div className="storage-history-chart-grid">
                  <section className="storage-chart-card">
                    <div className="storage-chart-header">
                      <div>
                        <h4>Storage Usage Over Time</h4>
                        <p>Total indexed storage.</p>
                      </div>
                    </div>
                    <div className="storage-chart">
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={historyChartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" />
                          <YAxis tickFormatter={(value) => formatBytes(Number(value))} />
                          <Tooltip formatter={(value) => formatBytes(Number(value))} />
                          <Line type="monotone" dataKey="storage" name="Storage" strokeWidth={2} dot={history.length <= 30} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </section>

                  <section className="storage-chart-card">
                    <div className="storage-chart-header">
                      <div>
                        <h4>File Count Over Time</h4>
                        <p>Total indexed non-missing files.</p>
                      </div>
                    </div>
                    <div className="storage-chart">
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={historyChartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" />
                          <YAxis tickFormatter={(value) => Number(value).toLocaleString()} />
                          <Tooltip formatter={(value) => Number(value).toLocaleString()} />
                          <Line type="monotone" dataKey="files" name="Files" strokeWidth={2} dot={history.length <= 30} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </section>
                </div>

                <section className="storage-chart-card storage-type-history-card">
                  <div className="storage-chart-header">
                    <div>
                      <h4>Storage by File Type Over Time</h4>
                      <p>Historical storage distribution across images, videos, documents and other files.</p>
                    </div>
                  </div>
                  <div className="storage-chart">
                    <ResponsiveContainer width="100%" height={330}>
                      <BarChart data={historyChartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis tickFormatter={(value) => formatBytes(Number(value))} />
                        <Tooltip formatter={(value) => formatBytes(Number(value))} />
                        <Legend />
                        <Bar
  dataKey="image_bytes"
  stackId="storage"
  name="Images"
  fill="#6366f1"
/>

<Bar
  dataKey="video_bytes"
  stackId="storage"
  name="Videos"
  fill="#22c55e"
/>

<Bar
  dataKey="document_bytes"
  stackId="storage"
  name="Documents"
  fill="#f59e0b"
/>

<Bar
  dataKey="other_bytes"
  stackId="storage"
  name="Other"
  fill="#94a3b8"
/>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </section>
              </>
            )}
          </section>
        </>
      ) : (
        <div className="storage-empty storage-page-empty">
          <HardDrive size={34} />
          <h3>No storage data yet</h3>
          <p>Run a local scan first, then refresh this dashboard.</p>
          <button className="primary-button" onClick={refresh}>Load Storage Intelligence</button>
        </div>
      )}
    </section>
  );
}

function StorageFile({
  asset,
  showDate = false,
}: {
  asset: {
    id: number;
    name: string;
    path: string;
    size_bytes: number;
    file_type: string;
    modified_at: string | null;
  };
  showDate?: boolean;
}) {
  return (
    <div className="storage-file-row">
      <div className="storage-file-info">
        {getFileIcon(asset.file_type)}
        <div>
          <strong>{asset.name}</strong>
          <span title={asset.path}>{asset.path}</span>
          {showDate && <small>Modified: {formatDate(asset.modified_at)}</small>}
        </div>
      </div>
      <strong>{formatBytes(asset.size_bytes)}</strong>
    </div>
  );
}

function DocumentsPage({
  analyses,
  loading,
  statusFilter,
  setStatusFilter,
  refresh,
  ocrDiagnostics,
}: {
  analyses: DocumentAnalysis[];
  loading: boolean;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  refresh: () => void;
  ocrDiagnostics: OCRDiagnostics | null;
}) {
  const analyzedDocuments = analyses.filter(
    (item) => item.analysis_status === "ANALYZED" || item.status === "ANALYZED",
  );
  const pendingDocuments = analyses.filter((item) => item.analysis_status === "PENDING").length;
  const processingDocuments = analyses.filter((item) => item.analysis_status === "PROCESSING").length;
  const failedDocuments = analyses.filter((item) => item.analysis_status === "FAILED" || item.status === "ERROR").length;
  const counts = analyses.reduce(
    (acc, item) => {
      if (item.analysis_status && item.analysis_status !== "ANALYZED") return acc;
      const status = item.document_status || "UNKNOWN";
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  const filtered = statusFilter === "ALL"
    ? analyses
    : analyses.filter((item) => (item.document_status || "UNKNOWN") === statusFilter);

  const statusClass = (status: string) =>
    status === "VALID"
      ? "available"
      : status === "EXPIRING SOON"
        ? "warning"
        : status === "EXPIRED"
          ? "missing"
          : "";

  const dateLabel = (value: string | null) => {
    if (!value) return "-";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
  };

  return (
    <section className="storage-page">
      <div className="page-header">
        <div>
          <h2>Document Intelligence</h2>
          <p>Review extracted document information, OCR results and validity status.</p>
        </div>
        <button className="secondary-button" onClick={refresh} disabled={loading}>
          <RefreshCw size={17} className={loading ? "spin" : ""} />
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {ocrDiagnostics && !ocrDiagnostics.available && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{ocrDiagnostics.message || "OCR is unavailable. Configure TESSERACT_CMD or install Tesseract on PATH."}</span>
        </div>
      )}

        <div className="summary-grid storage-summary-grid">
          <Summary label="Analyzed Documents" value={analyzedDocuments.length.toLocaleString()} icon={<FileText size={22} />} />
        <Summary label="Valid" value={(counts["VALID"] || 0).toLocaleString()} icon={<Sparkles size={22} />} />
        <Summary label="Expiring Soon" value={(counts["EXPIRING SOON"] || 0).toLocaleString()} icon={<AlertTriangle size={22} />} />
        <Summary label="Expired" value={(counts["EXPIRED"] || 0).toLocaleString()} icon={<History size={22} />} />
          <Summary label="Pending" value={pendingDocuments.toLocaleString()} icon={<RefreshCw size={22} />} />
          <Summary label="Processing" value={processingDocuments.toLocaleString()} icon={<RefreshCw size={22} />} />
          <Summary label="Failed" value={failedDocuments.toLocaleString()} icon={<AlertTriangle size={22} />} />
      </div>

      <section className="storage-panel">
        <div className="storage-panel-header">
          <div>
            <h3>Document Status</h3>
            <p>Indexed documents and their analysis and validity status.</p>
          </div>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="ALL">All statuses</option>
            <option value="VALID">Valid</option>
            <option value="EXPIRING SOON">Expiring Soon</option>
            <option value="EXPIRED">Expired</option>
            <option value="UNKNOWN">Unknown</option>
          </select>
        </div>

        {loading ? (
          <div className="storage-history-loading">
            <RefreshCw size={21} className="spin" />
            <span>Loading document analyses...</span>
          </div>
        ) : filtered.length === 0 ? (
          <State
            text={analyses.length ? "No documents match this filter" : "No indexed documents yet"}
            subtext={analyses.length ? "Choose another status filter." : "Scan a local folder containing documents."}
          />
        ) : (
          <div className="storage-file-list">
            {filtered.map((item) => (
              <article key={item.id} className="storage-ranked-row" style={{ display: "block", padding: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 14, alignItems: "flex-start", flexWrap: "wrap" }}>
                  <div className="storage-file-info" style={{ minWidth: 0 }}>
                    <FileText size={22} />
                    <div style={{ minWidth: 0 }}>
                      <strong>{item.name || `Document Asset #${item.asset_id}`}</strong>
                      <span title={item.path || ""}>{item.path || `Asset ID: ${item.asset_id}`}</span>
                      <small>Source: {item.source || "local_pc"} · {item.analysis_status || item.status}</small>
                      {item.analyzed_at && <small>Analyzed: {dateLabel(item.analyzed_at)}</small>}
                    </div>
                  </div>
                  <div style={{ display: "grid", gap: 5, justifyItems: "end" }}>
                    <span className="asset-status">
                      <span className="asset-status-dot" />
                      {item.analysis_status || item.status}
                    </span>
                    {item.analysis_status === "ANALYZED" || !item.analysis_status ? (
                      <span className={`asset-status ${statusClass(item.document_status || "UNKNOWN")}`}>
                        <span className="asset-status-dot" />
                        {item.document_status || "UNKNOWN"}
                      </span>
                    ) : null}
                  </div>
                </div>

                {item.analysis_error && <div className="error-banner">{item.analysis_error}</div>}

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 8, marginTop: 14 }}>
                  <MetricBox label="Type" value={item.document_type || "Unknown"} />
                  <MetricBox label="Confidence" value={item.confidence == null ? "-" : `${Math.round(item.confidence * 100)}%`} />
                  <MetricBox label="Issue Date" value={dateLabel(item.issue_date)} />
                  <MetricBox label="Expiry Date" value={dateLabel(item.expiry_date)} />
                  <MetricBox label="Extracted Name" value={item.extracted_name || "-"} />
                  <MetricBox label="OCR" value={item.ocr_used ? "Used" : "Not required"} />
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="storage-optimization">
        <div className="storage-optimization-icon"><FileText size={22} /></div>
        <div>
          <strong>Document expiry workflow</strong>
          <p>Documents with expiry dates are surfaced as Valid, Expiring Soon or Expired. Unknown dates remain available for manual review.</p>
        </div>
      </section>
    </section>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: "9px 10px", borderRadius: 8, border: "1px solid rgba(100,116,139,0.16)", background: "rgba(148,163,184,0.05)", minWidth: 0 }}>
      <span style={{ display: "block", fontSize: 11, opacity: 0.7, marginBottom: 3 }}>{label}</span>
      <strong style={{ display: "block", fontSize: 13, overflowWrap: "anywhere" }}>{value}</strong>
    </div>
  );
}

function AIImages({ analyses, query, loading, analyzingId, setQuery, analyze, preview }: any) {
  return (
    <section className="ai-images-page">
      <div className="page-header">
        <div>
          <h2>AI Image Understanding</h2>
          <p>Search captions, categories, and tags generated for your images.</p>
        </div>
        <button className="secondary-button" onClick={() => setQuery("")}>
          <RefreshCw size={17} /> Refresh
        </button>
      </div>

      <div className="ai-toolbar">
        <div className="search-box">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search AI metadata, e.g. beach or person..."
          />
        </div>
      </div>

      {loading ? (
        <State text="Loading AI image results" subtext="Please wait while metadata is loaded." />
      ) : analyses.length === 0 ? (
        <State text="No analyzed images found" subtext="Analyze an image from the browser to create AI metadata." />
      ) : (
        <div className="ai-image-grid">
          {analyses.map((item: AIAnalysis) => (
            <article className="ai-image-card" key={item.asset_id} onClick={() => preview(item.asset_id)}>
              <img src={`${API_BASE_URL}/assets/${item.asset_id}/preview`} alt={item.name || "Analyzed image"} />
              <div className="ai-image-info">
                <strong>{item.name || `Asset ${item.asset_id}`}</strong>
                <p>{item.caption || item.analysis_error || "Analysis has not completed."}</p>
                <span>{item.category || "Category pending"}</span>
                <small>
                  {item.analysis_status === "PENDING"
                    ? "Pending"
                    : item.analysis_status === "PROCESSING"
                      ? "Processing"
                      : item.analysis_status === "FAILED"
                        ? "Failed"
                        : item.analysis_status === "ANALYZED" || item.caption
                          ? "Analyzed"
                          : "Not queued"}
                </small>
                <div className="ai-tags">
                  {item.tags.map((tag) => (
                    <small key={tag}>{tag}</small>
                  ))}
                </div>
              </div>
              <div className="ai-card-actions">
                <button
                  className="secondary-button compact"
                  onClick={(e) => {
                    e.stopPropagation();
                    preview(item.asset_id);
                  }}
                >
                  <Eye size={13} /> View
                </button>
                <button
                  className="primary-button compact"
                  onClick={(event) => {
                    event.stopPropagation();
                    void analyze(item.asset_id);
                  }}
                  disabled={
                    analyzingId === item.asset_id ||
                    item.analysis_status === "PENDING" ||
                    item.analysis_status === "PROCESSING"
                  }
                >
                  {analyzingId === item.asset_id
                    ? "Analyzing..."
                    : item.analysis_status === "PENDING" || item.analysis_status === "PROCESSING"
                      ? "Analysis queued"
                      : item.analysis_status === "ANALYZED" || item.caption
                        ? "Re-analyze"
                        : "Analyze"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function Preview({ asset, url, close }: { asset: Asset; url: string; close: () => void }) {
  const [loadError, setLoadError] = useState(false);
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    setLoadError(false);
    setZoomed(false);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [asset.id, close]);

  const isImage = asset.mime_type?.startsWith("image/");
  const isVideo = asset.mime_type?.startsWith("video/");
  const isPdf = asset.mime_type === "application/pdf";

  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="preview-modal preview-modal-enhanced" onClick={(event) => event.stopPropagation()}>
        <div className="preview-header">
          <div className="preview-title-block">
            <div className="preview-file-icon">{getFileIcon(asset.file_type, 20)}</div>
            <div>
              <h3 title={asset.name}>{asset.name}</h3>
              <span title={asset.path}>{asset.path}</span>
            </div>
          </div>
          <div className="preview-header-actions">
            <a
              className="secondary-button compact"
              href={url}
              target="_blank"
              rel="noreferrer"
              title="Open in a new browser tab"
            >
              <ExternalLink size={15} /> Open
            </a>
            <a
              className="secondary-button compact"
              href={url}
              download={asset.name}
              title="Download a copy"
            >
              <Download size={15} /> Download
            </a>
            <button className="icon-button" onClick={close} title="Close preview" aria-label="Close preview">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="preview-meta">
          <span>{asset.file_type}</span>
          <span>{formatBytes(asset.size_bytes)}</span>
          <span>{asset.mime_type || "Unknown MIME type"}</span>
        </div>

        <div className="preview-content preview-content-enhanced">
          {loadError ? (
            <div className="unsupported-preview">
              <AlertTriangle size={48} />
              <strong>Preview could not be loaded.</strong>
              <p>The indexed file may be unavailable or the browser could not render this format.</p>
              <a className="primary-button compact" href={url} target="_blank" rel="noreferrer">
                <ExternalLink size={15} /> Try Open
              </a>
            </div>
          ) : isImage ? (
            <button
              type="button"
              className={`preview-image-button ${zoomed ? "zoomed" : ""}`}
              onClick={() => setZoomed((current) => !current)}
              title={zoomed ? "Fit image" : "Zoom image"}
            >
              <img src={url} alt={asset.name} onError={() => setLoadError(true)} />
            </button>
          ) : isVideo ? (
            <video src={url} controls preload="metadata" onError={() => setLoadError(true)} />
          ) : isPdf ? (
            <iframe src={url} title={asset.name} onError={() => setLoadError(true)} />
          ) : (
            <div className="unsupported-preview">
              <File size={48} />
              <strong>Preview not available for this file type.</strong>
              <p>{asset.mime_type || "Unknown MIME type"}</p>
              <a className="secondary-button compact" href={url} target="_blank" rel="noreferrer">
                <ExternalLink size={15} /> Open File
              </a>
            </div>
          )}
        </div>

        {isImage && !loadError && (
          <div className="preview-hint">Click the image to {zoomed ? "fit it to the preview" : "zoom it"} · Press Esc to close</div>
        )}
      </div>
    </div>
  );
}

function CleanupModal({
  preview,
  loading,
  close,
  execute,
}: {
  preview: CleanupPreview;
  loading: boolean;
  close: () => void;
  execute: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="cleanup-modal" onClick={(event) => event.stopPropagation()}>
        <div className="preview-header">
          <div>
            <h3>Cleanup Preview</h3>
            <span>Review the files before moving them.</span>
          </div>
          <button className="icon-button" onClick={close}>
            <X size={20} />
          </button>
        </div>
        <div className="cleanup-summary">
          <div>
            <strong>{preview.asset_count}</strong>
            <span>Files</span>
          </div>
          <div>
            <strong>{formatBytes(preview.total_size_bytes)}</strong>
            <span>Storage to recover</span>
          </div>
        </div>
        <div className="cleanup-warning">
          <AlertTriangle size={20} />
          <div>
            <strong>Safe recovery operation</strong>
            <p>Files will be moved to the AI-DAM recovery directory. They will not be permanently deleted.</p>
          </div>
        </div>
        <div className="cleanup-preview-list">
          {preview.items.map((item) => (
            <div className="cleanup-preview-item" key={item.asset_id}>
              <div>
                <strong>{item.name}</strong>
                <span title={item.path}>{item.path}</span>
              </div>
              <span>{formatBytes(item.size_bytes)}</span>
            </div>
          ))}
        </div>
        <div className="cleanup-modal-actions">
          <button className="secondary-button" onClick={close}>
            Cancel
          </button>
          <button className="danger-button" onClick={execute} disabled={loading}>
            {loading ? "Moving..." : "Confirm & Move to Recovery"}
          </button>
        </div>
      </div>
    </div>
  );
}

function State({ text, subtext }: { text: string; subtext: string }) {
  return (
    <div className="empty-state">
      <File size={42} />
      <h3>{text}</h3>
      <p>{subtext}</p>
    </div>
  );
}

function Summary({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="summary-card">
      <div className="summary-icon">{icon}</div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default App;
