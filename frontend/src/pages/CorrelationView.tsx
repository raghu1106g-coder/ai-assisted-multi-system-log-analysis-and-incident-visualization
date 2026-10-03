import React, { useState } from 'react';
import { CorrelationGraph } from '../components/graph/CorrelationGraph';
import { EvidenceInspector } from '../components/evidence/EvidenceInspector';
import { NormalizedEvent, Evidence, EventRelationship } from '../types';
import { Network, Link2, ArrowRight, Layers, Filter } from 'lucide-react';

interface CorrelationViewProps {
  graphData: {
    nodes: any[];
    links: any[];
    node_count: number;
    link_count: number;
  } | null;
  relationships: EventRelationship[];
  events: NormalizedEvent[];
  selectedEvent: NormalizedEvent | null;
  selectedEvidence: Evidence[];
  onSelectEvent: (event: NormalizedEvent) => void;
  onSelectEventById: (id: string) => void;
}

export const CorrelationView: React.FC<CorrelationViewProps> = ({
  graphData,
  relationships,
  events,
  selectedEvent,
  selectedEvidence,
  onSelectEvent,
  onSelectEventById,
}) => {
  const [selectedRelType, setSelectedRelType] = useState<string>('ALL');

  const filteredRelationships = relationships.filter((r) => {
    if (selectedRelType !== 'ALL' && r.relationship_type !== selectedRelType) return false;
    return true;
  });

  const uniqueTypes = Array.from(new Set(relationships.map((r) => r.relationship_type)));

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        padding: '12px 16px',
        height: 'calc(100vh - 46px)',
        overflow: 'hidden',
        background: 'var(--bg-canvas)',
      }}
    >
      {/* Top Banner */}
      <div
        className="ops-panel"
        style={{
          padding: '10px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Network size={16} color="#c084fc" />
            <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Deterministic Cross-Node Correlation & Causal Graph Engine
            </h2>
          </div>
          <p className="text-xs text-secondary" style={{ marginTop: '2px' }}>
            Edges are constructed strictly via explicit shared IDs, request-reply handshakes, or confirmed fault cascades. Temporal closeness alone never creates edges.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <select
            value={selectedRelType}
            onChange={(e) => setSelectedRelType(e.target.value)}
            className="ops-select"
            style={{ fontSize: '0.74rem' }}
          >
            <option value="ALL">All Relationship Types ({relationships.length})</option>
            {uniqueTypes.map((t) => (
              <option key={t} value={t}>
                {t} ({relationships.filter((r) => r.relationship_type === t).length})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Grid: Graph + Relationship Explorer / Inspector */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: selectedEvent ? '1.25fr 1fr' : '1.35fr 0.95fr',
          gap: '12px',
          flex: 1,
          minHeight: 0,
        }}
      >
        {/* Left Column: Interactive Topology Graph Visualizer */}
        <div style={{ height: '100%', minHeight: 0 }}>
          <CorrelationGraph
            nodes={graphData?.nodes || []}
            links={graphData?.links || []}
            selectedNodeId={selectedEvent?.event_id || null}
            onSelectNode={onSelectEventById}
          />
        </div>

        {/* Right Column: Relationships Table or Evidence Inspector */}
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden' }}>
          {selectedEvent ? (
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
          ) : (
            <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
              <div className="ops-panel-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Link2 size={14} color="#38bdf8" />
                  <span style={{ fontWeight: 700, fontSize: '0.82rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Discovered Relationships ({filteredRelationships.length})
                  </span>
                </div>
                <span className="text-xs text-dim">Click nodes or IDs to inspect</span>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', padding: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {filteredRelationships.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)', fontSize: '0.78rem' }}>
                    No relationships found for selected type.
                  </div>
                ) : (
                  filteredRelationships.map((rel) => (
                    <div
                      key={rel.relationship_id}
                      className="ops-panel-subtle"
                      style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '4px' }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className="ops-badge ops-badge-routine" style={{ fontSize: '0.68rem' }}>
                          {rel.relationship_type}
                        </span>
                        <span className="font-mono text-xs" style={{ color: '#38bdf8' }}>
                          Confidence: {(rel.confidence * 100).toFixed(0)}%
                        </span>
                      </div>

                      <div className="text-xs text-secondary" style={{ lineHeight: 1.4 }}>
                        {rel.reason}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', marginTop: '2px' }}>
                        <button
                          onClick={() => onSelectEventById(rel.source_event_id)}
                          className="btn-ops btn-ops-ghost font-mono text-xs"
                          style={{ padding: '2px 6px', fontSize: '0.7rem', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.25)' }}
                          title={`Source Event: ${rel.source_event_id}`}
                        >
                          Src: {rel.source_event_id}
                        </button>

                        <ArrowRight size={12} color="var(--text-dim)" />

                        <button
                          onClick={() => onSelectEventById(rel.target_event_id)}
                          className="btn-ops btn-ops-ghost font-mono text-xs"
                          style={{ padding: '2px 6px', fontSize: '0.7rem', color: '#c084fc', border: '1px solid rgba(192, 132, 252, 0.25)' }}
                          title={`Target Event: ${rel.target_event_id}`}
                        >
                          Tgt: {rel.target_event_id}
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
