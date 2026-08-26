import axios from 'axios';
import type { User, Document, QueryResult, GraphNode, GraphEdge, TimelineEvent, AnalyticsOverview, EvaluationReport } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000,
});

// Request interceptor – attach JWT token if available
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('memoragraph_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor – handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('memoragraph_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// --- Health ---
export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  uptime_seconds: number;
  services: Record<string, { status: string }>;
}

export const checkHealth = async (): Promise<HealthStatus> => {
  const response = await api.get<HealthStatus>('/api/health');
  return response.data;
};

// --- Authentication ---
export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export const login = async (email: string, password: string): Promise<AuthResponse> => {
  const response = await api.post<AuthResponse>('/api/auth/login', { email, password });
  localStorage.setItem('memoragraph_token', response.data.access_token);
  return response.data;
};

export const register = async (email: string, password: string, name: string, role: string): Promise<AuthResponse> => {
  const response = await api.post<AuthResponse>('/api/auth/register', { email, password, name, role });
  localStorage.setItem('memoragraph_token', response.data.access_token);
  return response.data;
};

export const firebaseLoginSync = async (firebaseIdToken: string, name?: string, role?: string): Promise<AuthResponse> => {
  localStorage.setItem('memoragraph_token', firebaseIdToken);
  try {
    const response = await api.post<AuthResponse>('/api/auth/firebase-sync', { id_token: firebaseIdToken, name, role });
    if (response.data.access_token) {
      localStorage.setItem('memoragraph_token', response.data.access_token);
    }
    return response.data;
  } catch (err) {
    // If backend doesn't need additional token exchange, continue with firebaseIdToken
    return {
      access_token: firebaseIdToken,
      token_type: 'bearer',
      expires_in: 3600,
      user: { id: 'firebase-user', email: '', name: name || 'User', role: (role as any) || 'EMPLOYEE' }
    };
  }
};

export const getMe = async (): Promise<User> => {
  const response = await api.get<User>('/api/auth/me');
  return response.data;
};

export const logout = async () => {
  localStorage.removeItem('memoragraph_token');
  try {
    const { firebaseLogout } = await import('./firebase');
    await firebaseLogout();
  } catch {
    // ignore
  }
  window.location.href = '/login';
};

// --- Documents ---
export interface DocumentListResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
}

export const uploadDocument = async (file: File, department?: string, project?: string): Promise<any> => {
  const formData = new FormData();
  formData.append('file', file);
  if (department) formData.append('department', department);
  if (project) formData.append('project', project);

  const response = await api.post('/api/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getDocuments = async (query?: string, statusFilter?: string, page = 1, pageSize = 10): Promise<DocumentListResponse> => {
  const response = await api.get<DocumentListResponse>('/api/documents', {
    params: { query, status_filter: statusFilter, page, page_size: pageSize },
  });
  return response.data;
};

export const deleteDocument = async (id: string): Promise<void> => {
  await api.delete(`/api/documents/${id}`);
};

// --- Query Assistant ---
export const askQuestion = async (query: string, topK = 5): Promise<QueryResult> => {
  const response = await api.post<QueryResult>('/api/query', { query, top_k: topK });
  return response.data;
};

export interface HistoryItem {
  id: string;
  query_text: string;
  answer: string;
  intent: string;
  intent_confidence: number;
  answer_confidence: number;
  total_time_ms: number;
  created_at: string;
}

export const getQueryHistory = async (): Promise<HistoryItem[]> => {
  const response = await api.get<HistoryItem[]>('/api/query/history');
  return response.data;
};

export const submitFeedback = async (queryId: string, helpful: boolean, rating?: number, comment?: string): Promise<void> => {
  await api.post(`/api/query/feedback/${queryId}`, null, {
    params: { helpful, rating, comment },
  });
};

// --- Knowledge Graph ---
export interface NeighborResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const getGraphEntity = async (id: string): Promise<GraphNode> => {
  const response = await api.get<GraphNode>(`/api/graph/entity/${id}`);
  return response.data;
};

export const getGraphNeighbors = async (id: string, allowedRelations?: string): Promise<NeighborResponse> => {
  const response = await api.get<NeighborResponse>(`/api/graph/neighbors/${id}`, {
    params: { allowed_relations: allowedRelations },
  });
  return response.data;
};

export const searchGraphEntities = async (query: string, nodeTypes?: string[]): Promise<{ entities: GraphNode[] }> => {
  const response = await api.post<{ entities: GraphNode[] }>('/api/graph/search', { query, node_types: nodeTypes });
  return response.data;
};

// --- Timeline & Analytics ---
export const getTimeline = async (): Promise<TimelineEvent[]> => {
  const response = await api.get<TimelineEvent[]>('/api/timeline');
  return response.data;
};

export const getAnalyticsOverview = async (): Promise<AnalyticsOverview> => {
  const response = await api.get<AnalyticsOverview>('/api/analytics/overview');
  return response.data;
};

export const getEvaluationReport = async (): Promise<EvaluationReport> => {
  const response = await api.get<EvaluationReport>('/api/analytics/evaluation');
  return response.data;
};

export default api;
