import { useEffect, useState } from 'react';
import {
  FileText,
  Share2,
  MessageSquare,
  AlertTriangle,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Brain,
  TrendingUp,
} from 'lucide-react';
import { checkHealth, getAnalyticsOverview, type HealthStatus } from '../services/api';
import type { AnalyticsOverview } from '../types';

interface StatCard {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
  color: string;
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const healthData = await checkHealth();
        setHealth(healthData);
        setHealthError(null);
      } catch (err: any) {
        setHealthError(err?.response?.data?.detail || 'Backend unreachable');
      }

      try {
        const overviewData = await getAnalyticsOverview();
        setOverview(overviewData);
      } catch {
        // Overview may be empty or awaiting documents/db
      } finally {
        setLoading(false);
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const stats: StatCard[] = [
    { 
      label: 'Documents', 
      value: overview ? overview.total_documents : 0, 
      icon: <FileText size={24} />, 
      trend: overview && overview.total_documents > 0 ? `${overview.total_documents} uploaded files` : 'Upload documents to begin', 
      color: 'var(--color-blue)' 
    },
    { 
      label: 'Entities', 
      value: overview ? overview.total_entities : 0, 
      icon: <Share2 size={24} />, 
      trend: overview && overview.total_entities > 0 ? `${overview.total_entities} extracted nodes` : 'Knowledge graph empty', 
      color: 'var(--color-purple)' 
    },
    { 
      label: 'Queries', 
      value: overview ? overview.total_queries : 0, 
      icon: <MessageSquare size={24} />, 
      trend: overview && overview.total_queries > 0 ? `${overview.total_queries} queries executed` : 'Ask your first question', 
      color: 'var(--color-emerald)' 
    },
    { 
      label: 'Active Risks', 
      value: overview ? overview.total_risks : 0, 
      icon: <AlertTriangle size={24} />, 
      trend: overview && overview.total_risks > 0 ? `${overview.total_risks} tracked hazards` : 'No risks tracked', 
      color: 'var(--color-amber)' 
    },
  ];

  const formatUptime = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-description">Organizational memory overview and system status</p>
        </div>
        <div className="header-badge">
          <Brain size={16} />
          <span>Intent-Routed Graph RAG</span>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        {stats.map((stat) => (
          <div key={stat.label} className="stat-card">
            <div className="stat-card-header">
              <span className="stat-card-label">{stat.label}</span>
              <div className="stat-card-icon" style={{ color: stat.color }}>
                {stat.icon}
              </div>
            </div>
            <div className="stat-card-value">{stat.value}</div>
            <div className="stat-card-trend">
              <TrendingUp size={14} />
              <span>{stat.trend}</span>
            </div>
          </div>
        ))}
      </div>

      {/* System Status + Pipeline */}
      <div className="dashboard-grid">
        {/* System Status Card */}
        <div className="card">
          <div className="card-header">
            <Activity size={20} />
            <h2 className="card-title">System Status</h2>
          </div>
          <div className="card-body">
            {loading ? (
              <div className="status-loading">
                <div className="spinner" />
                <span>Checking services...</span>
              </div>
            ) : healthError ? (
              <div className="status-error">
                <XCircle size={20} />
                <span>{healthError}</span>
              </div>
            ) : health ? (
              <div className="service-list">
                {Object.entries(health.services).map(([name, svc]) => (
                  <div key={name} className="service-item">
                    <div className="service-info">
                      {svc.status === 'up' ? (
                        <CheckCircle2 size={16} className="service-up" />
                      ) : (
                        <XCircle size={16} className="service-down" />
                      )}
                      <span className="service-name">{name}</span>
                    </div>
                    <span className={`service-badge service-badge-${svc.status === 'up' ? 'up' : 'down'}`}>
                      {svc.status}
                    </span>
                  </div>
                ))}
                <div className="service-meta">
                  <div className="service-meta-item">
                    <Clock size={14} />
                    <span>Uptime: {formatUptime(health.uptime_seconds)}</span>
                  </div>
                  <div className="service-meta-item">
                    <span>v{health.version}</span>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* Pipeline Overview Card */}
        <div className="card">
          <div className="card-header">
            <Brain size={20} />
            <h2 className="card-title">MemoraGraph Pipeline</h2>
          </div>
          <div className="card-body">
            <div className="pipeline">
              {[
                { label: 'Document Upload', status: 'ready' },
                { label: 'Text Extraction & Chunking', status: 'ready' },
                { label: 'Entity & Relationship Extraction', status: 'ready' },
                { label: 'Knowledge Graph (Neo4j)', status: 'ready' },
                { label: 'Vector Embeddings (Qdrant)', status: 'ready' },
                { label: 'Semantic Intent Classification', status: 'ready' },
                { label: 'Directed Edge-Routing', status: 'ready' },
                { label: 'Context Validation', status: 'ready' },
                { label: 'LLM Generation', status: 'ready' },
              ].map((step, i) => (
                <div key={i} className="pipeline-step">
                  <div className={`pipeline-dot pipeline-dot-${step.status}`} />
                  <span className="pipeline-label">{step.label}</span>
                  <span className={`pipeline-status pipeline-status-${step.status}`}>
                    {step.status === 'ready' ? 'Ready' : 'Phase ' + (Math.floor(i / 2) + 2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Quick Actions</h2>
        </div>
        <div className="card-body">
          <div className="quick-actions">
            <a href="/documents" className="quick-action-btn">
              <FileText size={20} />
              <span>Upload Document</span>
            </a>
            <a href="/assistant" className="quick-action-btn">
              <MessageSquare size={20} />
              <span>Ask a Question</span>
            </a>
            <a href="/graph" className="quick-action-btn">
              <Share2 size={20} />
              <span>Explore Graph</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
