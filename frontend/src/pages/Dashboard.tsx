import React, { useState } from 'react';
import { SystemStats, Incident } from '../types';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle,
  Database,
  Network,
  Clock,
  ArrowRight,
  Server,
  Layers,
  Search,
  ExternalLink,
  Cpu,
  Activity,
} from 'lucide-react';

interface DashboardProps {
  stats: SystemStats | null;
  incidents: Incident[];
  onSelectIncident: (incidentId: string) => void;
  onNavigate: (view: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  stats,
  incidents,
  onSelectIncident,
  onNavigate,
}) => {
  const [filterKind, setFilterKind] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const totalEvents = stats?.events?.total_events || 0;
  const malformedCount = stats?.events?.ingestion_errors || 0;
  const relCount = stats?.relationships?.total || 0;

  const faultIncidents = incidents.filter((i) => i.kind === 'INCIDENT');
  const candidateIncidents = incidents.filter(
    (i) => i.kind === 'INCIDENT_CANDIDATE' || (i.kind as string) === 'CANDIDATE'
  );
  const normalOps = incidents.filter((i) => i.kind === 'NON_INCIDENT_NORMAL_OPERATION');

  const filteredIncidents = incidents.filter((inc) => {
    if (filterKind === 'INCIDENT' && inc.kind !== 'INCIDENT') return false;
    if (
      filterKind === 'CANDIDATE' &&
      inc.kind !== 'INCIDENT_CANDIDATE' &&
      (inc.kind as string) !== 'CANDIDATE'
    )
      return false;
    if (filterKind === 'NORMAL' && inc.kind !== 'NON_INCIDENT_NORMAL_OPERATION') return false;

    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const match =
        inc.incident_id.toLowerCase().includes(q) ||
        inc.title.toLowerCase().includes(q) ||
        inc.involved_nodes.some((n) => n.toLowerCase().includes(q)) ||
        inc.primary_faults.some((f) => f.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  const getKindBadge = (kind: string) => {
    switch (kind) {
      case 'INCIDENT':
        return <span className="ops-badge ops-badge-critical">INCIDENT CASCADE</span>;
      case 'NON_INCIDENT_NORMAL_OPERATION':
        return <span className="ops-badge ops-badge-routine">ROUTINE OPS</span>;
      default:
        return <span className="ops-badge ops-badge-warning">ANOMALY CANDIDATE</span>;
    }
  };

  const getRecoveryBadge = (status?: string) => {
    switch (status) {
      case 'RECOVERED':
        return <span className="ops-badge ops-badge-nominal">RECOVERED</span>;
      case 'PARTIAL':
        return <span className="ops-badge ops-badge-warning">PARTIAL RECOVERY</span>;
      case 'ONGOING':
        return <span className="ops-badge ops-badge-critical">UNRESOLVED</span>;
      default:
        return <span className="ops-badge ops-badge-muted">N/A</span>;
    }
  };

  return (
    <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Top Status & Metrics Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>
        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Normalized Events
            </span>
            <Database size={14} color="#38bdf8" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
            {totalEvents.toLocaleString()}
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            3 Nodes Ingested
          </div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Fault Cascades
            </span>
            <AlertTriangle size={14} color="#f87171" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: '#f87171' }}>
            {faultIncidents.length}
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Multi-node fault groups
          </div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Anomaly Candidates
            </span>
            <Activity size={14} color="#fbbf24" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: '#fbbf24' }}>
            {candidateIncidents.length}
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Protocol / State deviations
          </div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Graph Relationships
            </span>
            <Network size={14} color="#a855f7" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: '#c084fc' }}>
            {relCount.toLocaleString()}
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Deterministic links
          </div>
        </div>

        <div className="ops-panel" style={{ padding: '12px 14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
              Quarantined Lines
            </span>
            <ShieldAlert size={14} color="#f59e0b" />
          </div>
          <div className="font-mono text-xl" style={{ fontWeight: 700, color: malformedCount > 0 ? '#fbbf24' : '#34d399' }}>
            {malformedCount}
          </div>
          <div className="text-xs text-dim" style={{ marginTop: '2px' }}>
            Parser errors isolated
          </div>
        </div>
      </div>

      {/* Nodes Status Strip */}
      <div className="ops-panel" style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={14} color="var(--text-muted)" />
            <span style={{ fontWeight: 600, fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Distributed Node Telemetry Topology
            </span>
          </div>
          <span className="text-xs text-muted">Synchronous Tri-Node Cluster</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
          {['NODE_A', 'NODE_B', 'NODE_C'].map((node) => {
            const nodeEvts = stats?.events?.by_node?.[node] || 0;
            const badgeClass =
              node === 'NODE_A'
                ? 'ops-badge-node-a'
                : node === 'NODE_B'
                ? 'ops-badge-node-b'
                : 'ops-badge-node-c';
            return (
              <div
                key={node}
                className="ops-panel-subtle"
                style={{ padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className={`ops-badge ${badgeClass}`}>{node}</span>
                  <span className="text-xs text-secondary">
                    {node === 'NODE_A' ? 'Primary Flight / Planner' : node === 'NODE_B' ? 'Navigation & Sensor Hub' : 'Actuation & Guidance Peer'}
                  </span>
                </div>
                <span className="font-mono text-sm" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                  {nodeEvts} evts
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Incident Queue Table */}
      <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="ops-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={15} color="#38bdf8" />
              <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>
                Incident Investigation Queue ({filteredIncidents.length})
              </span>
            </div>

            {/* Filter Tabs */}
            <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-canvas)', padding: '2px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
              {[
                { id: 'ALL', label: `All (${incidents.length})` },
                { id: 'INCIDENT', label: `Cascades (${faultIncidents.length})` },
                { id: 'CANDIDATE', label: `Anomalies (${candidateIncidents.length})` },
                { id: 'NORMAL', label: `Routine (${normalOps.length})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setFilterKind(tab.id)}
                  style={{
                    padding: '2px 8px',
                    fontSize: '0.74rem',
                    borderRadius: 'var(--radius-xs)',
                    border: 'none',
                    background: filterKind === tab.id ? 'var(--bg-surface-elevated)' : 'transparent',
                    color: filterKind === tab.id ? 'var(--text-primary)' : 'var(--text-dim)',
                    fontWeight: filterKind === tab.id ? 600 : 500,
                    cursor: 'pointer',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Search */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={13} style={{ position: 'absolute', left: '8px', color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search incidents, faults, nodes..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="ops-input"
              style={{ paddingLeft: '26px', fontSize: '0.75rem', width: '220px' }}
            />
          </div>
        </div>

        <div style={{ overflowX: 'auto', maxHeight: '550px' }}>
          <table className="ops-table">
            <thead>
              <tr>
                <th style={{ width: '90px' }}>Incident ID</th>
                <th style={{ width: '130px' }}>Classification</th>
                <th>Incident Description & Root Cause</th>
                <th style={{ width: '130px' }}>Nodes</th>
                <th style={{ width: '110px' }}>Primary Faults</th>
                <th style={{ width: '110px' }}>Recovery</th>
                <th style={{ width: '80px', textAlign: 'right' }}>Events</th>
                <th style={{ width: '90px', textAlign: 'center' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
                    No incidents match current filter criteria.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => (
                  <tr
                    key={inc.incident_id}
                    className="ops-table-row"
                    onClick={() => {
                      onSelectIncident(inc.incident_id);
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="font-mono" style={{ fontWeight: 700, color: inc.kind === 'INCIDENT' ? '#f87171' : '#38bdf8' }}>
                      {inc.incident_id}
                    </td>
                    <td>{getKindBadge(inc.kind)}</td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>
                        {inc.title}
                      </div>
                      <div className="text-xs text-muted" style={{ display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {inc.description}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                        {inc.involved_nodes.map((n) => (
                          <span
                            key={n}
                            className={`ops-badge ${
                              n === 'NODE_A' ? 'ops-badge-node-a' : n === 'NODE_B' ? 'ops-badge-node-b' : 'ops-badge-node-c'
                            }`}
                            style={{ fontSize: '0.65rem' }}
                          >
                            {n.replace('NODE_', '')}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="font-mono text-xs">
                      {inc.primary_faults.length > 0 ? (
                        <span style={{ color: '#f87171', fontWeight: 600 }}>{inc.primary_faults.join(', ')}</span>
                      ) : (
                        <span className="text-dim">—</span>
                      )}
                    </td>
                    <td>{getRecoveryBadge(inc.recovery_status)}</td>
                    <td className="font-mono text-xs" style={{ textAlign: 'right', fontWeight: 600 }}>
                      {inc.event_ids.length}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="btn-ops btn-ops-primary"
                        style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectIncident(inc.incident_id);
                        }}
                      >
                        Inspect <ArrowRight size={11} />
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
