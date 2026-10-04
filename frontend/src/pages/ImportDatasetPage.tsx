import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Database,
  RefreshCw,
  Clock,
  Copy,
  Check,
  FolderPlus,
  Loader2,
  ArrowDownCircle,
} from 'lucide-react';
import { DatasetInfo, IngestionError, SystemStats } from '../types';
import { api } from '../services/api';

interface ImportDatasetPageProps {
  datasets: DatasetInfo[];
  selectedDatasetPath: string;
  onSelectDatasetPath: (path: string) => void;
  onRunPipeline: (path?: string) => Promise<void>;
  isLoading: boolean;
  errors: IngestionError[];
  stats: SystemStats | null;
  onNavigateToIncidents: () => void;
}

/* ── Pipeline stage definition ─────────────────────────────────────────── */
const PIPELINE_STAGES = [
  {
    id: 'upload',
    name: 'Upload',
    detail: 'Discover node tree & log families',
  },
  {
    id: 'parse',
    name: 'Parse',
    detail: 'Line-by-line syntax extraction',
  },
  {
    id: 'validate',
    name: 'Validate',
    detail: 'Isolate malformed timestamps',
  },
  {
    id: 'normalize',
    name: 'Normalize',
    detail: 'UTC millisecond standardization',
  },
  {
    id: 'store',
    name: 'Store',
    detail: 'DuckDB columnar persistence',
  },
  {
    id: 'correlate',
    name: 'Correlate',
    detail: 'Causal & sequence edge building',
  },
  {
    id: 'reconstruct',
    name: 'Reconstruct',
    detail: 'Multi-node incident grouping',
  },
  {
    id: 'narrative',
    name: 'Narrative',
    detail: 'AI engineering brief generation',
  },
  {
    id: 'ready',
    name: 'Ready',
    detail: 'L1–L4 observability workbench',
  },
];

export const ImportDatasetPage: React.FC<ImportDatasetPageProps> = ({
  datasets,
  selectedDatasetPath,
  onSelectDatasetPath,
  onRunPipeline,
  isLoading,
  errors,
  stats,
  onNavigateToIncidents,
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [uploadedDataset, setUploadedDataset] = useState<DatasetInfo | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [searchError, setSearchError] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeDataset =
    uploadedDataset ||
    datasets.find((d) => d.path === selectedDatasetPath) ||
    datasets[0] ||
    null;

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploadStatus('Uploading log files…');

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const relativePath = file.webkitRelativePath || file.name;
      formData.append('files', file, relativePath);
    }

    try {
      const res = await api.uploadDataset(formData);
      setUploadedDataset(res.dataset);
      onSelectDatasetPath(res.dataset.path);
      setUploadStatus(
        `Dataset uploaded successfully — ${res.dataset.file_count} files, ${res.dataset.nodes.length} nodes detected.`
      );
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
      setUploadStatus(null);
    }
  };

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 1500);
  };

  /* Stage resolution */
  const totalEvents   = stats?.events?.total_events || 0;
  const skippedCount  = stats?.events?.ingestion_errors || errors.length;
  const relCount      = stats?.relationships?.total || 0;
  const incidentCount = stats?.incidents?.total || 0;

  const stageState = (id: string): 'done' | 'active' | 'pending' => {
    if (id === 'upload') return activeDataset ? 'done' : 'pending';
    if (isLoading) return 'active';
    switch (id) {
      case 'parse':
      case 'validate':
      case 'normalize':
      case 'store':
        return totalEvents > 0 ? 'done' : 'pending';
      case 'correlate':
        return relCount > 0 ? 'done' : 'pending';
      case 'reconstruct':
      case 'narrative':
        return incidentCount > 0 ? 'done' : 'pending';
      case 'ready':
        return totalEvents > 0 ? 'done' : 'pending';
      default:
        return 'pending';
    }
  };

  const filteredErrors = errors.filter((err) => {
    if (!searchError) return true;
    const q = searchError.toLowerCase();
    return (
      (err.source_file && err.source_file.toLowerCase().includes(q)) ||
      (err.reason && err.reason.toLowerCase().includes(q)) ||
      (err.raw_record && err.raw_record.toLowerCase().includes(q))
    );
  });

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        padding: '20px 24px',
        height: 'calc(100vh - var(--navbar-height))',
        overflowY: 'auto',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* ----------------------------------------------------------------- */}
      {/* PAGE HEADER                                                         */}
      {/* ----------------------------------------------------------------- */}
      <div>
        <div className="section-label" style={{ marginBottom: '2px' }}>Log Ingestion</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h1 className="page-title">Import Log Dataset</h1>
            <p
              className="text-sm text-secondary"
              style={{ marginTop: '4px', maxWidth: '640px', lineHeight: 1.55 }}
            >
              Upload a multi-node log dataset for automated ingestion, deterministic causal
              correlation, and AI-assisted incident reconstruction.
            </p>
          </div>
          {activeDataset && totalEvents > 0 && !isLoading && (
            <button
              className="btn-ops btn-ops-primary"
              onClick={onNavigateToIncidents}
              style={{ fontSize: '0.78rem' }}
            >
              <span>Explore Incidents</span>
              <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* UPLOAD AREA                                                         */}
      {/* ----------------------------------------------------------------- */}
      <div className="ops-panel" style={{ padding: '20px 22px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '14px', marginBottom: '16px', flexWrap: 'wrap' }}>
          <div>
            <div className="panel-title" style={{ marginBottom: '3px' }}>Upload Dataset Files</div>
            <p className="text-xs text-muted">
              Supports log directories, individual <code>.log</code> files, or <code>.zip</code> archives.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="file"
              ref={fileInputRef}
              multiple
              // @ts-ignore
              webkitdirectory="true"
              directory="true"
              style={{ display: 'none' }}
              onChange={(e) => handleFileUpload(e.target.files)}
            />
            <button
              className="btn-ops btn-ops-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
            >
              <FolderPlus size={13} />
              <span>Browse Folder</span>
            </button>
          </div>
        </div>

        {/* Drop zone */}
        <div
          className={`upload-zone${dragOver ? ' dragover' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFileUpload(e.dataTransfer.files); }}
          onClick={() => fileInputRef.current?.click()}
        >
          <UploadCloud
            size={34}
            color={dragOver ? 'var(--text-accent)' : 'var(--text-dim)'}
            style={{ margin: '0 auto 10px auto' }}
          />
          <div style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Drag & drop log dataset here
          </div>
          <p className="text-xs text-muted">
            or click to browse files
          </p>

          {/* Directory structure hint */}
          <div
            style={{
              display: 'inline-block',
              marginTop: '16px',
              textAlign: 'left',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 16px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="section-label" style={{ marginBottom: '4px' }}>Expected structure</div>
            <pre
              className="font-mono text-xs text-secondary"
              style={{ fontSize: '0.71rem', margin: 0, lineHeight: 1.6 }}
            >
{`Dataset/
├── NODE_A/
│   ├── operator.log
│   ├── planning.log
│   ├── guidance.log
│   ├── state.log
│   └── fault_recovery.log
├── NODE_B/
└── NODE_C/`}
            </pre>
          </div>
        </div>

        {/* Upload feedback */}
        {uploadStatus && (
          <div
            style={{
              marginTop: '12px',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--status-nominal-bg)',
              border: '1px solid var(--status-nominal-border)',
              color: 'var(--status-nominal)',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
            }}
          >
            <CheckCircle2 size={14} />
            <span>{uploadStatus}</span>
          </div>
        )}
        {uploadError && (
          <div
            style={{
              marginTop: '12px',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--status-critical-bg)',
              border: '1px solid var(--status-critical-border)',
              color: 'var(--status-critical)',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              gap: '7px',
            }}
          >
            <AlertTriangle size={14} />
            <span>{uploadError}</span>
          </div>
        )}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* DATASET PREVIEW (when selected)                                     */}
      {/* ----------------------------------------------------------------- */}
      {activeDataset && (
        <div className="ops-panel" style={{ padding: '16px 20px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
              marginBottom: '14px',
            }}
          >
            <div>
              <div className="section-label" style={{ marginBottom: '2px' }}>
                Selected dataset
              </div>
              <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)' }}>
                {activeDataset.name}
              </div>
              <div className="font-mono text-xs text-dim" style={{ marginTop: '2px' }}>
                {activeDataset.path}
              </div>
            </div>
            <button
              className="btn-ops btn-ops-primary"
              onClick={() => onRunPipeline(activeDataset.path)}
              disabled={isLoading}
              style={{ padding: '6px 16px', fontSize: '0.8rem' }}
            >
              <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
              <span>
                {isLoading ? 'Executing Pipeline…' : 'Run Full Pipeline'}
              </span>
            </button>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: '10px',
            }}
          >
            {/* Nodes */}
            <div className="ops-panel-inset" style={{ padding: '10px 13px' }}>
              <div className="section-label" style={{ marginBottom: '5px' }}>Detected Nodes</div>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {activeDataset.nodes.length > 0 ? (
                  activeDataset.nodes.map((n) => (
                    <span
                      key={n}
                      className={`ops-badge ${
                        n === 'NODE_A' ? 'ops-badge-node-a'
                        : n === 'NODE_B' ? 'ops-badge-node-b'
                        : 'ops-badge-node-c'
                      }`}
                    >
                      {n}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-dim">Scanning…</span>
                )}
              </div>
            </div>

            {/* Log families */}
            <div className="ops-panel-inset" style={{ padding: '10px 13px' }}>
              <div className="section-label" style={{ marginBottom: '5px' }}>Log Families</div>
              <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                {activeDataset.log_families.length > 0 ? (
                  activeDataset.log_families.map((f) => (
                    <span key={f} className="ops-badge ops-badge-muted">{f}</span>
                  ))
                ) : (
                  <span className="text-xs text-dim">Scanning…</span>
                )}
              </div>
            </div>

            {/* File count */}
            <div className="ops-panel-inset" style={{ padding: '10px 13px' }}>
              <div className="section-label" style={{ marginBottom: '3px' }}>Log Files</div>
              <div className="font-mono" style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                {activeDataset.file_count}
              </div>
              <div className="text-xs text-muted">files</div>
            </div>

            {/* Records */}
            <div className="ops-panel-inset" style={{ padding: '10px 13px' }}>
              <div className="section-label" style={{ marginBottom: '3px' }}>Ingested Records</div>
              <div
                className="font-mono"
                style={{
                  fontSize: '1.15rem',
                  fontWeight: 800,
                  color: totalEvents > 0 ? 'var(--status-nominal)' : 'var(--text-dim)',
                }}
              >
                {totalEvents > 0 ? totalEvents.toLocaleString() : '—'}
              </div>
              <div className="text-xs text-muted">
                {totalEvents > 0 ? 'valid events' : 'pending analysis'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      <div className="ops-panel" style={{ padding: '18px 22px' }}>
        <div style={{ marginBottom: '16px' }}>
          <div className="panel-title" style={{ marginBottom: '2px' }}>
            Automated Analysis Pipeline
          </div>
          <p className="text-xs text-muted">
            End-to-end multi-node log correlation &amp; causal incident reconstruction
          </p>
        </div>

        {/* Horizontal pipeline stepper */}
        <div style={{ display: 'flex', alignItems: 'flex-start', overflowX: 'auto', paddingBottom: '4px' }}>
          {PIPELINE_STAGES.map((stage, idx) => {
            const state = stageState(stage.id);
            const isLast = idx === PIPELINE_STAGES.length - 1;
            const nextState = !isLast ? stageState(PIPELINE_STAGES[idx + 1].id) : 'pending';
            const connectorDone = state === 'done' && nextState === 'done';

            return (
              <React.Fragment key={stage.id}>
                {/* Stage cell */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '72px', flex: 1 }}>
                  {/* Dot */}
                  <div
                    style={{
                      width: '24px',
                      height: '24px',
                      borderRadius: '50%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.58rem',
                      fontWeight: 800,
                      color: 'white',
                      background:
                        state === 'done' ? 'var(--status-nominal)'
                        : state === 'active' ? 'var(--text-accent)'
                        : 'var(--border-strong)',
                      flexShrink: 0,
                      zIndex: 2,
                      boxShadow:
                        state === 'done' ? '0 0 0 3px var(--status-nominal-bg)'
                        : state === 'active' ? '0 0 0 3px var(--status-info-bg)'
                        : 'none',
                      transition: 'background 0.2s ease',
                    }}
                  >
                    {state === 'done' ? (
                      <Check strokeWidth={3} size={12} />
                    ) : state === 'active' ? (
                      <Loader2 size={11} className="animate-spin" />
                    ) : (
                      <span>{idx + 1}</span>
                    )}
                  </div>

                  {/* Label */}
                  <div
                    style={{
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      textAlign: 'center',
                      marginTop: '5px',
                      color:
                        state === 'done' ? 'var(--status-nominal)'
                        : state === 'active' ? 'var(--text-accent)'
                        : 'var(--text-secondary)',
                      lineHeight: 1.2,
                    }}
                  >
                    {stage.name}
                  </div>
                  <div
                    style={{
                      fontSize: '0.56rem',
                      color: 'var(--text-dim)',
                      textAlign: 'center',
                      marginTop: '1px',
                      lineHeight: 1.2,
                      maxWidth: '72px',
                    }}
                  >
                    {stage.detail}
                  </div>
                </div>

                {/* Connector line */}
                {!isLast && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      paddingTop: '10px',
                      flexShrink: 0,
                      minWidth: '20px',
                      flex: '0 1 40px',
                    }}
                  >
                    <div
                      style={{
                        height: '2px',
                        flex: 1,
                        background: connectorDone ? 'var(--status-nominal)' : 'var(--border-default)',
                        transition: 'background 0.3s ease',
                      }}
                    />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* PROCESSING STATUS METRICS                                           */}
      {/* ----------------------------------------------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
        <div className="metric-card">
          <span className="metric-card-label">Normalized Records</span>
          <div
            className="metric-card-value"
            style={{ color: totalEvents > 0 ? 'var(--text-accent)' : 'var(--text-dim)' }}
          >
            {totalEvents.toLocaleString()}
          </div>
          <div className="metric-card-sub">Valid timestamps & attributes</div>
        </div>

        <div className="metric-card">
          <span className="metric-card-label">Quarantined / Skipped</span>
          <div
            className="metric-card-value"
            style={{ color: skippedCount > 0 ? 'var(--status-warning)' : 'var(--status-nominal)' }}
          >
            {skippedCount}
          </div>
          <div className="metric-card-sub">Malformed lines isolated</div>
        </div>

        <div className="metric-card">
          <span className="metric-card-label">Causal Graph Links</span>
          <div
            className="metric-card-value"
            style={{ color: relCount > 0 ? 'var(--node-b-color)' : 'var(--text-dim)' }}
          >
            {relCount.toLocaleString()}
          </div>
          <div className="metric-card-sub">Deterministic relationships</div>
        </div>

        <div className="metric-card">
          <span className="metric-card-label">Incident Cascades</span>
          <div
            className="metric-card-value"
            style={{ color: incidentCount > 0 ? 'var(--status-critical)' : 'var(--text-dim)' }}
          >
            {incidentCount}
          </div>
          <div className="metric-card-sub">Reconstructed candidates</div>
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* SKIPPED / INVALID RECORDS AUDIT REPORT                             */}
      {/* ----------------------------------------------------------------- */}
      <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="ops-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={14} color="var(--status-warning)" />
            <span className="panel-title">
              Ingestion Quarantine Report
            </span>
            <span
              className="font-mono"
              style={{
                fontSize: '0.67rem',
                padding: '1px 5px',
                borderRadius: 'var(--radius-xs)',
                background: errors.length > 0 ? 'var(--status-warning-bg)' : 'var(--bg-surface-elevated)',
                color: errors.length > 0 ? 'var(--status-warning)' : 'var(--text-muted)',
                fontWeight: 700,
              }}
            >
              {errors.length}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="text-xs text-muted">
              Malformed lines are isolated; downstream causal graphs are unaffected
            </span>
            {errors.length > 0 && (
              <input
                type="text"
                placeholder="Filter errors…"
                value={searchError}
                onChange={(e) => setSearchError(e.target.value)}
                className="ops-input"
                style={{ fontSize: '0.72rem', width: '160px' }}
              />
            )}
          </div>
        </div>

        <div style={{ overflowX: 'auto', maxHeight: '320px' }}>
          <table className="ops-table">
            <thead>
              <tr>
                <th style={{ width: '220px' }}>Source File</th>
                <th style={{ width: '80px' }}>Line #</th>
                <th style={{ width: '90px' }}>Node</th>
                <th style={{ width: '200px' }}>Quarantine Reason</th>
                <th>Raw Record</th>
                <th style={{ width: '60px', textAlign: 'center' }}>Copy</th>
              </tr>
            </thead>
            <tbody>
              {errors.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    style={{ textAlign: 'center', padding: '32px', color: 'var(--text-dim)' }}
                  >
                    <CheckCircle2
                      size={20}
                      color="var(--status-nominal)"
                      style={{ display: 'block', margin: '0 auto 6px' }}
                    />
                    No malformed records quarantined — full dataset parsed cleanly.
                  </td>
                </tr>
              ) : (
                filteredErrors.map((err, idx) => (
                  <tr key={err.id || idx} className="ops-table-row">
                    <td className="font-mono text-xs" style={{ color: 'var(--text-primary)' }}>
                      {err.source_file}
                    </td>
                    <td
                      className="font-mono"
                      style={{ fontSize: '0.74rem', color: 'var(--text-accent)', fontWeight: 700 }}
                    >
                      L{err.source_line}
                    </td>
                    <td>
                      {err.node ? (
                        <span
                          className={`ops-badge ${
                            err.node === 'NODE_A' ? 'ops-badge-node-a'
                            : err.node === 'NODE_B' ? 'ops-badge-node-b'
                            : 'ops-badge-node-c'
                          }`}
                        >
                          {err.node}
                        </span>
                      ) : (
                        <span className="ops-badge ops-badge-muted">N/A</span>
                      )}
                    </td>
                    <td>
                      <span
                        className="ops-badge ops-badge-warning font-mono"
                        style={{ fontSize: '0.65rem' }}
                      >
                        {err.reason}
                      </span>
                    </td>
                    <td style={{ maxWidth: '380px' }}>
                      <pre
                        style={{
                          background: 'var(--status-critical-bg)',
                          border: '1px solid var(--status-critical-border)',
                          padding: '3px 7px',
                          borderRadius: 'var(--radius-xs)',
                          color: 'var(--status-critical)',
                          overflowX: 'auto',
                          margin: 0,
                          whiteSpace: 'pre',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.7rem',
                        }}
                      >
                        {err.raw_record || '(blank line)'}
                      </pre>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="btn-ops btn-ops-ghost font-mono"
                        onClick={() => copyToClipboard(err.raw_record || '', idx)}
                        style={{ padding: '2px 6px', fontSize: '0.68rem' }}
                        title="Copy raw record"
                      >
                        {copiedIndex === idx ? (
                          <Check size={11} color="var(--status-nominal)" />
                        ) : (
                          <Copy size={11} />
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
