import React, { useState } from 'react';
import { NormalizedEvent } from '../../types';
import { Clock, ShieldAlert, Cpu, CheckCircle2, ChevronRight, Search, Filter, AlertTriangle, ArrowRight, CornerDownRight } from 'lucide-react';

interface IncidentTimelineProps {
  events: NormalizedEvent[];
  selectedEventId: string | null;
  onSelectEvent: (event: NormalizedEvent) => void;
}

export const IncidentTimeline: React.FC<IncidentTimelineProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
}) => {
  const [filterNode, setFilterNode] = useState<string>('ALL');
  const [filterFamily, setFilterFamily] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const filteredEvents = events.filter((ev) => {
    if (filterNode !== 'ALL' && ev.node !== filterNode) return false;
    if (filterFamily !== 'ALL' && ev.log_family !== filterFamily) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const match =
        ev.event_id.toLowerCase().includes(q) ||
        ev.event_type.toLowerCase().includes(q) ||
        (ev.message && ev.message.toLowerCase().includes(q)) ||
        (ev.component && ev.component.toLowerCase().includes(q)) ||
        (ev.entity && ev.entity.toLowerCase().includes(q));
      if (!match) return false;
    }
    return true;
  });

  const getNodeBadgeClass = (node: string) => {
    if (node === 'NODE_A') return 'ops-badge-node-a';
    if (node === 'NODE_B') return 'ops-badge-node-b';
    if (node === 'NODE_C') return 'ops-badge-node-c';
    return 'ops-badge-info';
  };

  const getEventTypeBadge = (ev: NormalizedEvent) => {
    const type = ev.event_type;
    const cat = ev.category;
    const sev = ev.severity;

    if (cat === 'FAULT' || sev === 'CRITICAL' || sev === 'ERROR' || type.includes('FAULT') || type.includes('ERROR')) {
      return <span className="ops-badge ops-badge-critical">{type}</span>;
    }
    if (type.includes('RECOVERY') || type.includes('CLEARED')) {
      return <span className="ops-badge ops-badge-nominal">{type}</span>;
    }
    if (type.includes('WARN') || type.includes('DEGRADED') || type.includes('DEVIATION')) {
      return <span className="ops-badge ops-badge-warning">{type}</span>;
    }
    if (ev.log_family === 'operator' || type.includes('COMMAND')) {
      return <span className="ops-badge ops-badge-routine">{type}</span>;
    }
    if (ev.log_family === 'planning' || type.includes('MESSAGE')) {
      return <span className="ops-badge ops-badge-info">{type}</span>;
    }
    return <span className="ops-badge ops-badge-muted">{type}</span>;
  };

  return (
    <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Timeline Controls Header */}
      <div className="ops-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
          <Clock size={13} color="var(--text-accent)" />
          <span className="panel-title">
            Event Sequence
          </span>
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
            {filteredEvents.length}
          </span>
        </div>

        {/* Filter Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search size={11} style={{ position: 'absolute', left: '7px', color: 'var(--text-dim)', pointerEvents: 'none' }} />
            <input
              type="text"
              placeholder="Search events…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="ops-input"
              style={{ paddingLeft: '22px', fontSize: '0.72rem', width: '160px' }}
            />
          </div>

          <select
            value={filterNode}
            onChange={(e) => setFilterNode(e.target.value)}
            className="ops-select"
            style={{ fontSize: '0.72rem' }}
          >
            <option value="ALL">All Nodes</option>
            <option value="NODE_A">NODE_A</option>
            <option value="NODE_B">NODE_B</option>
            <option value="NODE_C">NODE_C</option>
          </select>

          <select
            value={filterFamily}
            onChange={(e) => setFilterFamily(e.target.value)}
            className="ops-select"
            style={{ fontSize: '0.72rem' }}
          >
            <option value="ALL">All Families</option>
            <option value="fault_recovery">fault_recovery</option>
            <option value="planning">planning</option>
            <option value="state">state</option>
            <option value="operator">operator</option>
            <option value="guidance">guidance</option>
          </select>
        </div>
      </div>

      {/* Timeline Stream */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
        {filteredEvents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)', fontSize: '0.8rem' }}>
            No events match current filter.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {filteredEvents.map((ev) => {
              const isSelected = ev.event_id === selectedEventId;
              const formattedTime = new Date(ev.timestamp).toISOString().replace('T', ' ').slice(11, 23);
              const isFault = ev.category === 'FAULT' || ev.severity === 'CRITICAL' || ev.severity === 'ERROR';

              return (
                <div
                  key={ev.event_id}
                  onClick={() => onSelectEvent(ev)}
                  className={`incident-card${isFault ? ' fault' : ''}${isSelected ? ' selected' : ''}`}
                style={{ gap: '4px', display: 'flex', flexDirection: 'column' }}
              >
                  {/* Top metadata line */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="font-mono text-xs text-muted" style={{ fontWeight: 600 }}>
                        {formattedTime}
                      </span>
                      <span className={`ops-badge ${getNodeBadgeClass(ev.node)}`} style={{ fontSize: '0.68rem' }}>
                        {ev.node}
                      </span>
                      {getEventTypeBadge(ev)}
                      {ev.entity && (
                        <span className="font-mono text-xs" style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>
                          {ev.entity}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="font-mono text-xs text-dim">
                        L{ev.source_line}
                      </span>
                      <span className="font-mono text-xs text-dim">
                        {ev.event_id}
                      </span>
                    </div>
                  </div>

                  {/* Message body */}
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '8px' }}>
                    <div className="text-xs text-primary" style={{ fontWeight: 500 }}>
                      {ev.message || ev.raw_record.slice(0, 100)}
                    </div>

                    {/* Attributes chips preview */}
                    {ev.attributes && Object.keys(ev.attributes).length > 0 && (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                        {Object.entries(ev.attributes).slice(0, 2).map(([k, v]) => (
                          <span
                            key={k}
                            className="font-mono text-xs ops-badge ops-badge-muted"
                            style={{ fontSize: '0.65rem' }}
                          >
                            {k}={String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
