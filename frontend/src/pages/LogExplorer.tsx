import React from 'react';
import { NormalizedEvent, Evidence, EventRelationship } from '../types';
import { FilterBar } from '../components/filters/FilterBar';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';
import { Terminal, Download, FileCode, Layers } from 'lucide-react';
import { EventFilterParams } from '../services/api';

interface LogExplorerProps {
  events: NormalizedEvent[];
  filters: EventFilterParams;
  onFilterChange: (filters: EventFilterParams) => void;
  onResetFilters: () => void;
  selectedEvent: NormalizedEvent | null;
  selectedEvidence: Evidence[];
  relationships: EventRelationship[];
  onSelectEvent: (event: NormalizedEvent) => void;
  onSelectEventById: (id: string) => void;
}

export const LogExplorer: React.FC<LogExplorerProps> = ({
  events,
  filters,
  onFilterChange,
  onResetFilters,
  selectedEvent,
  selectedEvidence,
  relationships,
  onSelectEvent,
  onSelectEventById,
}) => {
  const handleExport = (format: 'json' | 'csv') => {
    const url = `/api/v1/export/events?format=${format}`;
    window.open(url, '_blank');
  };

  const getNodeBadgeClass = (node: string) => {
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
        gap: '10px',
        padding: '14px 18px',
        height: 'calc(100vh - var(--navbar-height))',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* Top Filter & Export Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <div style={{ flex: 1 }}>
          <FilterBar filters={filters} onChange={onFilterChange} onReset={onResetFilters} />
        </div>

        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            className="btn-ops btn-ops-secondary font-mono"
            onClick={() => handleExport('json')}
            style={{ fontSize: '0.74rem' }}
          >
            <Download size={12} /> JSON
          </button>
          <button
            className="btn-ops btn-ops-secondary font-mono"
            onClick={() => handleExport('csv')}
            style={{ fontSize: '0.74rem' }}
          >
            <Download size={12} /> CSV
          </button>
        </div>
      </div>

      {/* Main Table + Inspector Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedEvent ? '1fr 380px' : '1fr',
          gap: '12px',
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Table Panel */}
        <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
          <div className="ops-panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <Terminal size={13} color="var(--text-accent)" />
              <span className="panel-title">
                Evidence Log Stream
              </span>
              <span className="font-mono" style={{ fontSize: '0.62rem', padding: '1px 5px', borderRadius: 'var(--radius-xs)', background: 'var(--bg-surface-elevated)', color: 'var(--text-muted)', fontWeight: 700 }}>
                {events.length}
              </span>
            </div>
            <span className="text-xs text-muted">
              Click any row to inspect Level 4 physical source coordinates and raw byte stream
            </span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto' }}>
            <table className="ops-table">
              <thead>
                <tr>
                  <th style={{ width: '160px' }}>Timestamp (UTC)</th>
                  <th style={{ width: '80px' }}>Node</th>
                  <th style={{ width: '100px' }}>Family</th>
                  <th style={{ width: '150px' }}>Event Type</th>
                  <th>Payload Message / Raw Record</th>
                  <th style={{ width: '160px' }}>Source Coordinates</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                      No log records found matching current criteria.
                    </td>
                  </tr>
                ) : (
                  events.map((ev) => {
                    const isSelected = selectedEvent?.event_id === ev.event_id;
                    const formattedTime = new Date(ev.timestamp).toISOString().replace('T', ' ').slice(0, 23);
                    const isFault = ev.category === 'FAULT' || ev.severity === 'CRITICAL' || ev.severity === 'ERROR';

                    return (
                      <tr
                        key={ev.event_id}
                        onClick={() => onSelectEvent(ev)}
                        className={`ops-table-row ${isSelected ? 'ops-table-row-selected' : ''}`}
                        style={{ cursor: 'pointer' }}
                      >
                        <td className="font-mono text-xs" style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                          {formattedTime}
                        </td>
                        <td>
                          <span className={`ops-badge ${getNodeBadgeClass(ev.node)}`}>{ev.node}</span>
                        </td>
                        <td>
                          <span className="ops-badge ops-badge-muted">{ev.log_family}</span>
                        </td>
                        <td className="font-mono text-xs" style={{ fontWeight: 600, color: isFault ? '#dc2626' : 'var(--text-primary)' }}>
                          {ev.event_type}
                        </td>
                        <td style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                            {ev.message || ev.raw_record}
                          </span>
                        </td>
                        <td className="font-mono text-xs text-dim" style={{ whiteSpace: 'nowrap' }}>
                          <span style={{ color: 'var(--text-muted)' }}>{ev.source_file.split('/').slice(-2).join('/')}:</span>
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

        {/* Right Inspector Panel */}
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
