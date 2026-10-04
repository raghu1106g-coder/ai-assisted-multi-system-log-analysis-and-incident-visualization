import React, { useState } from 'react';
import { Incident, AIIncidentNarrative } from '../../types';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  RefreshCw,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  Zap,
  Info,
} from 'lucide-react';
import { api } from '../../services/api';

interface AINarrativePanelProps {
  incident: Incident | null;
  onSelectEventById?: (id: string) => void;
}

export const AINarrativePanel: React.FC<AINarrativePanelProps> = ({
  incident,
  onSelectEventById,
}) => {
  const [narrative, setNarrative] = useState<AIIncidentNarrative | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!incident) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.generateNarrative(incident.incident_id);
      setNarrative(res.narrative);
    } catch (err: any) {
      setError(err.message || 'Failed to generate narrative');
    } finally {
      setIsLoading(false);
    }
  };

  if (!incident) {
    return (
      <div className="ops-panel" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}>
        <FileText size={24} style={{ margin: '0 auto 8px auto', opacity: 0.5 }} />
        <p className="text-sm">Select an incident to view structured engineering synthesis.</p>
      </div>
    );
  }

  return (
    <div className="ops-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div className="ops-panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={14} color="var(--text-accent)" />
          <span className="panel-title">
            Incident Narrative
          </span>
          <span className="font-mono text-2xs text-muted">{incident.incident_id}</span>
        </div>

        <button
          className="btn-ops btn-ops-primary"
          onClick={handleGenerate}
          disabled={isLoading}
          style={{ fontSize: '0.74rem', padding: '3px 8px' }}
        >
          <RefreshCw size={11} className={isLoading ? 'animate-spin' : ''} />
          <span>{isLoading ? 'Synthesizing...' : narrative ? 'Regenerate Brief' : 'Generate Synthesis'}</span>
        </button>
      </div>

      {/* Main Content Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {error && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--status-critical-bg)',
              border: '1px solid var(--status-critical-border)',
              color: 'var(--status-critical)',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <AlertTriangle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Deterministic Reconstructed Overview */}
        <div className="ops-panel-subtle" style={{ padding: '12px 14px', background: '#ffffff', border: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
            <span className="text-xs" style={{ fontWeight: 700, color: '#0284c7', textTransform: 'uppercase' }}>
              Deterministic Finding: {incident.title}
            </span>
            <span className="ops-badge ops-badge-nominal">DETERMINISTIC RECONSTRUCTION</span>
          </div>
          <p className="text-xs text-secondary" style={{ lineHeight: 1.5 }}>
            {incident.description}
          </p>

          <div style={{ display: 'flex', gap: '12px', marginTop: '10px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)', flexWrap: 'wrap' }}>
            <div className="text-xs">
              <span className="text-muted">Nodes: </span>
              <span className="font-mono" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                {incident.involved_nodes.join(', ')}
              </span>
            </div>
            <div className="text-xs">
              <span className="text-muted">Faults: </span>
              <span className="font-mono" style={{ color: '#dc2626', fontWeight: 600 }}>
                {incident.primary_faults.length > 0 ? incident.primary_faults.join(', ') : 'None'}
              </span>
            </div>
            <div className="text-xs">
              <span className="text-muted">Status: </span>
              <span className="font-mono" style={{ color: '#059669', fontWeight: 600 }}>
                {incident.recovery_status || 'UNKNOWN'}
              </span>
            </div>
          </div>
        </div>

        {/* Generated Structured Brief */}
        {narrative ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* Executive Summary */}
            <div className="ops-panel-subtle" style={{ padding: '12px 14px', borderLeft: '3px solid #0284c7', background: '#f0f9ff' }}>
              <div style={{ fontWeight: 700, fontSize: '0.78rem', textTransform: 'uppercase', color: '#0369a1', marginBottom: '4px' }}>
                Executive Incident Synthesis
              </div>
              <p className="text-xs text-primary" style={{ lineHeight: 1.55 }}>
                {narrative.incident_summary}
              </p>
            </div>

            {/* Confirmed Observations Section */}
            {narrative.observations && narrative.observations.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={13} color="#059669" />
                  <span style={{ fontWeight: 700, fontSize: '0.76rem', textTransform: 'uppercase', color: '#047857', letterSpacing: '0.04em' }}>
                    Confirmed Facts (Direct Grounding)
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {narrative.observations.map((obs, idx) => (
                    <div
                      key={idx}
                      className="ops-panel-subtle"
                      style={{ padding: '8px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', background: '#ffffff' }}
                    >
                      <div className="text-xs text-secondary" style={{ flex: 1, lineHeight: 1.45 }}>
                        • {obs.statement}
                      </div>

                      {obs.evidence_refs && obs.evidence_refs.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', flexShrink: 0 }}>
                          {obs.evidence_refs.map((refId) => (
                            <button
                              key={refId}
                              onClick={() => onSelectEventById?.(refId)}
                              className="btn-ops btn-ops-ghost font-mono text-xs"
                              style={{ padding: '1px 5px', fontSize: '0.68rem', color: '#0284c7', border: '1px solid #bae6fd', background: '#eff6ff' }}
                              title={`Inspect source evidence for ${refId}`}
                            >
                              <ExternalLink size={10} /> {refId}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Possible Relationships Section */}
            {narrative.possible_relationships && narrative.possible_relationships.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertTriangle size={13} color="#d97706" />
                  <span style={{ fontWeight: 700, fontSize: '0.76rem', textTransform: 'uppercase', color: '#b45309', letterSpacing: '0.04em' }}>
                    Possible / Inferred Relationships (Uncertainty Explicit)
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {narrative.possible_relationships.map((rel, idx) => (
                    <div
                      key={idx}
                      className="ops-panel-subtle"
                      style={{ padding: '8px 10px', borderLeft: '2px solid #f59e0b', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', background: '#ffffff' }}
                    >
                      <div className="text-xs text-secondary" style={{ flex: 1, lineHeight: 1.45 }}>
                        {rel.description}
                      </div>

                      {rel.evidence_refs && rel.evidence_refs.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', flexShrink: 0 }}>
                          {rel.evidence_refs.map((refId) => (
                            <button
                              key={refId}
                              onClick={() => onSelectEventById?.(refId)}
                              className="btn-ops btn-ops-ghost font-mono text-xs"
                              style={{ padding: '1px 5px', fontSize: '0.68rem', color: '#d97706', border: '1px solid #fde68a', background: '#fffbeb' }}
                              title={`Inspect evidence for ${refId}`}
                            >
                              <ExternalLink size={10} /> {refId}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Unknown / Information Gaps */}
            {narrative.uncertainties && narrative.uncertainties.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <HelpCircle size={13} color="var(--text-dim)" />
                  <span style={{ fontWeight: 700, fontSize: '0.76rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                    Unknown / Insufficient Evidence
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {narrative.uncertainties.map((unc, idx) => (
                    <div
                      key={idx}
                      className="ops-panel-subtle"
                      style={{ padding: '8px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', background: '#ffffff' }}
                    >
                      <div className="text-xs text-muted" style={{ lineHeight: 1.45 }}>
                        • {unc.description}
                      </div>
                      <span className="ops-badge ops-badge-muted font-mono" style={{ fontSize: '0.65rem' }}>
                        {unc.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recovery Summary */}
            {narrative.recovery_summary && (
              <div className="ops-panel-subtle" style={{ padding: '10px 12px', borderLeft: '2px solid #059669', background: '#ecfdf5' }}>
                <div style={{ fontWeight: 700, fontSize: '0.76rem', textTransform: 'uppercase', color: '#047857', marginBottom: '2px' }}>
                  Recovery & Resolution Summary
                </div>
                <p className="text-xs text-secondary" style={{ lineHeight: 1.5 }}>
                  {narrative.recovery_summary}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div
            className="ops-panel-subtle"
            style={{ padding: '24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', background: '#ffffff' }}
          >
            <Sparkles size={20} color="#0284c7" style={{ opacity: 0.8 }} />
            <div className="text-xs text-muted" style={{ maxWidth: '420px' }}>
              Click <strong>Generate Synthesis</strong> to run AI-assisted structured hypothesis verification and uncertainty analysis against the normalized log graph.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
