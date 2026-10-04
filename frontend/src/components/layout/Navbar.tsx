import React from 'react';
import { Activity, RefreshCw, ChevronDown } from 'lucide-react';
import { DatasetInfo, SystemStats } from '../../types';

interface NavbarProps {
  onRunPipeline: () => void;
  isLoading: boolean;
  datasets: DatasetInfo[];
  selectedDataset: string;
  onSelectDataset: (datasetId: string) => void;
  stats?: SystemStats | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  onRunPipeline,
  isLoading,
  datasets,
  selectedDataset,
  onSelectDataset,
  stats,
}) => {
  const totalEvents = stats?.events?.total_events || 0;
  const incidentCount = stats?.incidents?.total || 0;

  return (
    <header
      style={{
        background: 'var(--bg-header)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '0 20px',
        height: 'var(--navbar-height)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        zIndex: 40,
        position: 'sticky',
        top: 0,
        boxShadow: 'var(--shadow-xs)',
      }}
    >
      {/* ── Brand ─────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Monogram mark */}
          <div
            style={{
              width: '30px',
              height: '30px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--text-accent)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              flexShrink: 0,
            }}
          >
            <Activity size={16} strokeWidth={2.2} />
          </div>

          <div style={{ lineHeight: 1 }}>
            <div
              style={{
                fontWeight: 800,
                fontSize: '0.92rem',
                letterSpacing: '-0.025em',
                color: 'var(--text-primary)',
              }}
            >
              PS3{' '}
              <span style={{ color: 'var(--text-accent)', fontWeight: 700 }}>
                Observability
              </span>
            </div>
            <div
              style={{
                fontSize: '0.64rem',
                color: 'var(--text-dim)',
                fontWeight: 500,
                marginTop: '1px',
                letterSpacing: '0.01em',
              }}
            >
              Multi-System Log Analysis & Incident Reconstruction
            </div>
          </div>
        </div>

        {/* Live telemetry pill */}
        {totalEvents > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: '99px',
              border: '1px solid var(--border-subtle)',
              background: 'var(--bg-surface-elevated)',
              marginLeft: '4px',
            }}
          >
            <span className="status-dot online" />
            <span
              className="font-mono"
              style={{ fontSize: '0.67rem', color: 'var(--text-muted)', fontWeight: 600 }}
            >
              {totalEvents.toLocaleString()} records
            </span>
            {incidentCount > 0 && (
              <>
                <span style={{ color: 'var(--border-default)', fontSize: '0.7rem' }}>·</span>
                <span
                  className="font-mono"
                  style={{ fontSize: '0.67rem', color: 'var(--status-critical)', fontWeight: 700 }}
                >
                  {incidentCount} incidents
                </span>
              </>
            )}
          </div>
        )}
      </div>

      {/* ── Right Controls ───────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        {/* Dataset selector */}
        {datasets.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <span
              className="section-label"
              style={{ fontSize: '0.65rem' }}
            >
              Dataset
            </span>
            <select
              value={selectedDataset}
              onChange={(e) => onSelectDataset(e.target.value)}
              className="ops-select font-mono"
              style={{
                fontSize: '0.74rem',
                minWidth: '200px',
                fontWeight: 600,
                maxWidth: '300px',
              }}
              disabled={isLoading}
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.path}>
                  {d.name} ({d.file_count} logs)
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Pipeline trigger */}
        <button
          className="btn-ops btn-ops-primary"
          onClick={onRunPipeline}
          disabled={isLoading}
          style={{ padding: '5px 14px', fontSize: '0.76rem' }}
          title="Re-run full ingestion and deterministic correlation pipeline on active dataset"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
          <span>{isLoading ? 'Processing…' : 'Run Pipeline'}</span>
        </button>
      </div>
    </header>
  );
};
