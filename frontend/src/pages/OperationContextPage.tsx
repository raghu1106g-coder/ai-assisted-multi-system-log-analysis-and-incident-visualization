import React, { useState } from 'react';
import {
  Compass,
  Activity,
  Layers,
  ArrowRight,
  Server,
  Cpu,
  Clock,
  Radio,
  FileCode,
  ShieldAlert,
  Search,
  Filter,
} from 'lucide-react';
import { NormalizedEvent, Incident, EventRelationship, Evidence } from '../types';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';

interface OperationContextPageProps {
  events: NormalizedEvent[];
  incidents: Incident[];
  relationships: EventRelationship[];
  selectedEvent: NormalizedEvent | null;
  selectedEvidence: Evidence[];
  onSelectEvent: (event: NormalizedEvent) => void;
  onSelectEventById: (id: string) => void;
}

export const OperationContextPage: React.FC<OperationContextPageProps> = ({
  events,
  incidents,
  relationships,
  selectedEvent,
  selectedEvidence,
  onSelectEvent,
  onSelectEventById,
}) => {
  const [selectedNode, setSelectedNode] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Extract all state change events, commands, and planning exchanges for context
  const stateEvents = events.filter(
    (e) =>
      e.log_family === 'state' ||
      e.log_family === 'operator' ||
      e.log_family === 'planning' ||
      e.event_type.includes('STATE') ||
      e.event_type.includes('COMMAND') ||
      e.event_type.includes('PLAN')
  );

  const filteredEvents = stateEvents.filter((e) => {
    if (selectedNode !== 'ALL' && e.node !== selectedNode) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const match =
        e.event_type.toLowerCase().includes(q) ||
        (e.message && e.message.toLowerCase().includes(q)) ||
        (e.entity && e.entity.toLowerCase().includes(q)) ||
        (e.component && e.component.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  // Calculate current node states from most recent STATE_CHANGE events
  const latestNodeStates: Record<string, { entity: string; state: string; time: string; event: NormalizedEvent }[]> = {
    NODE_A: [],
    NODE_B: [],
    NODE_C: [],
  };

  events.forEach((ev) => {
    if (ev.event_type === 'STATE_CHANGE' && ev.attributes?.new_state && ev.entity) {
      const list = latestNodeStates[ev.node] || [];
      const existingIdx = list.findIndex((item) => item.entity === ev.entity);
      const entry = {
        entity: ev.entity,
        state: String(ev.attributes.new_state),
        time: ev.timestamp,
        event: ev,
      };
      if (existingIdx >= 0) {
        list[existingIdx] = entry;
      } else {
        list.push(entry);
      }
      latestNodeStates[ev.node] = list;
    }
  });

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '16px 20px',
        height: 'calc(100vh - var(--navbar-height))',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* Top Banner */}
      <div
        className="ops-panel"
        style={{
          padding: '12px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>Level 3 Visualization</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Compass size={15} color="var(--text-accent)" />
            <h2 className="page-title" style={{ fontSize: '1rem' }}>
              Operation Context &amp; System State Matrix
            </h2>
          </div>
          <p className="text-xs text-secondary" style={{ marginTop: '2px' }}>
            Explains: <strong>What was the system doing when the fault occurred?</strong> Correlates phases, component states, and command handshakes.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={12} style={{ position: 'absolute', left: '7px', color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search states, entities, commands..."
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

      {/* Tri-Node Realtime Component State Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
        {['NODE_A', 'NODE_B', 'NODE_C'].map((node) => {
          const states = latestNodeStates[node] || [];
          const badgeClass =
            node === 'NODE_A' ? 'ops-badge-node-a' : node === 'NODE_B' ? 'ops-badge-node-b' : 'ops-badge-node-c';
          return (
            <div key={node} className="ops-panel" style={{ padding: '12px 14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid var(--border-subtle)' }}>
                <span className={`ops-badge ${badgeClass}`}>{node} Component States</span>
                <span className="text-xs text-muted">{states.length} tracked entities</span>
              </div>

              {states.length === 0 ? (
                <div className="text-xs text-dim" style={{ padding: '8px 0' }}>
                  No active entity states registered yet.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '100px', overflowY: 'auto' }}>
                  {states.map((s) => {
                    const isNominal = s.state === 'NOMINAL' || s.state === 'READY' || s.state === 'ACTIVE';
                    const isDegraded = s.state === 'DEGRADED' || s.state === 'FAIL' || s.state === 'ERROR';
                    return (
                      <div
                        key={s.entity}
                        onClick={() => onSelectEvent(s.event)}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          padding: '3px 6px',
                          borderRadius: 'var(--radius-xs)',
                          background: 'var(--bg-surface-subtle)',
                          cursor: 'pointer',
                          fontSize: '0.74rem',
                        }}
                      >
                        <span className="font-mono" style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
                          {s.entity}
                        </span>
                        <span
                          className={`ops-badge ${
                            isNominal
                              ? 'ops-badge-nominal'
                              : isDegraded
                              ? 'ops-badge-critical'
                              : 'ops-badge-warning'
                          }`}
                          style={{ fontSize: '0.66rem' }}
                        >
                          {s.state}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Operational Stream Table & Evidence Side Drawer */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedEvent ? '1fr 380px' : '1fr',
          gap: '12px',
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Context Stream Table */}
        <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
          <div className="ops-panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Compass size={14} color="#0284c7" />
              <span style={{ fontWeight: 700, fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Operational Event Context Stream ({filteredEvents.length})
              </span>
            </div>
            <span className="text-xs text-muted">
              Click any operational record to inspect Level 4 source line evidence
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table className="ops-table">
              <thead>
                <tr>
                  <th style={{ width: '150px' }}>Timestamp (UTC)</th>
                  <th style={{ width: '80px' }}>Node</th>
                  <th style={{ width: '100px' }}>Family</th>
                  <th style={{ width: '140px' }}>Entity / Component</th>
                  <th style={{ width: '150px' }}>Event Type</th>
                  <th>Operational Message / State Transition</th>
                  <th style={{ width: '140px' }}>Source Coordinates</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                      No operational context events matching filter.
                    </td>
                  </tr>
                ) : (
                  filteredEvents.map((ev) => {
                    const isSelected = selectedEvent?.event_id === ev.event_id;
                    const formattedTime = new Date(ev.timestamp).toISOString().replace('T', ' ').slice(11, 23);
                    const isStateChange = ev.event_type === 'STATE_CHANGE';
                    const isCommand = ev.log_family === 'operator';

                    return (
                      <tr
                        key={ev.event_id}
                        onClick={() => onSelectEvent(ev)}
                        className={`ops-table-row ${isSelected ? 'ops-table-row-selected' : ''}`}
                        style={{ cursor: 'pointer' }}
                      >
                        <td className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                          {formattedTime}
                        </td>
                        <td>
                          <span
                            className={`ops-badge ${
                              ev.node === 'NODE_A' ? 'ops-badge-node-a' : ev.node === 'NODE_B' ? 'ops-badge-node-b' : 'ops-badge-node-c'
                            }`}
                          >
                            {ev.node}
                          </span>
                        </td>
                        <td>
                          <span className="ops-badge ops-badge-muted">{ev.log_family}</span>
                        </td>
                        <td className="font-mono text-xs" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {ev.entity || ev.component || 'SYSTEM'}
                        </td>
                        <td className="font-mono text-xs" style={{ color: isCommand ? '#6366f1' : isStateChange ? '#0284c7' : 'var(--text-primary)' }}>
                          {ev.event_type}
                        </td>
                        <td style={{ maxWidth: '350px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {ev.message || ev.raw_record}
                          </span>
                        </td>
                        <td className="font-mono text-xs text-dim">
                          <span style={{ color: 'var(--text-muted)' }}>{ev.source_file.split('/').slice(-1)[0]}:</span>
                          <span style={{ color: '#0284c7', fontWeight: 600 }}>L{ev.source_line}</span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Level 4 Inspector Drawer */}
        {selectedEvent && (
          <div style={{ height: '100%', minHeight: 0 }}>
            <EvidenceInspector
              event={selectedEvent}
              evidence={selectedEvidence}
              relationships={relationships.filter(
                (r) =>
                  r.source_event_id === selectedEvent.event_id || r.target_event_id === selectedEvent.event_id
              )}
              onSelectEventId={onSelectEventById}
              onClose={() => onSelectEvent(null as any)}
            />
          </div>
        )}
      </div>
    </div>
  );
};
