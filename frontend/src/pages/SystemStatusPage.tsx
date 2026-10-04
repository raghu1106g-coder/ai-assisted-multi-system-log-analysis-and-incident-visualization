import React, { useState } from 'react';
import { IngestionError, SystemStats, DatasetInfo } from '../types';
import {
  Server,
  Database,
  ShieldAlert,
  AlertTriangle,
  FileCode,
  CheckCircle2,
  Terminal,
  Search,
  Copy,
  Check,
  Filter,
  HardDrive,
  Cpu,
  Layers,
} from 'lucide-react';

interface SystemStatusPageProps {
  stats: SystemStats | null;
  errors: IngestionError[];
  datasets: DatasetInfo[];
  activeDatasetPath: string;
}

export const SystemStatusPage: React.FC<SystemStatusPageProps> = ({
  stats,
  errors,
  datasets,
  activeDatasetPath,
}) => {
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

  const totalEvents = stats?.events?.total_events || 0;
  const incidentCount = stats?.incidents?.total || 0;
  const relCount = stats?.relationships?.total || 0;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        padding: '18px 22px',
        height: 'calc(100vh - var(--navbar-height))',
        overflowY: 'auto',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* Top Banner */}
      <div
        className="ops-panel"
        style={{
          padding: '14px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Database & System Health</div>
          <h1 className="page-title">System Status & Parser Audit</h1>
          <p className="text-xs text-secondary" style={{ marginTop: '3px', maxWidth: '700px' }}>
            Analytical integrity metrics, columnar database row counts, active dataset location, and quarantined malformed line audits.
          </p>
        </div>

        <div className="ops-panel-inset" style={{ padding: '8px 14px', textAlign: 'right' }}>
          <div className="section-label" style={{ marginBottom: '2px' }}>Active Storage File</div>
          <div className="font-mono text-xs text-primary" style={{ fontWeight: 700 }}>
            backend/app/ps3_analysis.db
          </div>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
        <div className="metric-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="metric-card-label">Normalized Events Table</span>
            <Database size={14} color="var(--text-accent)" />
          </div>
          <div className="metric-card-value" style={{ color: 'var(--text-accent)' }}>
            {totalEvents.toLocaleString()} rows
          </div>
          <div className="metric-card-sub">Indexed by timestamp &amp; event_id</div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Causal Relationships
            </span>
            <HardDrive size={15} color="#6d28d9" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: '#6d28d9' }}>
            {relCount.toLocaleString()} edges
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Command-ACK & cascade links
          </div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Reconstructed Incidents
            </span>
            <Layers size={15} color="#dc2626" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: '#dc2626' }}>
            {incidentCount} incidents
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Multi-node causal clusters
          </div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Quarantined Lines
            </span>
            <ShieldAlert size={15} color="#d97706" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: errors.length > 0 ? '#d97706' : '#059669' }}>
            {errors.length} isolated
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Parser boundary quarantine
          </div>
        </div>
      </div>

      {/* Node Distribution Breakdown */}
      <div className="ops-panel" style={{ padding: '14px 18px' }}>
        <div style={{ fontWeight: 700, fontSize: '0.84rem', color: 'var(--text-primary)', marginBottom: '10px' }}>
          Cluster Ingestion Telemetry by Node & Log Family
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          {/* Node Breakdown */}
          <div className="ops-panel-subtle" style={{ padding: '10px 14px' }}>
            <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
              Events by Node
            </div>
            {stats?.events?.by_node &&
              Object.entries(stats.events.by_node).map(([node, count]) => (
                <div key={node} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span className={`ops-badge ${node === 'NODE_A' ? 'ops-badge-node-a' : node === 'NODE_B' ? 'ops-badge-node-b' : 'ops-badge-node-c'}`}>
                    {node}
                  </span>
                  <span className="font-mono text-xs text-primary" style={{ fontWeight: 600 }}>
                    {count.toLocaleString()} events
                  </span>
                </div>
              ))}
          </div>

          {/* Family Breakdown */}
          <div className="ops-panel-subtle" style={{ padding: '10px 14px' }}>
            <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
              Events by Log Family
            </div>
            {stats?.events?.by_family &&
              Object.entries(stats.events.by_family).map(([family, count]) => (
                <div key={family} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span className="ops-badge ops-badge-muted">{family}</span>
                  <span className="font-mono text-xs text-primary" style={{ fontWeight: 600 }}>
                    {count.toLocaleString()} events
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Parser Quarantine Audit Table */}
      <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="ops-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={15} color="#d97706" />
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

        <div style={{ overflowX: 'auto', maxHeight: '400px' }}>
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
                  <td colSpan={6} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
                    No quarantined records matching filter.
                  </td>
                </tr>
              ) : (
                filteredErrors.map((err, idx) => (
                  <tr key={err.id || idx} className="ops-table-row">
                    <td>
                      {err.node ? (
                        <span className={`ops-badge ${err.node === 'NODE_A' ? 'ops-badge-node-a' : err.node === 'NODE_B' ? 'ops-badge-node-b' : 'ops-badge-node-c'}`}>
                          {err.node}
                        </span>
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
                        <span style={{ color: '#0284c7', fontWeight: 700 }}>
                          L{err.source_line}
                        </span>
                      </div>
                    </td>
                    <td style={{ maxWidth: '480px' }}>
                      <pre
                        className="font-mono"
                        style={{
                          background: '#fef2f2',
                          border: '1px solid #fecaca',
                          padding: '4px 8px',
                          borderRadius: 'var(--radius-xs)',
                          fontSize: '0.74rem',
                          color: '#dc2626',
                          overflowX: 'auto',
                          whiteSpace: 'pre',
                          margin: 0,
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
                          <Check size={11} color="#059669" />
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
