import React from 'react';
import {
  LayoutDashboard,
  UploadCloud,
  Layers,
  Clock,
  Network,
  Compass,
  FileCode,
  Server,
} from 'lucide-react';
import { SystemStats } from '../../types';

interface SidebarProps {
  activeView: string;
  setActiveView: (view: string) => void;
  stats?: SystemStats | null;
}

const navItems = [
  {
    id: 'dashboard',
    label: 'Overview',
    icon: LayoutDashboard,
    desc: 'L1 System summary',
  },
  {
    id: 'import',
    label: 'Import Dataset',
    icon: UploadCloud,
    desc: 'Log ingestion pipeline',
    highlight: true,
  },
  {
    id: 'incidents',
    label: 'Incidents',
    icon: Layers,
    desc: 'L2 Fault workbench',
  },
  {
    id: 'timeline',
    label: 'Timeline',
    icon: Clock,
    desc: 'Cross-node event stream',
  },
  {
    id: 'graph',
    label: 'Correlation Graph',
    icon: Network,
    desc: 'Causal topology map',
  },
  {
    id: 'context',
    label: 'Op. Context',
    icon: Compass,
    desc: 'L3 System state',
  },
  {
    id: 'evidence',
    label: 'Evidence',
    icon: FileCode,
    desc: 'L4 Source provenance',
  },
  {
    id: 'status',
    label: 'System Status',
    icon: Server,
    desc: 'DB & parser diagnostics',
  },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeView,
  setActiveView,
  stats,
}) => {
  const incidentCount = stats?.incidents?.total || 0;
  const errorCount = stats?.events?.ingestion_errors || 0;
  const totalEvents = stats?.events?.total_events || 0;

  const getBadge = (id: string): string | undefined => {
    if (id === 'incidents' && incidentCount > 0) return String(incidentCount);
    if (id === 'status' && errorCount > 0) return String(errorCount);
    if (id === 'evidence' && totalEvents > 0) return totalEvents.toLocaleString();
    return undefined;
  };

  return (
    <aside
      style={{
        width: 'var(--sidebar-width)',
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        flexShrink: 0,
        zIndex: 30,
        height: '100%',
        overflowY: 'auto',
      }}
    >
      {/* Navigation */}
      <div style={{ padding: '10px 8px', display: 'flex', flexDirection: 'column', gap: '1px' }}>
        {/* Section label */}
        <div
          style={{
            padding: '6px 10px 8px 10px',
            fontSize: '0.62rem',
            fontWeight: 700,
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          Navigation
        </div>

        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          const badge = getBadge(item.id);
          const isError = item.id === 'status' && errorCount > 0;
          const isImport = item.id === 'import';

          return (
            <button
              key={item.id}
              className={`nav-item${isActive ? ' active' : ''}`}
              onClick={() => setActiveView(item.id)}
            >
              <Icon
                size={15}
                color={isActive ? 'var(--text-accent)' : isImport ? 'var(--text-accent)' : '#6B7468'}
                strokeWidth={isActive ? 2.2 : 1.8}
                style={{ flexShrink: 0 }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    lineHeight: 1.2,
                    fontWeight: isActive ? 600 : isImport ? 600 : 500,
                    color: isImport && !isActive ? 'var(--text-accent)' : undefined,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {item.label}
                </div>
                <div
                  style={{
                    fontSize: '0.62rem',
                    color: 'var(--text-dim)',
                    marginTop: '1px',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {item.desc}
                </div>
              </div>

              {badge && (
                <span
                  className="font-mono"
                  style={{
                    fontSize: '0.62rem',
                    padding: '1px 5px',
                    borderRadius: 'var(--radius-xs)',
                    background: isError
                      ? 'var(--status-critical-bg)'
                      : isActive
                      ? 'rgba(3,105,161,0.1)'
                      : 'var(--bg-surface-elevated)',
                    color: isError
                      ? 'var(--status-critical)'
                      : isActive
                      ? 'var(--text-accent)'
                      : 'var(--text-muted)',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer: Architecture level reference */}
      <div
        style={{
          padding: '12px',
          borderTop: '1px solid var(--border-subtle)',
          background: 'var(--bg-surface-subtle)',
        }}
      >
        <div
          style={{
            fontSize: '0.62rem',
            fontWeight: 700,
            color: 'var(--text-dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: '5px',
          }}
        >
          PS3 Level Coverage
        </div>
        {[
          { level: 'L1', label: 'Overview', view: 'dashboard' },
          { level: 'L2', label: 'Fault Detail', view: 'incidents' },
          { level: 'L3', label: 'Op. Context', view: 'context' },
          { level: 'L4', label: 'Evidence', view: 'evidence' },
        ].map(({ level, label, view }) => (
          <div
            key={level}
            onClick={() => setActiveView(view)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '2px 0',
              cursor: 'pointer',
            }}
          >
            <span
              className="font-mono"
              style={{
                fontSize: '0.6rem',
                fontWeight: 700,
                color: activeView === view ? 'var(--text-accent)' : 'var(--text-dim)',
                width: '18px',
              }}
            >
              {level}
            </span>
            <span
              style={{
                fontSize: '0.67rem',
                color: activeView === view ? 'var(--text-accent)' : 'var(--text-muted)',
                fontWeight: activeView === view ? 600 : 400,
              }}
            >
              {label}
            </span>
          </div>
        ))}
      </div>
    </aside>
  );
};
