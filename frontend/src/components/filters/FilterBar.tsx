import React from 'react';
import { Filter, Search, X, RotateCcw } from 'lucide-react';
import { EventFilterParams } from '../../services/api';

interface FilterBarProps {
  filters: EventFilterParams;
  onChange: (filters: EventFilterParams) => void;
  onReset: () => void;
}

export const FilterBar: React.FC<FilterBarProps> = ({ filters, onChange, onReset }) => {
  const updateFilter = (key: keyof EventFilterParams, value: any) => {
    onChange({
      ...filters,
      [key]: value === '' ? undefined : value,
    });
  };

  const hasActiveFilters = Object.entries(filters).some(
    ([k, v]) => v !== undefined && v !== '' && k !== 'limit' && k !== 'offset'
  );

  return (
    <div className="ops-panel" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#38bdf8', fontSize: '0.78rem', fontWeight: 700 }}>
        <Filter size={13} />
        <span style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}>Filter:</span>
      </div>

      {/* Free Search */}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <Search size={12} style={{ position: 'absolute', left: '7px', color: 'var(--text-dim)' }} />
        <input
          type="text"
          placeholder="Search logs / ID / message..."
          value={filters.search || ''}
          onChange={(e) => updateFilter('search', e.target.value)}
          className="ops-input"
          style={{ paddingLeft: '24px', fontSize: '0.75rem', width: '200px' }}
        />
        {filters.search && (
          <button
            onClick={() => updateFilter('search', '')}
            style={{ position: 'absolute', right: '6px', background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}
          >
            <X size={11} />
          </button>
        )}
      </div>

      {/* Node Select */}
      <select
        value={filters.node || ''}
        onChange={(e) => updateFilter('node', e.target.value)}
        className="ops-select"
        style={{ fontSize: '0.75rem' }}
      >
        <option value="">All Nodes</option>
        <option value="NODE_A">NODE_A</option>
        <option value="NODE_B">NODE_B</option>
        <option value="NODE_C">NODE_C</option>
      </select>

      {/* Log Family */}
      <select
        value={filters.log_family || ''}
        onChange={(e) => updateFilter('log_family', e.target.value)}
        className="ops-select"
        style={{ fontSize: '0.75rem' }}
      >
        <option value="">All Families</option>
        <option value="operator">operator</option>
        <option value="planning">planning</option>
        <option value="guidance">guidance</option>
        <option value="state">state</option>
        <option value="fault_recovery">fault_recovery</option>
      </select>

      {/* Category */}
      <select
        value={filters.category || ''}
        onChange={(e) => updateFilter('category', e.target.value)}
        className="ops-select"
        style={{ fontSize: '0.75rem' }}
      >
        <option value="">All Categories</option>
        <option value="FAULT">FAULT</option>
        <option value="RECOVERY">RECOVERY</option>
        <option value="COMMAND">COMMAND</option>
        <option value="MESSAGE">MESSAGE</option>
        <option value="STATE_CHANGE">STATE_CHANGE</option>
        <option value="GUIDANCE">GUIDANCE</option>
        <option value="SYSTEM">SYSTEM</option>
      </select>

      {/* Severity */}
      <select
        value={filters.severity || ''}
        onChange={(e) => updateFilter('severity', e.target.value)}
        className="ops-select"
        style={{ fontSize: '0.75rem' }}
      >
        <option value="">All Severities</option>
        <option value="CRITICAL">CRITICAL</option>
        <option value="ERROR">ERROR</option>
        <option value="WARN">WARN</option>
        <option value="INFO">INFO</option>
        <option value="DEBUG">DEBUG</option>
      </select>

      {/* Reset */}
      {hasActiveFilters && (
        <button
          className="btn-ops btn-ops-ghost"
          onClick={onReset}
          style={{ fontSize: '0.74rem', padding: '3px 7px', color: '#f87171' }}
          title="Reset all active filters"
        >
          <RotateCcw size={11} /> Reset
        </button>
      )}
    </div>
  );
};
