// MemoraGraph – Shared TypeScript Types

export interface User {
  id: string;
  email: string;
  name: string;
  role: 'ADMIN' | 'MANAGER' | 'EMPLOYEE';
}

export interface Document {
  id: string;
  name: string;
  original_filename: string;
  file_type: string;
  status: 'UPLOADED' | 'PROCESSING' | 'PROCESSED' | 'FAILED';
  error_message?: string;
  chunk_count: number;
  entity_count: number;
  relationship_count: number;
  uploaded_at: string;
  metadata?: Record<string, string>;
}

export interface EvidenceItem {
  text: string;
  source_document_id: string;
  chunk_id: string;
  entities?: string[];
  relationships?: string[];
  path?: string[];
  score: number;
}

export interface RetrievalMetadata {
  vector_chunks_retrieved?: number;
  graph_nodes_retrieved?: number;
  graph_edges_traversed?: number;
  retrieval_time_ms?: number;
  generation_time_ms?: number;
  total_time_ms?: number;
  llm_model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  fallback_used?: boolean;
  [key: string]: unknown;
}

export interface QueryResult {
  query_id?: string;
  answer: string;
  sources: Source[];
  graph_paths: GraphPath[];
  evidence?: EvidenceItem[];
  confidence: number;
  intent: string;
  intent_confidence: number;
  retrieval_mode?: string;
  latency_ms?: number;
  retrieval_metadata: RetrievalMetadata;
}

export interface Source {
  document_id: string;
  document_name: string;
  chunk_id: string;
  text: string;
  score: number;
}

export interface GraphPath {
  nodes: GraphNode[];
  edges: GraphEdge[];
  description?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface AnalyticsOverview {
  total_documents: number;
  total_chunks?: number;
  total_entities: number;
  total_relationships: number;
  total_queries: number;
  total_projects: number;
  total_risks: number;
  total_decisions: number;
  avg_retrieval_time_ms: number;
}

export interface TimelineEvent {
  id: string;
  date: string;
  title: string;
  description: string;
  entity_type: string;
  entity_id: string;
}

export interface MetricStat {
  mean: number;
  std: number;
  ci_95: [number, number];
}

export interface EvaluationReport {
  available?: boolean;
  message?: string;
  dataset_type?: string;
  total_samples_evaluated?: number;
  mode?: string;
  metrics?: {
    'Precision@1'?: MetricStat;
    'Precision@5'?: MetricStat;
    'Recall@5'?: MetricStat;
    'F1@5'?: MetricStat;
    'PathPrecision@5'?: MetricStat;
    'IntentAccuracy'?: MetricStat;
    'TotalRetrievalLatency_ms'?: MetricStat;
    'VectorRetrievalLatency_ms'?: MetricStat;
    'GraphRetrievalLatency_ms'?: MetricStat;
    'AnswerRecall'?: MetricStat;
    'Latency_ms'?: MetricStat;
    [key: string]: MetricStat | undefined;
  };
  evaluation_timestamp?: string;
}
