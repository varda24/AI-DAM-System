import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Film,
  Gauge,
  HardDrive,
  RefreshCw,
  ScanSearch,
} from "lucide-react";

import type {
  Asset,
  VideoAnalysis,
  VideoSimilarityResponse,
} from "../types";


interface VideoIntelligenceProps {
  asset: Asset | null;
  analysis: VideoAnalysis | null;
  analysisLoading: boolean;
  similarity: VideoSimilarityResponse | null;
  similarityLoading: boolean;
  onAnalyze: (assetId: number) => void;
  onReanalyze: (assetId: number) => void;
  onDetectSimilarity: (assetIds: number[]) => void;
}


function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) {
    return "0 B";
  }

  const units = [
    "B",
    "KB",
    "MB",
    "GB",
    "TB",
  ];

  let value = bytes;
  let index = 0;

  while (
    value >= 1024 &&
    index < units.length - 1
  ) {
    value /= 1024;
    index += 1;
  }

  return `${value.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
}


function formatDuration(
  seconds: number | null | undefined,
): string {
  if (
    seconds === null ||
    seconds === undefined ||
    !Number.isFinite(seconds)
  ) {
    return "Unknown";
  }

  const totalSeconds = Math.max(
    0,
    Math.round(seconds),
  );

  const hours = Math.floor(
    totalSeconds / 3600,
  );

  const minutes = Math.floor(
    (totalSeconds % 3600) / 60,
  );

  const remainingSeconds =
    totalSeconds % 60;

  if (hours > 0) {
    return [
      hours.toString().padStart(2, "0"),
      minutes.toString().padStart(2, "0"),
      remainingSeconds
        .toString()
        .padStart(2, "0"),
    ].join(":");
  }

  return [
    minutes.toString().padStart(2, "0"),
    remainingSeconds
      .toString()
      .padStart(2, "0"),
  ].join(":");
}


export default function VideoIntelligence({
  asset,
  analysis,
  analysisLoading,
  similarity,
  similarityLoading,
  onAnalyze,
  onReanalyze,
  onDetectSimilarity,
}: VideoIntelligenceProps) {
  if (!asset) {
    return null;
  }

  const thumbnailUrl =
    analysis?.thumbnail_path
      ? `/api/videos/${asset.id}/thumbnail`
      : null;

  const hasAnalysis =
    analysis?.status === "analyzed";

  const isMissing =
    analysis?.status === "missing";

  const isInvalid =
    analysis?.status === "invalid";

  return (
    <section className="video-intelligence-section">
      <div className="video-intelligence-header">
        <div>
          <h3>
            <Film size={18} />
            Video Intelligence
          </h3>

          <p>
            Analyze video metadata, generate a thumbnail,
            and compare visual similarity.
          </p>
        </div>

        <div className="video-intelligence-actions">
          {!hasAnalysis && (
            <button
              type="button"
              className="button primary"
              onClick={() =>
                onAnalyze(asset.id)
              }
              disabled={analysisLoading}
            >
              {analysisLoading ? (
                <>
                  <RefreshCw
                    size={15}
                    className="spin"
                  />
                  Analyzing...
                </>
              ) : (
                <>
                  <ScanSearch size={15} />
                  Analyze Video
                </>
              )}
            </button>
          )}

          {hasAnalysis && (
            <button
              type="button"
              className="button secondary"
              onClick={() =>
                onReanalyze(asset.id)
              }
              disabled={analysisLoading}
            >
              <RefreshCw
                size={15}
                className={
                  analysisLoading
                    ? "spin"
                    : undefined
                }
              />

              {analysisLoading
                ? "Analyzing..."
                : "Re-analyze"}
            </button>
          )}
        </div>
      </div>

      {analysisLoading && !analysis && (
        <div className="video-intelligence-state">
          <RefreshCw
            size={22}
            className="spin"
          />

          <span>
            Reading video metadata and generating
            thumbnail...
          </span>
        </div>
      )}

      {isMissing && (
        <div className="video-intelligence-state error">
          <AlertCircle size={20} />

          <div>
            <strong>Video file is missing</strong>
            <span>
              The indexed path no longer exists.
            </span>
          </div>
        </div>
      )}

      {isInvalid && (
        <div className="video-intelligence-state error">
          <AlertCircle size={20} />

          <div>
            <strong>
              Video could not be opened
            </strong>

            <span>
              OpenCV could not decode this file.
            </span>
          </div>
        </div>
      )}

      {hasAnalysis && (
        <>
          <div className="video-intelligence-grid">
            <div className="video-thumbnail-card">
              {thumbnailUrl ? (
                <img
                  src={thumbnailUrl}
                  alt={`Thumbnail for ${asset.name}`}
                />
              ) : (
                <div className="video-thumbnail-empty">
                  <Film size={32} />
                  <span>
                    No thumbnail
                  </span>
                </div>
              )}
            </div>

            <div className="video-metadata-card">
              <div className="video-analysis-status">
                <CheckCircle2 size={16} />
                Analysis complete
              </div>

              <div className="video-metadata-grid">
                <div>
                  <Clock3 size={15} />
                  <span>Duration</span>
                  <strong>
                    {formatDuration(
                      analysis.duration_seconds,
                    )}
                  </strong>
                </div>

                <div>
                  <Film size={15} />
                  <span>Resolution</span>
                  <strong>
                    {analysis.width &&
                    analysis.height
                      ? `${analysis.width} × ${analysis.height}`
                      : "Unknown"}
                  </strong>
                </div>

                <div>
                  <Gauge size={15} />
                  <span>Frame Rate</span>
                  <strong>
                    {analysis.fps
                      ? `${analysis.fps.toFixed(2)} FPS`
                      : "Unknown"}
                  </strong>
                </div>

                <div>
                  <Film size={15} />
                  <span>Frames</span>
                  <strong>
                    {analysis.frame_count
                      ? analysis.frame_count.toLocaleString()
                      : "Unknown"}
                  </strong>
                </div>

                <div>
                  <Film size={15} />
                  <span>Codec</span>
                  <strong>
                    {analysis.video_codec ||
                      "Unknown"}
                  </strong>
                </div>

                <div>
                  <HardDrive size={15} />
                  <span>File Size</span>
                  <strong>
                    {formatBytes(
                      asset.size_bytes,
                    )}
                  </strong>
                </div>
              </div>
            </div>
          </div>

          <div className="video-similarity-panel">
            <div>
              <div className="video-similarity-heading">
                <div>
                  <h4>
                    Similar Video Detection
                  </h4>

                  <p>
                    Compare this video with other
                    selected videos using sampled
                    frame fingerprints.
                  </p>
                </div>

                <button
                  type="button"
                  className="button secondary"
                  onClick={() =>
                    onDetectSimilarity([
                      asset.id,
                    ])
                  }
                  disabled={
                    similarityLoading
                  }
                  title="Select at least two videos to compare"
                >
                  <ScanSearch size={15} />
                  Detect Similar
                </button>
              </div>
            </div>

            {similarityLoading && (
              <div className="video-similarity-loading">
                <RefreshCw
                  size={18}
                  className="spin"
                />

                Comparing video frames...
              </div>
            )}

            {!similarityLoading &&
              similarity && (
                <>
                  <div className="video-similarity-summary">
                    <div>
                      <span>
                        Videos Checked
                      </span>

                      <strong>
                        {similarity.videos_checked}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Similar Groups
                      </span>

                      <strong>
                        {similarity.group_count}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Potential Recovery
                      </span>

                      <strong>
                        {formatBytes(
                          similarity.potential_savings_bytes,
                        )}
                      </strong>
                    </div>
                  </div>

                  {similarity.similar_groups.length ===
                    0 && (
                    <div className="video-similarity-empty">
                      <CheckCircle2 size={18} />

                      <span>
                        No similar video groups
                        were found at the current
                        threshold.
                      </span>
                    </div>
                  )}

                  {similarity.similar_groups.map(
                    (group) => (
                      <div
                        key={group.group_id}
                        className="video-similarity-group"
                      >
                        <div>
                          <strong>
                            Similar Group{" "}
                            #{group.group_id}
                          </strong>

                          <span>
                            {group.member_count} videos
                            {" · "}
                            {formatBytes(
                              group.potential_savings_bytes,
                            )}{" "}
                            potential recovery
                          </span>
                        </div>

                        <div>
                          {group.members.map(
                            (member) => (
                              <div
                                key={
                                  member.asset_id
                                }
                                className="video-similarity-member"
                              >
                                <span>
                                  {member.name}
                                </span>

                                <strong>
                                  {typeof member.similarity ===
                                    "number"
                                    ? `${member.similarity.toFixed(
                                        2,
                                      )}%`
                                    : "—"}
                                </strong>
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    ),
                  )}
                </>
              )}
          </div>
        </>
      )}
    </section>
  );
}