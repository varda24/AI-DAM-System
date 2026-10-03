export interface Asset {
  id: number;
  source: string;
  source_account_id?: string;
  source_folder_id?: string | null;
  drive_file_id?: string;
  web_view_link?: string;
  name: string;
  path: string;
  extension: string | null;
  mime_type: string | null;
  file_type: string;
  size_bytes: number;
  created_at: string | null;
  modified_at: string | null;
  accessed_at: string | null;
  is_missing: boolean;
  last_scanned_at: string | null;
  sha256?: string | null;
}

export interface DuplicateAsset {
  id: number;
  source?: string;
  source_account_id?: string | null;
  source_folder_id?: string | null;
  drive_file_id?: string | null;
  web_view_link?: string | null;
  name: string;
  path: string;
  size_bytes: number;
  file_type: string;
  modified_at: string | null;
}

export interface DuplicateGroup {
  id: number;
  sha256: string;
  file_size_bytes: number;
  file_count: number;
  potential_savings_bytes: number;
  created_at: string | null;
  assets: DuplicateAsset[];
}

export interface DuplicateSummary {
  duplicate_groups: number;
  duplicate_files: number;
  potential_savings_bytes: number;
}

export interface StorageSummary {
  total_files: number;
  total_bytes: number;
  duplicate_savings_bytes: number;
  by_file_type: {
    file_type: string;
    file_count: number;
    size_bytes: number;
  }[];
  largest_files: {
    id: number;
    name: string;
    path: string;
    size_bytes: number;
    file_type: string;
    modified_at: string | null;
  }[];
  old_files: {
    id: number;
    name: string;
    path: string;
    size_bytes: number;
    file_type: string;
    modified_at: string | null;
  }[];
}

/* =========================================================
   Storage History
   ========================================================= */

export interface StorageSnapshot {
  id: number;
  captured_at: string;
  source: string;
  total_files: number;
  total_bytes: number;
  duplicate_savings_bytes: number;
  image_files: number;
  image_bytes: number;
  video_files: number;
  video_bytes: number;
  document_files: number;
  document_bytes: number;
  other_files: number;
  other_bytes: number;
}

export interface StorageHistoryResponse {
  source: string;
  days: number;
  snapshot_count: number;
  snapshots: StorageSnapshot[];
}

export interface StorageHistorySummary {
  source: string;
  days: number;
  snapshot_count: number;
  first_snapshot: string | null;
  latest_snapshot: string | null;
  current_total_bytes: number;
  previous_total_bytes: number;
  change_bytes: number;
  change_percent: number;
  current_total_files: number;
  previous_total_files: number;
  change_files: number;
  current_duplicate_savings_bytes: number;
  previous_duplicate_savings_bytes: number;
}

/* =========================================================
   AI Image Analysis
   ========================================================= */

export interface AIAnalysis {
  asset_id: number;
  name?: string;
  path?: string;
  size_bytes?: number;
  mime_type?: string | null;
  caption: string | null;
  category: string | null;
  tags: string[];
  analyzed_at: string | null;
  analysis_status?: "PENDING" | "PROCESSING" | "ANALYZED" | "FAILED" | "NOT_QUEUED";
  analysis_error?: string | null;
}

export interface AnalysisProgress {
  totals: Record<"PENDING" | "PROCESSING" | "ANALYZED" | "FAILED", number>;
  by_type: Record<string, Record<string, number>>;
  worker_running: boolean;
}

/* =========================================================
   Face Analysis
   ========================================================= */

export interface FaceAnalysisResult {
  asset_id: number;
  faces_detected: number;
  faces: {
    face_index: number;
    confidence: number;
    bbox: number[] | null;
  }[];
  status: "analyzed" | "missing";
}

export interface VideoAnalysis {
  id: number;
  asset_id: number;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  frame_count: number | null;
  video_codec: string | null;
  thumbnail_path: string | null;
  status: string;
  error_message: string | null;
  analyzed_at: string | null;
}

export interface VideoSimilarityMember {
  asset_id: number;
  name: string;
  path: string;
  size_bytes: number;
  similarity: number;
}

export interface VideoSimilarityGroup {
  group_id: number;
  member_count: number;
  potential_savings_bytes: number;
  members: VideoSimilarityMember[];
}

export interface VideoSimilarityResponse {
  videos_checked: number;
  fingerprints_created: number;
  similar_groups: VideoSimilarityGroup[];
  group_count: number;
  potential_savings_bytes: number;
  errors: Array<{
    asset_id: number;
    name: string;
    error: string;
  }>;
  threshold: number;
}

export interface DocumentAnalysis {
  id: number | null;
  asset_id: number;
  document_type: string | null;
  confidence: number | null;
  extracted_text: string | null;
  extracted_name: string | null;
  issue_date: string | null;
  document_date?: string | null;
  expiry_date: string | null;
  issue_date_source?: string | null;
  expiry_date_source?: string | null;
  expiry_confidence?: number | null;
  issuing_organization?: string | null;
  document_status: "VALID" | "EXPIRING SOON" | "EXPIRED" | "UNKNOWN";
  days_until_expiry: number | null;
  ocr_used: boolean;
  page_count: number | null;
  status: string;
  error_message: string | null;
  analyzed_at: string | null;
  analysis_status?: "PENDING" | "PROCESSING" | "ANALYZED" | "FAILED" | "NOT_QUEUED" | string;
  analysis_error?: string | null;
  source?: string;
  file_type?: string;
  name?: string | null;
  path?: string | null;
  size_bytes?: number;
}

export interface OCRDiagnostics {
  available: boolean;
  command: string | null;
  message: string | null;
}

export interface DocumentSummary {
  total_analyzed: number;
  valid: number;
  expiring_soon: number;
  expired: number;
  unknown: number;
  warning_days: number;
}

export interface DocumentExpiryResponse {
  warning_days: number;
  status: string | null;
  total: number;
  documents: DocumentAnalysis[];
}

export interface DocumentBatchResult {
  requested: number;
  analyzed: number;
  skipped: number;
  results: DocumentAnalysis[];
  skipped_items: Array<{
    asset_id: number;
    name?: string;
    reason: string;
  }>;
}



/* =========================================================
   Cleanup
   ========================================================= */

export interface CleanupPreview {
  asset_count: number;
  total_size_bytes: number;
  items: {
    asset_id: number;
    name: string;
    path: string;
    size_bytes: number;
    exists: boolean;
    action: string;
  }[];
}

export interface CleanupOperationRecord {
  id: number;
  status: string;
  action: string;
  asset_count: number;
  total_size_bytes: number;
  created_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface CleanupItemRecord {
  id: number;
  asset_id: number;
  original_path: string;
  recovery_path: string | null;
  size_bytes: number;
  status: string;
  error_message: string | null;
}

export interface CleanupOperationDetail extends CleanupOperationRecord {
  items: CleanupItemRecord[];
}

/* =========================================================
   Person / Face Clustering
   ========================================================= */

export interface PersonClusterAsset {
  id: number;
  name: string;
  path: string;
  mime_type: string | null;
  file_type: string;
  size_bytes: number;
}

export interface PersonCluster {
  id: number;
  label: string | null;
  face_count: number;
  confidence: number | null;
  asset_ids: number[];
  assets?: PersonClusterAsset[];
  created_at: string | null;
}

/* =========================================================
   AI Collections
   ========================================================= */

export interface CollectionSuggestion {
  name: string;
  type: string;
  description: string;
  asset_count: number;
  confidence: number;
  matched_keywords?: string[];
  start_time?: string | null;
  end_time?: string | null;
  asset_ids: number[];
}

export interface ApprovedCollection {
  id: number;
  name: string;
  description: string | null;
  collection_type: string;
  status: string;
  confidence: number | null;
  asset_count: number;
  created_at: string;
}

/* =========================================================
   Visual Similarity
   ========================================================= */

export interface VisualSimilarAsset {
  id: number;
  source?: string;
  source_account_id?: string | null;
  source_folder_id?: string | null;
  drive_file_id?: string | null;
  web_view_link?: string | null;
  name: string;
  path: string;
  size_bytes: number;
  mime_type: string | null;
  modified_at: string | null;
  perceptual_hash: string;
}

export interface VisualSimilarGroup {
  id: number;
  asset_count: number;
  assets: VisualSimilarAsset[];
}
