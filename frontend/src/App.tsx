import React, { useState, useEffect } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Dashboard } from './pages/Dashboard';
import { IncidentsPage } from './pages/IncidentsPage';
import { LogExplorer } from './pages/LogExplorer';
import { CorrelationView } from './pages/CorrelationView';
import { ErrorsPage } from './pages/ErrorsPage';
import { api, EventFilterParams } from './services/api';
import { NormalizedEvent, Incident, IngestionError, EventRelationship, Evidence, SystemStats } from './types';
import { AlertTriangle, RefreshCw, Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<string>('dashboard');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Core state
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [events, setEvents] = useState<NormalizedEvent[]>([]);
  const [errors, setErrors] = useState<IngestionError[]>([]);
  const [relationships, setRelationships] = useState<EventRelationship[]>([]);
  const [graphData, setGraphData] = useState<any>(null);

  // Active selection
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<NormalizedEvent | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence[]>([]);

  // Explorer filters
  const [filters, setFilters] = useState<EventFilterParams>({ limit: 500 });

  const loadAllData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Load Stats
      const statsRes = await api.getStats().catch(() => null);
      setStats(statsRes);

      // 2. Load Incidents
      const incRes = await api.getIncidents();
      setIncidents(incRes.incidents);
      if (incRes.incidents.length > 0 && !selectedIncident) {
        setSelectedIncident(incRes.incidents[0]);
      }

      // 3. Load Events
      const evRes = await api.getEvents(filters);
      setEvents(evRes.events);

      // 4. Load Errors
      const errRes = await api.getIngestionErrors();
      setErrors(errRes.errors);

      // 5. Load Relationships & Graph
      const relRes = await api.getRelationships();
      setRelationships(relRes.relationships);

      const graphRes = await api.getGraph();
      setGraphData(graphRes);
    } catch (err: any) {
      setError(err.message || 'Failed to communicate with backend');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, []);

  const handleRunPipeline = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api.runPipeline(true, 10.0);
      await loadAllData();
    } catch (err: any) {
      setError(err.message || 'Pipeline execution failed');
      setIsLoading(false);
    }
  };

  const handleSelectEvent = async (event: NormalizedEvent) => {
    setSelectedEvent(event);
    try {
      const detail = await api.getEventDetail(event.event_id);
      setSelectedEvidence(detail.evidence);
    } catch (err) {
      setSelectedEvidence([]);
    }
  };

  const handleSelectEventById = async (id: string) => {
    try {
      const detail = await api.getEventDetail(id);
      setSelectedEvent(detail.event);
      setSelectedEvidence(detail.evidence);
    } catch (err) {
      console.error(err);
    }
  };

  const handleFilterChange = async (newFilters: EventFilterParams) => {
    setFilters(newFilters);
    try {
      const evRes = await api.getEvents(newFilters);
      setEvents(evRes.events);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-canvas)' }}>
      {/* Top Navigation Bar */}
      <Navbar
        onRunPipeline={handleRunPipeline}
        isLoading={isLoading}
        activeView={activeView}
        setActiveView={setActiveView}
        stats={stats}
      />

      {/* Global Error Notice */}
      {error && (
        <div
          style={{
            margin: '12px 16px 0 16px',
            padding: '10px 16px',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--status-critical-bg)',
            border: '1px solid var(--status-critical-border)',
            color: 'var(--status-critical)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={15} />
            <span>{error}</span>
          </div>
          <button className="btn-ops btn-ops-secondary" onClick={loadAllData} style={{ padding: '2px 8px', fontSize: '0.72rem' }}>
            Retry
          </button>
        </div>
      )}

      {/* View Router */}
      <main style={{ flex: 1, minHeight: 0 }}>
        {activeView === 'dashboard' && (
          <Dashboard
            stats={stats}
            incidents={incidents}
            onSelectIncident={(id) => {
              const inc = incidents.find((i) => i.incident_id === id);
              if (inc) setSelectedIncident(inc);
              setActiveView('incidents');
            }}
            onNavigate={setActiveView}
          />
        )}

        {activeView === 'incidents' && (
          <IncidentsPage
            incidents={incidents}
            selectedIncident={selectedIncident}
            onSelectIncident={setSelectedIncident}
            events={events}
            relationships={relationships}
            selectedEvent={selectedEvent}
            selectedEvidence={selectedEvidence}
            onSelectEvent={handleSelectEvent}
            onSelectEventById={handleSelectEventById}
          />
        )}

        {activeView === 'graph' && (
          <CorrelationView
            graphData={graphData}
            relationships={relationships}
            events={events}
            selectedEvent={selectedEvent}
            selectedEvidence={selectedEvidence}
            onSelectEvent={handleSelectEvent}
            onSelectEventById={handleSelectEventById}
          />
        )}

        {activeView === 'logs' && (
          <LogExplorer
            events={events}
            filters={filters}
            onFilterChange={handleFilterChange}
            onResetFilters={() => handleFilterChange({ limit: 500 })}
            selectedEvent={selectedEvent}
            selectedEvidence={selectedEvidence}
            relationships={relationships}
            onSelectEvent={handleSelectEvent}
            onSelectEventById={handleSelectEventById}
          />
        )}

        {activeView === 'errors' && <ErrorsPage errors={errors} />}
      </main>
    </div>
  );
};
