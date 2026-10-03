import React, { useState } from 'react';
import { IngestionError } from '../types';
import {
  ShieldAlert,
  AlertTriangle,
  FileCode,
  CheckCircle2,
  Terminal,
  Search,
  Copy,
  Check,
  Filter,
} from 'lucide-react';

interface ErrorsPageProps {
  errors: IngestionError[];
}

export const ErrorsPage: React.FC<ErrorsPageProps> = ({ errors }) => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<string>('ALL');
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyToClipboard = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 1500);
  };

  const filteredErrors = errors.filter((err) => {
    if (selectedNode !== 'ALL' && err.node !== selectedNode) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const match =
        (err.reason && err.reason.toLowerCase().includes(q)) ||
        (err.source_file && err.source_file.toLowerCase().includes(q)) ||
        (err.raw_record && err.raw_record.toLowerCase().includes(q)) ||
        String(err.source_line).includes(q);
      if (!match) return false;
    }
    return true;
  });

  const getNodeBadgeClass = (node?: string) => {
    if (node === 'NODE_A') return 'ops-badge-node-a';
    if (node === 'NODE_B') return 'ops-badge-node-b';
    if (node === 'NODE_C') return 'ops-badge-node-c';
    return 'ops-badge-info';
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '16px 20px',
        height: 'calc(100vh - 46px)',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* Top Banner */}
      <div
        className="ops-panel"
        style={{
          padding: '14px 18px',
          borderLeft: '4px solid #f59e0b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span className="ops-badge ops-badge-warning">PARSER QUARANTINE LOG</span>
            <span className="text-xs text-muted">
              Total Isolated Records: {errors.length}
            </span>
          </div>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            Malformed Line Isolation & Analytical Integrity Quarantine
          </h2>
          <p className="text-xs text-secondary" style={{ marginTop: '2px', maxWidth: '820px' }}>
            To safeguard downstream causal graphs and deterministic incident models, corrupted lines (unterminated quotes, missing timestamps, bad delimiters) are caught at ingestion boundaries and isolated with exact physical file coordinates.
          </p>
        </div>

        <div
          className="ops-panel-subtle"
          style={{
            padding: '8px 14px',
            textAlign: 'right',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
          }}
        >
          <span className="text-xs text-dim" style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Quarantine Integrity
          </span>
          <span className="font-mono text-sm" style={{ fontWeight: 700, color: '#fbbf24' }}>
            {errors.length} Lines Isolated
          </span>
        </div>
      </div>

      {/* Main Table Panel */}
      <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {/* Table Header & Search/Filter Controls */}
        <div className="ops-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={15} color="#f59e0b" />
            <span style={{ fontWeight: 700, fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Quarantined Records Audit ({filteredErrors.length})
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <Search size={12} style={{ position: 'absolute', left: '7px', color: 'var(--text-dim)' }} />
              <input
                type="text"
                placeholder="Search error reason, file, line..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="ops-input"
                style={{ paddingLeft: '24px', fontSize: '0.74rem', width: '220px' }}
              />
            </div>

            <select
              value={selectedNode}
              onChange={(e) => setSelectedNode(e.target.value)}
              className="ops-select"
              style={{ fontSize: '0.74rem' }}
            >
              <option value="ALL">All Nodes</option>
              <option value="NODE_A">NODE_A</option>
              <option value="NODE_B">NODE_B</option>
              <option value="NODE_C">NODE_C</option>
            </select>
          </div>
        </div>

        {/* Scrollable Table Content */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <table className="ops-table">
            <thead>
              <tr>
                <th style={{ width: '90px' }}>Node</th>
                <th style={{ width: '130px' }}>Log Family</th>
                <th style={{ width: '220px' }}>Failure Reason</th>
                <th style={{ width: '220px' }}>Physical Source Coordinates</th>
                <th>Raw Corrupted Line Content</th>
                <th style={{ width: '70px', textAlign: 'center' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredErrors.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                    No quarantined records matching filter.
                  </td>
                </tr>
              ) : (
                filteredErrors.map((err, idx) => (
                  <tr key={err.id || idx} className="ops-table-row">
                    <td>
                      {err.node ? (
                        <span className={`ops-badge ${getNodeBadgeClass(err.node)}`}>{err.node}</span>
                      ) : (
                        <span className="ops-badge ops-badge-muted">GLOBAL</span>
                      )}
                    </td>
                    <td>
                      {err.log_family ? (
                        <span className="ops-badge ops-badge-muted">{err.log_family}</span>
                      ) : (
                        <span className="text-dim">—</span>
                      )}
                    </td>
                    <td>
                      <span className="ops-badge ops-badge-warning font-mono" style={{ fontSize: '0.7rem' }}>
                        {err.reason}
                      </span>
                    </td>
                    <td className="font-mono text-xs">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <FileCode size={12} color="var(--text-dim)" />
                        <span style={{ color: 'var(--text-muted)' }}>
                          {err.source_file.split('/').slice(-2).join('/')}:
                        </span>
                        <span style={{ color: '#38bdf8', fontWeight: 700 }}>
                          L{err.source_line}
                        </span>
                      </div>
                    </td>
                    <td style={{ maxWidth: '480px' }}>
                      <pre
                        className="font-mono"
                        style={{
                          background: '#060a14',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          padding: '4px 8px',
                          borderRadius: 'var(--radius-xs)',
                          fontSize: '0.74rem',
                          color: '#f87171',
                          overflowX: 'auto',
                          whiteSpace: 'pre',
                        }}
                      >
                        {err.raw_record || '(blank or null record)'}
                      </pre>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="btn-ops btn-ops-ghost font-mono text-xs"
                        onClick={() => copyToClipboard(err.raw_record || '', idx)}
                        style={{ padding: '2px 6px', fontSize: '0.68rem' }}
                        title="Copy raw record"
                      >
                        {copiedIndex === idx ? (
                          <Check size={11} color="#34d399" />
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
