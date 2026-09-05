export interface Asset {
  id: number;
  source: string;
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
}

export interface DuplicateAsset {
  id: number;
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
  by_file_type: { file_type: string; file_count: number; size_bytes: number }[];
  largest_files: { id: number; name: string; path: string; size_bytes: number; file_type: string; modified_at: string | null }[];
  old_files: { id: number; name: string; path: string; size_bytes: number; file_type: string; modified_at: string | null }[];
}

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
}

export interface FaceAnalysisResult {
  asset_id: number;
  faces_detected: number;
  faces: { face_index: number; confidence: number; bbox: number[] | null }[];
  status: "analyzed" | "missing";
}

export interface CleanupPreview {
  asset_count: number;
  total_size_bytes: number;
  items: { asset_id: number; name: string; path: string; size_bytes: number; exists: boolean; action: string }[];
}

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

export interface VisualSimilarAsset {
  id: number;
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
