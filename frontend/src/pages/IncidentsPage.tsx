import React, { useState } from 'react';
import { Incident, NormalizedEvent, EventRelationship, Evidence } from '../types';
import { IncidentTimeline } from '../components/timeline/IncidentTimeline';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';
import { AINarrativePanel } from '../components/narrative/AINarrativePanel';
import {
  Clock,
  FileText,
  ShieldAlert,
  Search,
  Layers,
  Sparkles,
} from 'lucide-react';

interface IncidentsPageProps {
  incidents: Incident[];
  selectedIncident: Incident | null;
  onSelectIncident: (incident: Incident) => void;
  events: NormalizedEvent[];
  relationships: EventRelationship[];
  selectedEvent: NormalizedEvent | null;
  selectedEvidence: Evidence[];
  onSelectEvent: (event: NormalizedEvent) => void;
  onSelectEventById: (id: string) => void;
}

export const IncidentsPage: React.FC<IncidentsPageProps> = ({
  incidents,
  selectedIncident,
  onSelectIncident,
  events,
  relationships,
  selectedEvent,
  selectedEvidence,
  onSelectEvent,
  onSelectEventById,
}) => {
  const [activeTab, setActiveTab] = useState<'timeline' | 'narrative'>('timeline');
  const [searchIncident, setSearchIncident] = useState<string>('');
  const [kindFilter, setKindFilter] = useState<string>('ALL');

  const filteredIncidents = incidents.filter((inc) => {
    if (kindFilter === 'INCIDENT' && inc.kind !== 'INCIDENT') return false;
    if (
      kindFilter === 'CANDIDATE' &&
      inc.kind !== 'INCIDENT_CANDIDATE' &&
      (inc.kind as string) !== 'CANDIDATE'
    )
      return false;
    if (kindFilter === 'NORMAL' && inc.kind !== 'NON_INCIDENT_NORMAL_OPERATION') return false;

    if (searchIncident) {
      const q = searchIncident.toLowerCase();
      const match =
        inc.incident_id.toLowerCase().includes(q) ||
        inc.title.toLowerCase().includes(q) ||
        inc.involved_nodes.some((n) => n.toLowerCase().includes(q)) ||
        inc.primary_faults.some((f) => f.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  const incidentEvents = selectedIncident
    ? events.filter((e) => selectedIncident.event_ids.includes(e.event_id))
    : events;

  const nodeEventCounts: Record<string, number> = {};
  incidentEvents.forEach((e) => {
    nodeEventCounts[e.node] = (nodeEventCounts[e.node] || 0) + 1;
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

  const faultCount     = incidents.filter((i) => i.kind === 'INCIDENT').length;
  const candidateCount = incidents.filter(
    (i) => i.kind === 'INCIDENT_CANDIDATE' || (i.kind as string) === 'CANDIDATE'
  ).length;
  const normalCount = incidents.filter((i) => i.kind === 'NON_INCIDENT_NORMAL_OPERATION').length;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '280px 1fr 360px',
        gap: '12px',
        padding: '14px 18px',
        height: 'calc(100vh - var(--navbar-height))',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* ----------------------------------------------------------------- */}
      {/* LEFT: Incident Queue                                                */}
      {/* ----------------------------------------------------------------- */}
      <div
        className="ops-panel"
        style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}
      >
        {/* Queue header */}
        <div
          style={{
            padding: '10px 12px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={13} color="var(--text-accent)" />
              <span className="panel-title">Incident Queue</span>
              <span
                className="font-mono"
                style={{
                  fontSize: '0.62rem',
                  padding: '1px 5px',
                  borderRadius: 'var(--radius-xs)',
                  background: 'var(--bg-surface-elevated)',
                  color: 'var(--text-muted)',
                  fontWeight: 700,
                }}
              >
                {filteredIncidents.length}
              </span>
            </div>
          </div>

          {/* Search */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search
              size={11}
              style={{ position: 'absolute', left: '7px', color: 'var(--text-dim)', pointerEvents: 'none' }}
            />
            <input
              type="text"
              placeholder="Search incidents, faults…"
              value={searchIncident}
              onChange={(e) => setSearchIncident(e.target.value)}
              className="ops-input"
              style={{ paddingLeft: '22px', fontSize: '0.72rem', width: '100%' }}
            />
          </div>

          {/* Filter pills */}
          <div className="ops-tab-bar">
            {[
              { id: 'ALL',       label: `All (${incidents.length})` },
              { id: 'INCIDENT',  label: `Cascades (${faultCount})` },
              { id: 'CANDIDATE', label: `Anomalies (${candidateCount})` },
              { id: 'NORMAL',    label: `Routine (${normalCount})` },
            ].map((f) => (
              <button
                key={f.id}
                className={`ops-tab${kindFilter === f.id ? ' active' : ''}`}
                onClick={() => setKindFilter(f.id)}
                style={{ flex: 1, textAlign: 'center', padding: '3px 2px', fontSize: '0.64rem' }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Incident list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
          {filteredIncidents.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '30px 10px',
                color: 'var(--text-dim)',
                fontSize: '0.78rem',
              }}
            >
              No matching incidents.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {filteredIncidents.map((inc) => {
                const isSelected   = selectedIncident?.incident_id === inc.incident_id;
                const isFault      = inc.kind === 'INCIDENT';

                return (
                  <div
                    key={inc.incident_id}
                    className={`incident-card${isFault ? ' fault' : ''}${isSelected ? ' selected' : ''}`}
                    onClick={() => onSelectIncident(inc)}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '3px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <span
                          className="font-mono"
                          style={{
                            fontSize: '0.67rem',
                            fontWeight: 800,
                            color: isFault ? 'var(--status-critical)' : 'var(--text-accent)',
                          }}
                        >
                          {inc.incident_id}
                        </span>
                        {getKindBadge(inc.kind)}
                      </div>
                      <span className="font-mono text-2xs text-dim">
                        {inc.event_ids.length} evts
                      </span>
                    </div>

                    <div
                      style={{
                        fontSize: '0.74rem',
                        fontWeight: isSelected ? 600 : 500,
                        color: 'var(--text-primary)',
                        lineHeight: 1.35,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                        marginBottom: '4px',
                      }}
                    >
                      {inc.title}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', gap: '3px' }}>
                        {inc.involved_nodes.map((n) => (
                          <span
                            key={n}
                            className={`ops-badge ${
                              n === 'NODE_A' ? 'ops-badge-node-a'
                              : n === 'NODE_B' ? 'ops-badge-node-b'
                              : 'ops-badge-node-c'
                            }`}
                            style={{ fontSize: '0.6rem' }}
                          >
                            {n.replace('NODE_', '')}
                          </span>
                        ))}
                      </div>
                      {inc.primary_faults.length > 0 && (
                        <span
                          className="font-mono"
                          style={{
                            fontSize: '0.62rem',
                            color: 'var(--status-critical)',
                            fontWeight: 700,
                          }}
                        >
                          {inc.primary_faults[0]}
                          {inc.primary_faults.length > 1 && ` +${inc.primary_faults.length - 1}`}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* CENTER: Incident Workbench                                          */}
      {/* ----------------------------------------------------------------- */}
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: '10px', height: '100%', overflow: 'hidden' }}
      >
        {selectedIncident ? (
          <>
            {/* Incident summary header */}
            <div className="ops-panel" style={{ padding: '13px 16px', flexShrink: 0 }}>
              <div
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '4px' }}>
                    <span
                      className="font-mono"
                      style={{
                        fontSize: '0.8rem',
                        fontWeight: 800,
                        color:
                          selectedIncident.kind === 'INCIDENT'
                            ? 'var(--status-critical)'
                            : 'var(--text-accent)',
                      }}
                    >
                      {selectedIncident.incident_id}
                    </span>
                    {getKindBadge(selectedIncident.kind)}
                    {selectedIncident.recovery_status && (
                      <span
                        className={`ops-badge ${
                          selectedIncident.recovery_status === 'RECOVERED'
                            ? 'ops-badge-nominal'
                            : selectedIncident.recovery_status === 'ONGOING'
                            ? 'ops-badge-critical'
                            : 'ops-badge-warning'
                        }`}
                      >
                        {selectedIncident.recovery_status}
                      </span>
                    )}
                  </div>
                  <h2
                    style={{
                      fontSize: '0.95rem',
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      marginBottom: '3px',
                      lineHeight: 1.3,
                    }}
                  >
                    {selectedIncident.title}
                  </h2>
                  <p
                    className="text-xs text-secondary"
                    style={{ lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
                  >
                    {selectedIncident.description}
                  </p>
                </div>

                {/* Node participation widget */}
                <div
                  className="ops-panel-inset"
                  style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}
                >
                  {Object.entries(nodeEventCounts).map(([node, count], i, arr) => {
                    const badgeClass =
                      node === 'NODE_A' ? 'ops-badge-node-a'
                      : node === 'NODE_B' ? 'ops-badge-node-b'
                      : 'ops-badge-node-c';
                    return (
                      <React.Fragment key={node}>
                        <div style={{ textAlign: 'center' }}>
                          <span className={`ops-badge ${badgeClass}`}>{node.replace('NODE_', 'N')}</span>
                          <div className="font-mono text-2xs text-muted" style={{ marginTop: '2px' }}>
                            {count} evts
                          </div>
                        </div>
                        {i < arr.length - 1 && (
                          <span style={{ color: 'var(--border-default)', fontSize: '0.8rem' }}>⟷</span>
                        )}
                      </React.Fragment>
                    );
                  })}
                  {Object.keys(nodeEventCounts).length === 0 && (
                    <span className="text-xs text-dim">No events</span>
                  )}
                </div>
              </div>

              {/* View switcher */}
              <div
                style={{
                  display: 'flex',
                  gap: '6px',
                  marginTop: '10px',
                  paddingTop: '10px',
                  borderTop: '1px solid var(--border-subtle)',
                }}
              >
                <button
                  className={`btn-ops ${activeTab === 'timeline' ? 'btn-ops-primary' : 'btn-ops-secondary'}`}
                  onClick={() => setActiveTab('timeline')}
                  style={{ padding: '4px 12px', fontSize: '0.74rem' }}
                >
                  <Clock size={12} />
                  <span>Event Timeline ({incidentEvents.length})</span>
                </button>
                <button
                  className={`btn-ops ${activeTab === 'narrative' ? 'btn-ops-primary' : 'btn-ops-secondary'}`}
                  onClick={() => setActiveTab('narrative')}
                  style={{ padding: '4px 12px', fontSize: '0.74rem' }}
                >
                  <Sparkles size={12} />
                  <span>AI Incident Report</span>
                </button>
              </div>
            </div>

            {/* Center panel body */}
            <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
              {activeTab === 'timeline' ? (
                <IncidentTimeline
                  events={incidentEvents}
                  selectedEventId={selectedEvent?.event_id || null}
                  onSelectEvent={onSelectEvent}
                />
              ) : (
                <AINarrativePanel
                  incident={selectedIncident}
                  onSelectEventById={onSelectEventById}
                />
              )}
            </div>
          </>
        ) : (
          /* Empty selection state */
          <div
            className="ops-panel"
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <ShieldAlert size={28} color="var(--text-dim)" />
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                Select an incident
              </div>
              <div className="text-xs text-muted">
                Choose an incident from the queue to begin investigation.
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* RIGHT: Evidence Inspector (L3 + L4)                                */}
      {/* ----------------------------------------------------------------- */}
      <div style={{ height: '100%', minHeight: 0, overflow: 'hidden' }}>
        <EvidenceInspector
          event={selectedEvent}
          evidence={selectedEvidence}
          relationships={relationships.filter(
            (r) =>
              selectedEvent &&
              (r.source_event_id === selectedEvent.event_id ||
                r.target_event_id === selectedEvent.event_id)
          )}
          onSelectEventId={onSelectEventById}
        />
      </div>
    </div>
  );
};
