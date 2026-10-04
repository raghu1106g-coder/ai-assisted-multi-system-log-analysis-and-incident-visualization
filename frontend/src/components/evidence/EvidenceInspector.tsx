import React, { useState } from 'react';
import { NormalizedEvent, Evidence, EventRelationship } from '../../types';
import {
  ShieldCheck,
  FileCode,
  Link2,
  AlertTriangle,
  Copy,
  Check,
  ExternalLink,
  ArrowRight,
  ArrowLeft,
  Terminal,
  Layers,
  X,
} from 'lucide-react';

interface EvidenceInspectorProps {
  event: NormalizedEvent | null;
  evidence: Evidence[];
  relationships: EventRelationship[];
  onSelectEventId?: (id: string) => void;
  onClose?: () => void;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({
  event,
  evidence,
  relationships,
  onSelectEventId,
  onClose,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  if (!event) {
    return (
      <div className="ops-panel" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <ShieldCheck size={28} style={{ opacity: 0.4, marginBottom: '8px' }} />
        <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          No Event Selected
        </div>
        <p className="text-xs text-dim" style={{ marginTop: '4px', maxWidth: '260px' }}>
          Click any event in the timeline, log table, or correlation graph to inspect full source evidence and causal links.
        </p>
      </div>
    );
  }

  const getNodeBadgeClass = (node: string) => {
    if (node === 'NODE_A') return 'ops-badge-node-a';
    if (node === 'NODE_B') return 'ops-badge-node-b';
    if (node === 'NODE_C') return 'ops-badge-node-c';
    return 'ops-badge-info';
  };

  const formattedTime = new Date(event.timestamp).toISOString().replace('T', ' ');

  return (
    <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Inspector Header */}
      <div className="ops-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className={`ops-badge ${getNodeBadgeClass(event.node)}`}>{event.node}</span>
          <span className="ops-badge ops-badge-muted">{event.log_family}</span>
          {event.severity && (
            <span
              className={`ops-badge ${
                event.severity === 'CRITICAL' || event.severity === 'ERROR'
                  ? 'ops-badge-critical'
                  : 'ops-badge-warning'
              }`}
            >
              {event.severity}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button
            className="btn-ops btn-ops-ghost"
            onClick={() => copyToClipboard(event.event_id, 'eid')}
            title="Copy Event ID"
          >
            {copiedKey === 'eid' ? <Check size={12} color="#059669" /> : <Copy size={12} />}
            <span className="font-mono text-xs">{event.event_id}</span>
          </button>
          {onClose && (
            <button className="btn-ops btn-ops-ghost" onClick={onClose} title="Close Inspector">
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {/* Event Type & Message */}
        <div>
          <div className="font-mono text-sm" style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
            {event.event_type}
          </div>
          <div className="text-xs text-muted" style={{ marginTop: '2px' }}>
            {event.message || 'No structured description'}
          </div>
        </div>

        {/* Level 4: Source Line Traceability Box */}
        <div
          style={{
            padding: '10px 12px',
            borderLeft: '3px solid var(--text-accent)',
            background: 'var(--status-info-bg)',
            border: '1px solid var(--status-info-border)',
            borderLeftWidth: '3px',
            borderLeftColor: 'var(--text-accent)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '7px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                color: 'var(--text-accent)',
              }}
            >
              <FileCode size={13} />
              <span className="section-label" style={{ color: 'var(--text-accent)' }}>Level 4 · Source Traceability</span>
            </div>

            <button
              className="btn-ops btn-ops-ghost font-mono"
              onClick={() => copyToClipboard(`${event.source_file}:${event.source_line}`, 'src')}
              style={{
                padding: '1px 7px',
                fontSize: '0.67rem',
                background: 'var(--bg-surface)',
                border: '1px solid var(--status-info-border)',
              }}
              title="Copy file:line"
            >
              {copiedKey === 'src' ? <Check size={11} color="var(--status-nominal)" /> : <Copy size={11} />}
              <span>Copy</span>
            </button>
          </div>

          <div className="font-mono" style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.72rem' }}>
            <div className="evidence-coord">
              <span className="evidence-coord-label">File</span>
              <span className="evidence-coord-value">{event.source_file}</span>
            </div>
            <div className="evidence-coord">
              <span className="evidence-coord-label">Line</span>
              <span className="evidence-coord-value" style={{ color: 'var(--text-accent)', fontWeight: 700 }}>L{event.source_line}</span>
            </div>
            <div className="evidence-coord">
              <span className="evidence-coord-label">UTC Timestamp</span>
              <span className="evidence-coord-value">{formattedTime}</span>
            </div>
          </div>
        </div>

        {/* Raw Log Record */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <span style={{ fontWeight: 600, fontSize: '0.74rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
              Raw Log Record (Exact Byte String)
            </span>
            <button
              className="btn-ops btn-ops-ghost font-mono text-xs"
              onClick={() => copyToClipboard(event.raw_record, 'raw')}
              style={{ padding: '1px 5px', fontSize: '0.68rem', border: '1px solid var(--border-subtle)' }}
            >
              {copiedKey === 'raw' ? <Check size={11} color="#059669" /> : <Copy size={11} />}
              <span>Copy Log</span>
            </button>
          </div>

          <div className="ops-raw-log">
            {event.raw_record}
          </div>
        </div>

        {/* Normalized Key-Value Attributes */}
        {event.attributes && Object.keys(event.attributes).length > 0 && (
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.74rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
              Normalized Attribute Map
            </div>
            <div className="ops-panel-subtle" style={{ padding: '6px 10px', display: 'flex', flexDirection: 'column', gap: '2px', background: '#ffffff' }}>
              {Object.entries(event.attributes).map(([key, val]) => (
                <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span className="font-mono text-xs text-muted">{key}:</span>
                  <span className="font-mono text-xs" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                    {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Correlated Event Relationships */}
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              marginBottom: '6px',
            }}
          >
            <Link2 size={13} color="var(--node-b-color)" />
            <span className="section-label" style={{ color: 'var(--node-b-color)' }}>
              Causal Relationships ({relationships.length})
            </span>
          </div>

          {relationships.length === 0 ? (
            <div className="text-xs text-dim" style={{ fontStyle: 'italic', padding: '6px' }}>
              No explicit cross-node or sequence relationships linked.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {relationships.map((rel) => {
                const isSource = rel.source_event_id === event.event_id;
                const otherId = isSource ? rel.target_event_id : rel.source_event_id;
                const directionLabel = isSource ? 'Target →' : 'Source ←';

                return (
                  <div
                    key={rel.relationship_id}
                    className="ops-panel-subtle"
                    style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: '4px', background: '#ffffff' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="ops-badge ops-badge-routine" style={{ fontSize: '0.65rem' }}>
                          {rel.relationship_type}
                        </span>
                        <span className="text-xs text-dim">{directionLabel}</span>
                      </div>

                      <button
                        onClick={() => onSelectEventId?.(otherId)}
                        className="btn-ops btn-ops-ghost font-mono text-xs"
                        style={{ padding: '1px 6px', color: '#0284c7', border: '1px solid #bae6fd', background: '#eff6ff' }}
                        title={`Navigate to event ${otherId}`}
                      >
                        {otherId} <ArrowRight size={10} />
                      </button>
                    </div>

                    <div className="text-xs text-secondary" style={{ lineHeight: 1.4 }}>
                      {rel.reason}
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px' }}>
                      <span className="font-mono text-xs text-dim">
                        Confidence: {(rel.confidence * 100).toFixed(0)}%
                      </span>
                      <span className="font-mono text-xs text-dim">
                        {rel.relationship_id}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
