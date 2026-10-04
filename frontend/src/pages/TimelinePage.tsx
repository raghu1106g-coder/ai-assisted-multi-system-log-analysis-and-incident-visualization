import React from 'react';
import { NormalizedEvent, Evidence, EventRelationship } from '../types';
import { IncidentTimeline } from '../components/timeline/IncidentTimeline';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';
import { Clock, X } from 'lucide-react';

interface TimelinePageProps {
  events: NormalizedEvent[];
  relationships: EventRelationship[];
  selectedEvent: NormalizedEvent | null;
  selectedEvidence: Evidence[];
  onSelectEvent: (event: NormalizedEvent) => void;
  onSelectEventById: (id: string) => void;
}

export const TimelinePage: React.FC<TimelinePageProps> = ({
  events,
  relationships,
  selectedEvent,
  selectedEvidence,
  onSelectEvent,
  onSelectEventById,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '14px 18px',
        height: 'calc(100vh - var(--navbar-height))',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* Page header */}
      <div
        className="ops-panel"
        style={{
          padding: '12px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '10px',
          flexShrink: 0,
        }}
      >
        <div>
          <div className="section-label" style={{ marginBottom: '2px' }}>
            Chronological Event Stream
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={15} color="var(--text-accent)" />
            <h2 className="page-title" style={{ fontSize: '1rem' }}>
              Full Cross-Node Incident Timeline
            </h2>
          </div>
          <p className="text-xs text-muted" style={{ marginTop: '2px' }}>
            Millisecond-precision UTC timeline across all distributed nodes. Click any event to inspect source evidence.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              padding: '6px 12px',
              background: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              gap: '12px',
            }}
          >
            <span className="font-mono text-xs text-muted">
              Total events:{' '}
              <strong style={{ color: 'var(--text-accent)' }}>
                {events.length.toLocaleString()}
              </strong>
            </span>
          </div>
        </div>
      </div>

      {/* Timeline + optional evidence inspector */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedEvent ? '1fr 375px' : '1fr',
          gap: '12px',
          flex: 1,
          minHeight: 0,
          transition: 'grid-template-columns 0.15s ease',
        }}
      >
        <div style={{ height: '100%', minHeight: 0 }}>
          <IncidentTimeline
            events={events}
            selectedEventId={selectedEvent?.event_id || null}
            onSelectEvent={onSelectEvent}
          />
        </div>

        {selectedEvent && (
          <div style={{ height: '100%', minHeight: 0 }}>
            <EvidenceInspector
              event={selectedEvent}
              evidence={selectedEvidence}
              relationships={relationships.filter(
                (r) =>
                  r.source_event_id === selectedEvent.event_id ||
                  r.target_event_id === selectedEvent.event_id
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
