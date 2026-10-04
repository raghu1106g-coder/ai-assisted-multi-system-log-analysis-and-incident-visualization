import React, { useState, useEffect } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Sidebar } from './components/layout/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { ImportDatasetPage } from './pages/ImportDatasetPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { TimelinePage } from './pages/TimelinePage';
import { OperationContextPage } from './pages/OperationContextPage';
import { LogExplorer } from './pages/LogExplorer';
import { CorrelationView } from './pages/CorrelationView';
import { SystemStatusPage } from './pages/SystemStatusPage';
import { api, EventFilterParams } from './services/api';
import {
  NormalizedEvent,
  Incident,
  IngestionError,
  EventRelationship,
  Evidence,
  SystemStats,
  DatasetInfo,
} from './types';
import { AlertTriangle, Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<string>('dashboard');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Available datasets & active selection
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDatasetPath, setSelectedDatasetPath] = useState<string>('');

  // Core state
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [events, setEvents] = useState<NormalizedEvent[]>([]);
  const [errors, setErrors] = useState<IngestionError[]>([]);
  const [relationships, setRelationships] = useState<EventRelationship[]>([]);
  const [graphData, setGraphData] = useState<any>(null);

  // Active investigation selection
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<NormalizedEvent | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence[]>([]);

  // Explorer filters
  const [filters, setFilters] = useState<EventFilterParams>({ limit: 500 });

  // Initial load: fetch dataset list & existing data
  const loadAllData = async (targetPath?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Load Datasets
      const dsetsRes = await api.getDatasets().catch(() => ({ datasets: [] }));
      setDatasets(dsetsRes.datasets);

      const activePath =
        targetPath ||
        selectedDatasetPath ||
        (dsetsRes.datasets.length > 0 ? dsetsRes.datasets[0].path : '');
      if (activePath && activePath !== selectedDatasetPath) {
        setSelectedDatasetPath(activePath);
      }

      // 2. Load Stats
      const statsRes = await api.getStats().catch(() => null);
      setStats(statsRes);

      // 3. Load Incidents
      const incRes = await api.getIncidents();
      setIncidents(incRes.incidents);
      if (incRes.incidents.length > 0) {
        setSelectedIncident((prev) => {
          if (prev && incRes.incidents.some((i) => i.incident_id === prev.incident_id)) {
            return incRes.incidents.find((i) => i.incident_id === prev.incident_id) || incRes.incidents[0];
          }
          return incRes.incidents[0];
        });
      }

      // 4. Load Events
      const evRes = await api.getEvents(filters);
      setEvents(evRes.events);

      // 5. Load Errors
      const errRes = await api.getIngestionErrors();
      setErrors(errRes.errors);

      // 6. Load Relationships & Graph
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

  const handleRunPipeline = async (path?: string) => {
    setIsLoading(true);
    setError(null);
    const targetPath = path || selectedDatasetPath;
    try {
      await api.runPipeline(targetPath, true, 10.0);
      await loadAllData(targetPath);
    } catch (err: any) {
      setError(err.message || 'Pipeline execution failed');
      setIsLoading(false);
    }
  };

  const handleSelectDataset = async (datasetPath: string) => {
    setSelectedDatasetPath(datasetPath);
    await handleRunPipeline(datasetPath);
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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-canvas)', overflow: 'hidden' }}>
      {/* Top Header Bar */}
      <Navbar
        onRunPipeline={() => handleRunPipeline()}
        isLoading={isLoading}
        datasets={datasets}
        selectedDataset={selectedDatasetPath}
        onSelectDataset={handleSelectDataset}
        stats={stats}
      />

      {/* Global Error Notice */}
      {error && (
        <div
          style={{
            margin: '0 18px',
            padding: '7px 14px',
            background: 'var(--status-critical-bg)',
            border: '1px solid var(--status-critical-border)',
            borderTop: 'none',
            color: 'var(--status-critical)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.78rem',
            borderRadius: '0 0 var(--radius-sm) var(--radius-sm)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <AlertTriangle size={14} />
            <span>{error}</span>
          </div>
          <button className="btn-ops btn-ops-secondary" onClick={() => loadAllData()} style={{ padding: '2px 8px', fontSize: '0.72rem' }}>
            Retry
          </button>
        </div>
      )}

      {/* Main Workspace Layout (Sidebar + Fluid Content) */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'hidden' }}>
        <Sidebar
          activeView={activeView}
          setActiveView={setActiveView}
          stats={stats}
        />

        <main style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {activeView === 'dashboard' && (
            <Dashboard
              stats={stats}
              incidents={incidents}
              events={events}
              onSelectIncident={(id) => {
                const inc = incidents.find((i) => i.incident_id === id);
                if (inc) setSelectedIncident(inc);
                setActiveView('incidents');
              }}
              onNavigate={setActiveView}
            />
          )}

          {activeView === 'import' && (
            <ImportDatasetPage
              datasets={datasets}
              selectedDatasetPath={selectedDatasetPath}
              onSelectDatasetPath={setSelectedDatasetPath}
              onRunPipeline={handleRunPipeline}
              isLoading={isLoading}
              errors={errors}
              stats={stats}
              onNavigateToIncidents={() => setActiveView('incidents')}
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

          {activeView === 'timeline' && (
            <TimelinePage
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

          {activeView === 'context' && (
            <OperationContextPage
              events={events}
              incidents={incidents}
              relationships={relationships}
              selectedEvent={selectedEvent}
              selectedEvidence={selectedEvidence}
              onSelectEvent={handleSelectEvent}
              onSelectEventById={handleSelectEventById}
            />
          )}

          {activeView === 'evidence' && (
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

          {activeView === 'status' && (
            <SystemStatusPage
              stats={stats}
              errors={errors}
              datasets={datasets}
              activeDatasetPath={selectedDatasetPath}
            />
          )}
        </main>
      </div>
    </div>
  );
};
