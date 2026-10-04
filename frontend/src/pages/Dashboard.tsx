import React, { useState } from 'react';
import { SystemStats, Incident, NormalizedEvent } from '../types';
import {
  Database,
  AlertTriangle,
  Activity,
  Network,
  ShieldAlert,
  CheckCircle,
  ArrowRight,
  Search,
  UploadCloud,
  Layers,
  Server,
  Cpu,
  Radio,
  Clock,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';

interface DashboardProps {
  stats: SystemStats | null;
  incidents: Incident[];
  events?: NormalizedEvent[];
  onSelectIncident: (incidentId: string) => void;
  onNavigate: (view: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  stats,
  incidents,
  events = [],
  onSelectIncident,
  onNavigate,
}) => {
  const [filterKind, setFilterKind] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const totalEvents   = stats?.events?.total_events || 0;
  const malformedCount = stats?.events?.ingestion_errors || 0;
  const relCount       = stats?.relationships?.total || 0;

  const faultIncidents     = incidents.filter((i) => i.kind === 'INCIDENT');
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
        return <span className="ops-badge ops-badge-critical">CASCADE</span>;
      case 'NON_INCIDENT_NORMAL_OPERATION':
        return <span className="ops-badge ops-badge-routine">ROUTINE</span>;
      default:
        return <span className="ops-badge ops-badge-warning">ANOMALY</span>;
    }
  };

  const getRecoveryBadge = (status?: string) => {
    switch (status) {
      case 'RECOVERED':
        return <span className="ops-badge ops-badge-nominal">RECOVERED</span>;
      case 'PARTIAL':
        return <span className="ops-badge ops-badge-warning">PARTIAL</span>;
      case 'ONGOING':
        return <span className="ops-badge ops-badge-critical">UNRESOLVED</span>;
      default:
        return <span className="ops-badge ops-badge-muted">N/A</span>;
    }
  };

  // Empty-state CTA
  if (totalEvents === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px',
          gap: '20px',
          background: 'var(--bg-canvas)',
        }}
      >
        <div
          style={{
            width: '60px',
            height: '60px',
            borderRadius: 'var(--radius-md)',
            background: 'var(--status-info-bg)',
            border: '1px solid var(--status-info-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Database size={28} color="var(--status-info)" />
        </div>
        <div style={{ textAlign: 'center', maxWidth: '460px' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
            No dataset loaded
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Import a multi-node log dataset to begin analysis. The pipeline will parse, validate,
            normalize, correlate, and reconstruct incidents automatically.
          </p>
        </div>
        <button
          className="btn-ops btn-ops-primary"
          onClick={() => onNavigate('import')}
          style={{ padding: '7px 18px', fontSize: '0.82rem' }}
        >
          <UploadCloud size={15} />
          <span>Import Log Dataset</span>
        </button>
      </div>
    );
  }

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
      {/* ------------------------------------------------------------------ */}
      {/* PAGE HEADER                                                         */}
      {/* ------------------------------------------------------------------ */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Level 1 Overview</div>
          <h1 className="page-title">System Analysis Dashboard</h1>
        </div>
        <button
          className="btn-ops btn-ops-secondary"
          onClick={() => onNavigate('import')}
          style={{ fontSize: '0.74rem' }}
        >
          <UploadCloud size={13} />
          <span>Import New Dataset</span>
        </button>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* KPI METRICS STRIP                                                   */}
      {/* ------------------------------------------------------------------ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px' }}>

        <div className="metric-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="metric-card-label">Normalized Records</span>
            <Database size={14} color="var(--text-accent)" />
          </div>
          <div className="metric-card-value" style={{ color: 'var(--text-primary)' }}>
            {totalEvents.toLocaleString()}
          </div>
          <div className="metric-card-sub">Valid parsed events</div>
        </div>

        <div className="metric-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="metric-card-label">Fault Cascades</span>
            <AlertTriangle size={14} color="var(--status-critical)" />
          </div>
          <div className="metric-card-value" style={{ color: 'var(--status-critical)' }}>
            {faultIncidents.length}
          </div>
          <div className="metric-card-sub">Multi-node incidents</div>
        </div>

        <div className="metric-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="metric-card-label">Anomaly Candidates</span>
            <Activity size={14} color="var(--status-warning)" />
          </div>
          <div className="metric-card-value" style={{ color: 'var(--status-warning)' }}>
            {candidateIncidents.length}
          </div>
          <div className="metric-card-sub">Protocol anomalies</div>
        </div>

        <div className="metric-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="metric-card-label">Causal Graph Links</span>
            <Network size={14} color="var(--node-b-color)" />
          </div>
          <div className="metric-card-value" style={{ color: 'var(--node-b-color)' }}>
            {relCount.toLocaleString()}
          </div>
          <div className="metric-card-sub">Deterministic relations</div>
        </div>

        <div className="metric-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span className="metric-card-label">Quarantined Lines</span>
            <ShieldAlert size={14} color={malformedCount > 0 ? 'var(--status-warning)' : 'var(--status-nominal)'} />
          </div>
          <div
            className="metric-card-value"
            style={{ color: malformedCount > 0 ? 'var(--status-warning)' : 'var(--status-nominal)' }}
          >
            {malformedCount}
          </div>
          <div className="metric-card-sub">Parser errors isolated</div>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* DISTRIBUTED NODE TELEMETRY MATRIX                                   */}
      {/* ------------------------------------------------------------------ */}
      <div className="ops-panel" style={{ padding: '16px 20px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '14px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Server size={15} color="var(--text-accent)" />
            <span className="panel-title">Distributed Node Telemetry &amp; System Health</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <span className="text-xs text-muted">
              Synchronous 3-node cluster state
            </span>
            <span className="ops-badge ops-badge-nominal" style={{ fontSize: '0.65rem' }}>
              <span className="ops-pulse-dot ops-pulse-dot-nominal" />
              CLUSTER ACTIVE
            </span>
          </div>
        </div>

        {/* 3 Node Cards Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '14px',
          }}
        >
          {(['NODE_A', 'NODE_B', 'NODE_C'] as const).map((nodeId) => {
            const nodeEvents = events.filter((e) => e.node === nodeId);
            const count = nodeEvents.length || (stats?.events?.by_node?.[nodeId] || 0);
            const pct = totalEvents > 0 ? Math.round((count / totalEvents) * 100) : 0;

            const badgeClass =
              nodeId === 'NODE_A' ? 'ops-badge-node-a'
              : nodeId === 'NODE_B' ? 'ops-badge-node-b'
              : 'ops-badge-node-c';

            const barColor =
              nodeId === 'NODE_A' ? 'var(--node-a-color)'
              : nodeId === 'NODE_B' ? 'var(--node-b-color)'
              : 'var(--node-c-color)';

            const role =
              nodeId === 'NODE_A' ? 'Flight Guidance & Operator Ingest'
              : nodeId === 'NODE_B' ? 'Inter-Node Planning & Sync'
              : 'Actuation & State Telemetry';

            // Extract faults and criticals for this node
            const criticals = nodeEvents.filter(
              (e) => e.severity === 'CRITICAL' || e.event_type.startsWith('FLT') || e.attributes?.fault_code
            );
            const warnings = nodeEvents.filter((e) => e.severity === 'WARNING');

            const faultCodes = Array.from(
              new Set(
                nodeEvents
                  .map((e) => e.attributes?.fault_code || (e.event_type.startsWith('FLT') ? e.event_type : null))
                  .filter(Boolean)
              )
            ) as string[];

            // Extract unique active components
            const components = Array.from(
              new Set(nodeEvents.map((e) => e.component).filter(Boolean))
            ).slice(0, 4) as string[];

            // Extract log families on this node
            const nodeFamilies: { [k: string]: number } = {};
            nodeEvents.forEach((e) => {
              if (e.log_family) {
                nodeFamilies[e.log_family] = (nodeFamilies[e.log_family] || 0) + 1;
              }
            });

            // Timestamps
            const timestamps = nodeEvents.map((e) => e.timestamp).filter(Boolean).sort();
            const timeSpan =
              timestamps.length >= 2
                ? `${timestamps[0].slice(11, 19)} → ${timestamps[timestamps.length - 1].slice(11, 19)}`
                : undefined;

            const isDegraded = criticals.length > 0 || faultCodes.length > 0;

            return (
              <div
                key={nodeId}
                className="ops-panel-inset"
                style={{
                  padding: '14px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  border: isDegraded ? '1px solid var(--status-critical-border)' : '1px solid var(--border-subtle)',
                  background: isDegraded ? 'rgba(239, 68, 68, 0.02)' : 'var(--bg-surface-elevated)',
                }}
              >
                {/* Node Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className={`ops-badge ${badgeClass}`} style={{ fontSize: '0.74rem', fontWeight: 800 }}>
                        {nodeId}
                      </span>
                      {isDegraded ? (
                        <span className="ops-badge ops-badge-critical" style={{ fontSize: '0.62rem' }}>
                          <span className="ops-pulse-dot ops-pulse-dot-critical" />
                          FAULTS ({faultCodes.length || criticals.length})
                        </span>
                      ) : (
                        <span className="ops-badge ops-badge-nominal" style={{ fontSize: '0.62rem' }}>
                          <span className="ops-pulse-dot ops-pulse-dot-nominal" />
                          NOMINAL
                        </span>
                      )}
                    </div>
                    <div className="text-2xs text-muted" style={{ marginTop: '4px', fontWeight: 500 }}>
                      {role}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <span className="font-mono" style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      {count.toLocaleString()}
                    </span>
                    <div className="text-2xs text-dim">events ({pct}%)</div>
                  </div>
                </div>

                {/* Progress load bar */}
                <div>
                  <div
                    style={{
                      height: '4px',
                      borderRadius: '99px',
                      background: 'var(--border-subtle)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${pct}%`,
                        background: barColor,
                        borderRadius: '99px',
                        transition: 'width 0.4s ease',
                      }}
                    />
                  </div>
                </div>

                {/* Node Metric Indicators Strip */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '6px',
                    padding: '8px',
                    background: 'var(--bg-canvas)',
                    borderRadius: 'var(--radius-xs)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div className="text-2xs text-dim">Active Faults</div>
                    <div
                      className="font-mono"
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: faultCodes.length > 0 ? 'var(--status-critical)' : 'var(--status-nominal)',
                      }}
                    >
                      {faultCodes.length > 0 ? `${faultCodes.length} codes` : '0 clean'}
                    </div>
                  </div>
                  <div>
                    <div className="text-2xs text-dim">Components</div>
                    <div className="font-mono" style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {components.length || '3'} active
                    </div>
                  </div>
                  <div>
                    <div className="text-2xs text-dim">Warnings</div>
                    <div
                      className="font-mono"
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: warnings.length > 0 ? 'var(--status-warning)' : 'var(--text-muted)',
                      }}
                    >
                      {warnings.length}
                    </div>
                  </div>
                </div>

                {/* Log Families Breakdown on this Node */}
                <div>
                  <div className="text-2xs text-dim" style={{ marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Log Families &amp; Streams
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {Object.keys(nodeFamilies).length > 0 ? (
                      Object.entries(nodeFamilies).map(([fam, cnt]) => (
                        <span
                          key={fam}
                          className="font-mono"
                          style={{
                            fontSize: '0.64rem',
                            padding: '2px 6px',
                            borderRadius: 'var(--radius-xs)',
                            background: 'var(--bg-surface)',
                            border: '1px solid var(--border-default)',
                            color: 'var(--text-secondary)',
                            fontWeight: 600,
                          }}
                        >
                          {fam}: <strong style={{ color: 'var(--text-primary)' }}>{cnt}</strong>
                        </span>
                      ))
                    ) : (
                      <span className="text-2xs text-muted">Awaiting stream ingestion</span>
                    )}
                  </div>
                </div>

                {/* Active Fault Codes or Components */}
                {faultCodes.length > 0 ? (
                  <div>
                    <div className="text-2xs text-dim" style={{ marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Primary Fault Signatures
                    </div>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {faultCodes.map((fc) => (
                        <span key={fc} className="ops-badge ops-badge-critical font-mono" style={{ fontSize: '0.65rem' }}>
                          {fc}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="text-2xs text-dim" style={{ marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      Active Components
                    </div>
                    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {(components.length > 0 ? components : ['EXEC_CORE', 'BUS_MON']).map((comp) => (
                        <span
                          key={comp}
                          className="font-mono"
                          style={{
                            fontSize: '0.62rem',
                            padding: '1px 5px',
                            borderRadius: 'var(--radius-xs)',
                            background: 'var(--bg-surface)',
                            border: '1px solid var(--border-subtle)',
                            color: 'var(--text-muted)',
                          }}
                        >
                          {comp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Footer time range */}
                {timeSpan && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      paddingTop: '6px',
                      borderTop: '1px solid var(--border-subtle)',
                      marginTop: 'auto',
                    }}
                  >
                    <Clock size={11} color="var(--text-dim)" />
                    <span className="font-mono text-2xs text-dim">
                      Obs. Window: {timeSpan} UTC
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Cluster-Wide Log Family & Stream Distribution Strip */}
        {Object.keys(stats?.events?.by_family || {}).length > 0 && (
          <div
            style={{
              marginTop: '12px',
              padding: '10px 14px',
              background: 'var(--bg-surface-elevated)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '10px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Activity size={13} color="var(--text-accent)" />
              <span className="text-xs" style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                Cluster Log Streams:
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              {Object.entries(stats?.events?.by_family || {}).map(([fam, cnt]) => (
                <div
                  key={fam}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '3px 8px',
                    borderRadius: 'var(--radius-xs)',
                    background: 'var(--bg-canvas)',
                    border: '1px solid var(--border-default)',
                  }}
                >
                  <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {fam}
                  </span>
                  <span
                    className="font-mono text-xs"
                    style={{
                      fontWeight: 800,
                      color: 'var(--text-accent)',
                      background: 'rgba(3, 105, 161, 0.08)',
                      padding: '1px 5px',
                      borderRadius: 'var(--radius-xs)',
                    }}
                  >
                    {(cnt as number).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* INCIDENT INVESTIGATION QUEUE — FULL WIDTH                           */}
      {/* ------------------------------------------------------------------ */}
      <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
        {/* Queue header */}
        <div className="ops-panel-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <Layers size={14} color="var(--text-accent)" />
              <span className="panel-title">
                Incident Queue
              </span>
              <span
                className="font-mono"
                style={{
                  fontSize: '0.67rem',
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-xs)',
                  background: 'var(--bg-surface-elevated)',
                  color: 'var(--text-muted)',
                  fontWeight: 700,
                }}
              >
                {filteredIncidents.length}
              </span>
            </div>

            {/* Filter tabs */}
            <div className="ops-tab-bar">
              {[
                { id: 'ALL',       label: `All (${incidents.length})` },
                { id: 'INCIDENT',  label: `Cascades (${faultIncidents.length})` },
                { id: 'CANDIDATE', label: `Anomalies (${candidateIncidents.length})` },
                { id: 'NORMAL',    label: `Routine (${normalOps.length})` },
              ].map((tab) => (
                <button
                  key={tab.id}
                  className={`ops-tab${filterKind === tab.id ? ' active' : ''}`}
                  onClick={() => setFilterKind(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Quick search */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search
              size={12}
              style={{ position: 'absolute', left: '8px', color: 'var(--text-dim)', pointerEvents: 'none' }}
            />
            <input
              type="text"
              placeholder="Search incidents, faults, nodes…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="ops-input"
              style={{ paddingLeft: '26px', fontSize: '0.74rem', width: '220px' }}
            />
          </div>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto', flex: 1 }}>
          <table className="ops-table">
            <thead>
              <tr>
                <th style={{ width: '100px' }}>ID</th>
                <th style={{ width: '120px' }}>Classification</th>
                <th>Incident & Root Cause</th>
                <th style={{ width: '120px' }}>Nodes</th>
                <th style={{ width: '120px' }}>Primary Faults</th>
                <th style={{ width: '100px' }}>Recovery</th>
                <th style={{ width: '70px', textAlign: 'right' }}>Events</th>
                <th style={{ width: '90px', textAlign: 'center' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-dim)' }}
                  >
                    No incidents match current filter criteria.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => (
                  <tr
                    key={inc.incident_id}
                    className="ops-table-row"
                    onClick={() => onSelectIncident(inc.incident_id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td
                      className="font-mono"
                      style={{
                        fontWeight: 700,
                        fontSize: '0.74rem',
                        color: inc.kind === 'INCIDENT' ? 'var(--status-critical)' : 'var(--text-accent)',
                      }}
                    >
                      {inc.incident_id}
                    </td>
                    <td>{getKindBadge(inc.kind)}</td>
                    <td>
                      <div
                        style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.78rem', marginBottom: '1px' }}
                      >
                        {inc.title}
                      </div>
                      <div
                        className="text-xs text-muted"
                        style={{
                          display: '-webkit-box',
                          WebkitLineClamp: 1,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {inc.description}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                        {inc.involved_nodes.map((n) => (
                          <span
                            key={n}
                            className={`ops-badge ${
                              n === 'NODE_A' ? 'ops-badge-node-a'
                              : n === 'NODE_B' ? 'ops-badge-node-b'
                              : 'ops-badge-node-c'
                            }`}
                          >
                            {n.replace('NODE_', '')}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="font-mono" style={{ fontSize: '0.72rem' }}>
                      {inc.primary_faults.length > 0 ? (
                        <span style={{ color: 'var(--status-critical)', fontWeight: 700 }}>
                          {inc.primary_faults.join(', ')}
                        </span>
                      ) : (
                        <span className="text-dim">—</span>
                      )}
                    </td>
                    <td>{getRecoveryBadge(inc.recovery_status)}</td>
                    <td
                      className="font-mono text-xs"
                      style={{ textAlign: 'right', fontWeight: 700, color: 'var(--text-primary)' }}
                    >
                      {inc.event_ids.length}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="btn-ops btn-ops-primary"
                        style={{ padding: '3px 8px', fontSize: '0.7rem' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectIncident(inc.incident_id);
                        }}
                      >
                        Inspect <ArrowRight size={10} />
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
