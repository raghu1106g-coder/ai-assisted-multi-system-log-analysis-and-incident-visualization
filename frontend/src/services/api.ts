import {
  NormalizedEvent,
  IngestionError,
  EventRelationship,
  Incident,
  Evidence,
  AIIncidentNarrative,
  SystemStats,
  DatasetInfo,
} from '../types';

const API_BASE = '/api/v1';

export interface EventFilterParams {
  node?: string;
  log_family?: string;
  event_type?: string;
  category?: string;
  severity?: string;
  incident_hint?: string;
  ts_from?: string;
  ts_to?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export const api = {
  async getEvents(params: EventFilterParams = {}): Promise<{ count: number; events: NormalizedEvent[] }> {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        query.append(key, String(value));
      }
    });
    const res = await fetch(`${API_BASE}/events?${query.toString()}`);
    if (!res.ok) throw new Error(`Failed to fetch events: ${res.statusText}`);
    return res.json();
  },

  async getEventDetail(eventId: string): Promise<{
    event: NormalizedEvent;
    evidence: Evidence[];
    relationships: EventRelationship[];
  }> {
    const res = await fetch(`${API_BASE}/events/${encodeURIComponent(eventId)}`);
    if (!res.ok) throw new Error(`Failed to fetch event detail: ${res.statusText}`);
    return res.json();
  },

  async getIngestionErrors(runId?: string, limit: number = 500): Promise<{ count: number; errors: IngestionError[] }> {
    const query = new URLSearchParams();
    if (runId) query.append('run_id', runId);
    query.append('limit', String(limit));
    const res = await fetch(`${API_BASE}/events/errors?${query.toString()}`);
    if (!res.ok) throw new Error(`Failed to fetch errors: ${res.statusText}`);
    return res.json();
  },

  async getIncidents(): Promise<{ count: number; incidents: Incident[] }> {
    const res = await fetch(`${API_BASE}/incidents`);
    if (!res.ok) throw new Error(`Failed to fetch incidents: ${res.statusText}`);
    return res.json();
  },

  async getIncidentDetail(incidentId: string): Promise<{
    incident: Incident;
    events: NormalizedEvent[];
    relationships: EventRelationship[];
    event_count: number;
    relationship_count: number;
  }> {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}`);
    if (!res.ok) throw new Error(`Failed to fetch incident detail: ${res.statusText}`);
    return res.json();
  },

  async generateNarrative(incidentId: string, maxEvents: number = 50): Promise<{
    incident_id: string;
    narrative: AIIncidentNarrative;
  }> {
    const res = await fetch(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/narrative`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_events: maxEvents }),
    });
    if (!res.ok) throw new Error(`Failed to generate narrative: ${res.statusText}`);
    return res.json();
  },

  async getRelationships(eventId?: string, type?: string, limit: number = 1000): Promise<{
    count: number;
    relationships: EventRelationship[];
  }> {
    const query = new URLSearchParams();
    if (eventId) query.append('event_id', eventId);
    if (type) query.append('relationship_type', type);
    query.append('limit', String(limit));
    const res = await fetch(`${API_BASE}/relationships?${query.toString()}`);
    if (!res.ok) throw new Error(`Failed to fetch relationships: ${res.statusText}`);
    return res.json();
  },

  async getGraph(incidentId?: string, limit: number = 1000): Promise<{
    nodes: any[];
    links: any[];
    node_count: number;
    link_count: number;
  }> {
    const query = new URLSearchParams();
    if (incidentId) query.append('incident_id', incidentId);
    query.append('limit', String(limit));
    const res = await fetch(`${API_BASE}/relationships/graph?${query.toString()}`);
    if (!res.ok) throw new Error(`Failed to fetch graph data: ${res.statusText}`);
    return res.json();
  },

  async getDatasets(): Promise<{ datasets: DatasetInfo[] }> {
    const res = await fetch(`${API_BASE}/pipeline/datasets`);
    if (!res.ok) throw new Error(`Failed to fetch datasets: ${res.statusText}`);
    return res.json();
  },

  async uploadDataset(formData: FormData): Promise<{ status: string; dataset: DatasetInfo; message: string }> {
    const res = await fetch(`${API_BASE}/pipeline/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Upload failed: ${res.statusText}`);
    }
    return res.json();
  },

  async runPipeline(dataRoot?: string, resetFirst: boolean = true, temporalWindowSeconds: number = 10.0): Promise<any> {
    const res = await fetch(`${API_BASE}/pipeline/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data_root: dataRoot || undefined,
        reset_first: resetFirst,
        temporal_window_seconds: temporalWindowSeconds,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Pipeline run failed: ${res.statusText}`);
    }
    return res.json();
  },

  async getStats(): Promise<SystemStats> {
    const res = await fetch(`${API_BASE}/stats`);
    if (!res.ok) throw new Error(`Failed to fetch stats: ${res.statusText}`);
    return res.json();
  },
};
