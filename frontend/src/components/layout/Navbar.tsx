import React from 'react';
import { Shield, Cpu, Network, Terminal, AlertOctagon, RefreshCw, Activity, Server } from 'lucide-react';
import { SystemStats } from '../../types';

interface NavbarProps {
  onRunPipeline: () => void;
  isLoading: boolean;
  activeView: string;
  setActiveView: (view: string) => void;
  stats?: SystemStats | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  onRunPipeline,
  isLoading,
  activeView,
  setActiveView,
  stats,
}) => {
  const totalEvents = stats?.events?.total_events;
  const incidentCount = stats?.incidents?.total;

  const navItems = [
    { id: 'dashboard', label: 'Overview', icon: Shield, keynum: '1' },
    { id: 'incidents', label: 'Incident Workbench', icon: Cpu, badge: incidentCount !== undefined ? `${incidentCount}` : undefined, keynum: '2' },
    { id: 'graph', label: 'Correlation Graph', icon: Network, keynum: '3' },
    { id: 'logs', label: 'Log Explorer', icon: Terminal, badge: totalEvents ? `${totalEvents}` : undefined, keynum: '4' },
    { id: 'errors', label: 'Quarantine & Audit', icon: AlertOctagon, badge: stats?.events?.ingestion_errors ? `${stats.events.ingestion_errors}` : undefined, keynum: '5' },
  ];

  return (
    <header
      style={{
        background: 'var(--bg-header)',
        borderBottom: '1px solid var(--border-default)',
        padding: '0 16px',
        height: '46px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        zIndex: 40,
      }}
    >
      {/* Brand & System Indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '24px',
              height: '24px',
              borderRadius: 'var(--radius-xs)',
              background: '#0284c7',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
            }}
          >
            <Activity size={14} strokeWidth={2.5} />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span style={{ fontWeight: 800, fontSize: '0.88rem', letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
              PS3<span style={{ color: '#38bdf8' }}>::OPS</span>
            </span>
            <span className="text-xs" style={{ color: 'var(--text-dim)', fontWeight: 500 }}>
              v1.0
            </span>
          </div>
        </div>

        {/* Nodes Health Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            paddingLeft: '12px',
            borderLeft: '1px solid var(--border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
              NODE_A • NODE_B • NODE_C
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Segmented Tabs */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: '2px', background: 'var(--bg-canvas)', padding: '2px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px',
                borderRadius: 'var(--radius-xs)',
                border: 'none',
                background: isActive ? 'var(--bg-surface-elevated)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.78rem',
                cursor: 'pointer',
                transition: 'all 0.1s ease',
                boxShadow: isActive ? '0 1px 2px rgba(0,0,0,0.3)' : 'none',
              }}
            >
              <Icon size={13} color={isActive ? '#38bdf8' : 'currentColor'} />
              <span>{item.label}</span>
              {item.badge && (
                <span
                  className="font-mono"
                  style={{
                    fontSize: '0.68rem',
                    padding: '1px 5px',
                    borderRadius: 'var(--radius-xs)',
                    background: isActive ? 'rgba(56, 189, 248, 0.18)' : 'rgba(148, 163, 184, 0.1)',
                    color: isActive ? '#38bdf8' : 'var(--text-dim)',
                  }}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Action Area */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <button
          className="btn-ops btn-ops-secondary"
          onClick={onRunPipeline}
          disabled={isLoading}
          style={{ fontSize: '0.75rem', padding: '4px 9px' }}
          title="Re-run full ingestion and deterministic correlation pipeline"
        >
          <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          <span>{isLoading ? 'Ingesting...' : 'Ingest & Correlate'}</span>
        </button>
      </div>
    </header>
  );
};
