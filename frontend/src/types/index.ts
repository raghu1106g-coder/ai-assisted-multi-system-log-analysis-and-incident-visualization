export interface NormalizedEvent {
  event_id: string;
  schema_version: number;
  node: string;
  log_family: string;
  event_type: string;
  category?: string;
  severity?: string;
  timestamp: string;
  timestamp_precision?: string;
  component?: string;
  entity?: string;
  message?: string;
  incident_hint?: string;
  attributes?: Record<string, any>;
  source_file: string;
  source_line: number;
  raw_record: string;
}

export interface IngestionError {
  id: number;
  run_id: string;
  source_file: string;
  source_line: number;
  reason: string;
  raw_record?: string;
  log_family?: string;
  node?: string;
}

export interface EventRelationship {
  relationship_id: string;
  source_event_id: string;
  target_event_id: string;
  relationship_type: string;
  strength: 'STRONG' | 'MEDIUM' | 'WEAK' | 'HYPOTHETICAL';
  reason: string;
  supporting_evidence?: Record<string, any>;
  temporal_window_s?: number;
  confidence: number;
}

export interface MissingEvent {
  expected_type: string;
  expected_node: string;
  context: string;
  time_window?: string;
  confidence: string;
}

export interface Incident {
  incident_id: string;
  kind: 'INCIDENT' | 'NON_INCIDENT_NORMAL_OPERATION' | 'INCIDENT_CANDIDATE';
  title: string;
  description: string;
  start_time: string;
  end_time: string;
  involved_nodes: string[];
  involved_families: string[];
  primary_faults: string[];
  recovery_codes: string[];
  event_ids: string[];
  relationship_ids: string[];
  evidence_ids: string[];
  recovery_status?: string;
  missing_events: MissingEvent[];
  uncertainty_findings: string[];
}

export interface Evidence {
  evidence_id: string;
  event_id: string;
  source_file: string;
  source_line: number;
  raw_record: string;
  normalized_summary: string;
  relationship_to_finding: string;
  finding_type: string;
}

export interface AIObservation {
  statement: string;
  uncertainty_label: string;
  evidence_refs: string[];
}

export interface AIRelationship {
  description: string;
  uncertainty_label: string;
  evidence_refs: string[];
}

export interface AIUncertainty {
  description: string;
  label: string;
}

export interface AIIncidentNarrative {
  incident_summary: string;
  observations: AIObservation[];
  supported_relationships: AIRelationship[];
  possible_relationships: AIRelationship[];
  uncertainties: AIUncertainty[];
  recovery_summary: string;
  evidence_refs: string[];
  validation_passed: boolean;
  raw_ai_response?: string;
}

export interface SystemStats {
  events: {
    total_events: number;
    by_node: Record<string, number>;
    by_family: Record<string, number>;
    by_category: Record<string, number>;
    time_range: {
      start: string | null;
      end: string | null;
    };
    ingestion_errors: number;
  };
  incidents: {
    total: number;
    by_kind: Record<string, number>;
  };
  relationships: {
    total: number;
  };
}

export interface DatasetInfo {
  id: string;
  name: string;
  path: string;
  exists: boolean;
  files: string[];
  nodes: string[];
  log_families: string[];
  file_count: number;
}
