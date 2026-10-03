import React, { useState } from 'react';
import { Incident, NormalizedEvent, EventRelationship, Evidence } from '../types';
import { IncidentTimeline } from '../components/timeline/IncidentTimeline';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';
import { AINarrativePanel } from '../components/narrative/AINarrativePanel';
import {
  Cpu,
  Clock,
  FileText,
  ShieldAlert,
  Search,
  Filter,
  ArrowRight,
  Server,
  Activity,
  Layers,
  Sparkles,
  ChevronRight,
  Radio,
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

  // Events belonging to selected incident
  const incidentEvents = selectedIncident
    ? events.filter((e) => selectedIncident.event_ids.includes(e.event_id))
    : events;

  // Node event counts within selected incident for topology visualizer
  const nodeEventCounts: Record<string, number> = {
    NODE_A: incidentEvents.filter((e) => e.node === 'NODE_A').length,
    NODE_B: incidentEvents.filter((e) => e.node === 'NODE_B').length,
    NODE_C: incidentEvents.filter((e) => e.node === 'NODE_C').length,
  };

  const getKindBadge = (kind: string) => {
    switch (kind) {
      case 'INCIDENT':
        return <span className="ops-badge ops-badge-critical" style={{ fontSize: '0.65rem' }}>CASCADE</span>;
      case 'NON_INCIDENT_NORMAL_OPERATION':
        return <span className="ops-badge ops-badge-routine" style={{ fontSize: '0.65rem' }}>ROUTINE</span>;
      default:
        return <span className="ops-badge ops-badge-warning" style={{ fontSize: '0.65rem' }}>ANOMALY</span>;
    }
  };

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '310px 1fr 360px',
        gap: '12px',
        padding: '12px 16px',
        height: 'calc(100vh - 46px)',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* ------------------------------------------------------------- */}
      {/* LEFT RAIL: Incident Selector & Queue                           */}
      {/* ------------------------------------------------------------- */}
      <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <div className="ops-panel-header" style={{ flexDirection: 'column', gap: '8px', alignItems: 'stretch' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Layers size={14} color="#38bdf8" />
              <span style={{ fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Incident Queue ({filteredIncidents.length})
              </span>
            </div>
          </div>

          {/* Quick Search */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={12} style={{ position: 'absolute', left: '7px', color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search incidents / faults..."
              value={searchIncident}
              onChange={(e) => setSearchIncident(e.target.value)}
              className="ops-input"
              style={{ paddingLeft: '24px', fontSize: '0.74rem', width: '100%' }}
            />
          </div>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '3px' }}>
            {[
              { id: 'ALL', label: 'All' },
              { id: 'INCIDENT', label: 'Cascades' },
              { id: 'CANDIDATE', label: 'Anomalies' },
              { id: 'NORMAL', label: 'Routine' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setKindFilter(f.id)}
                style={{
                  flex: 1,
                  padding: '2px 4px',
                  fontSize: '0.7rem',
                  borderRadius: 'var(--radius-xs)',
                  border: 'none',
                  background: kindFilter === f.id ? '#0284c7' : 'var(--bg-canvas)',
                  color: kindFilter === f.id ? '#ffffff' : 'var(--text-muted)',
                  fontWeight: kindFilter === f.id ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Incident List Items */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '6px' }}>
          {filteredIncidents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)', fontSize: '0.78rem' }}>
              No matching incidents found.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {filteredIncidents.map((inc) => {
                const isSelected = selectedIncident?.incident_id === inc.incident_id;
                const isFault = inc.kind === 'INCIDENT';

                return (
                  <div
                    key={inc.incident_id}
                    onClick={() => onSelectIncident(inc)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-sm)',
                      background: isSelected ? 'var(--bg-selected)' : 'var(--bg-surface-subtle)',
                      border: isSelected ? '1px solid #38bdf8' : '1px solid var(--border-subtle)',
                      borderLeft: isFault
                        ? '3px solid #f87171'
                        : isSelected
                        ? '3px solid #38bdf8'
                        : '3px solid var(--border-default)',
                      cursor: 'pointer',
                      transition: 'all 0.1s ease',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          className="font-mono text-xs"
                          style={{ fontWeight: 700, color: isFault ? '#f87171' : '#38bdf8' }}
                        >
                          {inc.incident_id}
                        </span>
                        {getKindBadge(inc.kind)}
                      </div>
                      <span className="font-mono text-xs text-dim">
                        {inc.event_ids.length} evts
                      </span>
                    </div>

                    <div
                      className="text-xs text-primary"
                      style={{
                        fontWeight: isSelected ? 600 : 500,
                        lineHeight: 1.3,
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {inc.title}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '2px' }}>
                      <div style={{ display: 'flex', gap: '3px' }}>
                        {inc.involved_nodes.map((n) => (
                          <span
                            key={n}
                            className={`ops-badge ${
                              n === 'NODE_A'
                                ? 'ops-badge-node-a'
                                : n === 'NODE_B'
                                ? 'ops-badge-node-b'
                                : 'ops-badge-node-c'
                            }`}
                            style={{ fontSize: '0.62rem', padding: '1px 4px' }}
                          >
                            {n.replace('NODE_', '')}
                          </span>
                        ))}
                      </div>

                      {inc.primary_faults.length > 0 && (
                        <span className="font-mono text-xs" style={{ color: '#f87171', fontWeight: 600, fontSize: '0.68rem' }}>
                          {inc.primary_faults.join(', ')}
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

      {/* ------------------------------------------------------------- */}
      {/* CENTER WORKSPACE: Incident Workbench & Investigation Console   */}
      {/* ------------------------------------------------------------- */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', height: '100%', overflow: 'hidden' }}>
        {/* Incident Summary Card & Node Topology */}
        {selectedIncident && (
          <div className="ops-panel" style={{ padding: '12px 16px', flexShrink: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                  <span className="font-mono text-sm" style={{ fontWeight: 800, color: selectedIncident.kind === 'INCIDENT' ? '#f87171' : '#38bdf8' }}>
                    {selectedIncident.incident_id}
                  </span>
                  {getKindBadge(selectedIncident.kind)}
                  <span className="ops-badge ops-badge-nominal">
                    {selectedIncident.recovery_status || 'NOMINAL'}
                  </span>
                </div>

                <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedIncident.title}
                </h2>
                <p className="text-xs text-secondary" style={{ marginTop: '2px', maxWidth: '850px' }}>
                  {selectedIncident.description}
                </p>
              </div>

              {/* Tri-Node Topology Flow Widget */}
              <div
                className="ops-panel-subtle"
                style={{
                  padding: '6px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  background: 'var(--bg-canvas)',
                }}
              >
                <div style={{ textAlign: 'center' }}>
                  <span className="ops-badge ops-badge-node-a" style={{ fontSize: '0.68rem' }}>NODE_A</span>
                  <div className="font-mono text-xs text-muted" style={{ fontSize: '0.68rem', marginTop: '2px' }}>
                    {nodeEventCounts.NODE_A} evts
                  </div>
                </div>

                <div className="font-mono text-xs text-dim">⟷</div>

                <div style={{ textAlign: 'center' }}>
                  <span className="ops-badge ops-badge-node-b" style={{ fontSize: '0.68rem' }}>NODE_B</span>
                  <div className="font-mono text-xs text-muted" style={{ fontSize: '0.68rem', marginTop: '2px' }}>
                    {nodeEventCounts.NODE_B} evts
                  </div>
                </div>

                <div className="font-mono text-xs text-dim">⟷</div>

                <div style={{ textAlign: 'center' }}>
                  <span className="ops-badge ops-badge-node-c" style={{ fontSize: '0.68rem' }}>NODE_C</span>
                  <div className="font-mono text-xs text-muted" style={{ fontSize: '0.68rem', marginTop: '2px' }}>
                    {nodeEventCounts.NODE_C} evts
                  </div>
                </div>
              </div>
            </div>

            {/* View Switcher Tabs */}
            <div style={{ display: 'flex', gap: '8px', marginTop: '10px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}>
              <button
                onClick={() => setActiveTab('timeline')}
                className={`btn-ops ${activeTab === 'timeline' ? 'btn-ops-primary' : 'btn-ops-secondary'}`}
                style={{ padding: '3px 10px', fontSize: '0.74rem' }}
              >
                <Clock size={12} />
                <span>Chronological Event Timeline ({incidentEvents.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('narrative')}
                className={`btn-ops ${activeTab === 'narrative' ? 'btn-ops-primary' : 'btn-ops-secondary'}`}
                style={{ padding: '3px 10px', fontSize: '0.74rem' }}
              >
                <FileText size={12} />
                <span>AI Engineering Investigation Report</span>
              </button>
            </div>
          </div>
        )}

        {/* Dynamic Center Panel Body */}
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
      </div>

      {/* ------------------------------------------------------------- */}
      {/* RIGHT PANEL: Level 3 & Level 4 Inspector & Evidence Drawer    */}
      {/* ------------------------------------------------------------- */}
      <div style={{ height: '100%', minHeight: 0, overflow: 'hidden' }}>
        <EvidenceInspector
          event={selectedEvent}
          evidence={selectedEvidence}
          relationships={relationships.filter(
            (r) =>
              selectedEvent &&
              (r.source_event_id === selectedEvent.event_id || r.target_event_id === selectedEvent.event_id)
          )}
          onSelectEventId={onSelectEventById}
        />
      </div>
    </div>
  );
};
