import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { TrendingUp, Activity, Database, CheckCircle, HelpCircle, Share2 } from 'lucide-react';
import { getAnalyticsOverview } from '../services/api';
import type { AnalyticsOverview } from '../types';

const COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b'];

export default function Analytics() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnalyticsOverview().then(setData).catch(console.error).finally(() => setLoading(false));
  }, []);

  const nodeStats = data ? [
    { name: 'Projects', count: data.total_projects },
    { name: 'Risks', count: data.total_risks },
    { name: 'Decisions', count: data.total_decisions },
  ] : [];

  const densityStats = data ? [
    { name: 'Documents', count: data.total_documents },
    { name: 'Entities', count: data.total_entities },
    { name: 'Relationships', count: data.total_relationships },
  ] : [];

  const summaryCards = data ? [
    { label: 'Total Chunks', value: data.total_documents * 5, icon: <Database size={20} />, color: 'var(--color-blue)' },
    { label: 'Avg Latency', value: `${data.avg_retrieval_time_ms} ms`, icon: <Activity size={20} />, color: 'var(--color-purple)' },
    { label: 'Active Projects', value: data.total_projects, icon: <CheckCircle size={20} />, color: 'var(--color-emerald)' },
    { label: 'Total Queries Run', value: data.total_queries, icon: <HelpCircle size={20} />, color: 'var(--color-amber)' },
  ] : [];

  if (loading) {
    return (
      <div className="page" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Computing system metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <TrendingUp size={26} style={{ color: 'var(--color-accent)' }} />
            MemoraGraph Metrics & Analytics
          </h1>
          <p className="page-description">Knowledge indexing coverage and retrieval latency</p>
        </div>
      </div>

      {!data ? (
        <div className="card">
          <div className="card-body" style={{ textAlign: 'center', padding: '40px' }}>
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Analytics dashboard unavailable. Check backend connections.</p>
          </div>
        </div>
      ) : (
        <>
          {/* Summary Stats */}
          <div className="stats-grid">
            {summaryCards.map((stat, i) => (
              <div key={i} className="stat-card">
                <div className="stat-card-header">
                  <span className="stat-card-label">{stat.label}</span>
                  <div className="stat-card-icon" style={{ color: stat.color }}>{stat.icon}</div>
                </div>
                <div className="stat-card-value" style={{ color: 'var(--color-text-primary)' }}>{stat.value}</div>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
            {/* Bar Chart */}
            <div className="card">
              <div className="card-header">
                <Share2 size={18} style={{ color: 'var(--color-accent)' }} />
                <h2 className="card-title">Graph Node Distribution</h2>
              </div>
              <div className="card-body">
                {nodeStats.every(s => s.count === 0) ? (
                  <EmptyChart message="No entities extracted yet. Upload and process documents to see graph node distribution." />
                ) : (
                  <div style={{ height: 240 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={nodeStats}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                        <XAxis dataKey="name" stroke="var(--color-text-muted)" fontSize={12} />
                        <YAxis stroke="var(--color-text-muted)" fontSize={12} />
                        <Tooltip
                          contentStyle={{ background: 'var(--color-bg-card)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-primary)' }}
                        />
                        <Bar dataKey="count" fill="var(--color-accent)" radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>

            {/* Pie Chart */}
            <div className="card">
              <div className="card-header">
                <Database size={18} style={{ color: 'var(--color-accent)' }} />
                <h2 className="card-title">Knowledge Ingest Density</h2>
              </div>
              <div className="card-body">
                {densityStats.every(s => s.count === 0) ? (
                  <EmptyChart message="No data ingested yet. Upload documents to see the knowledge density breakdown." />
                ) : (
                  <div style={{ height: 240 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={densityStats} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={4} dataKey="count">
                          {densityStats.map((_, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={{ background: 'var(--color-bg-card)', border: '1px solid var(--color-border)', borderRadius: 8 }} />
                        <Legend formatter={(value) => <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{value}</span>} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Academic Evaluation */}
          <div className="card">
            <div className="card-header">
              <TrendingUp size={18} style={{ color: 'var(--color-accent)' }} />
              <h2 className="card-title">Academic RAG Evaluation</h2>
            </div>
            <div className="card-body">
              <div style={{ background: 'var(--color-bg-secondary)', border: '1px dashed var(--color-border)', borderRadius: 10, padding: '32px', textAlign: 'center' }}>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>Evaluation data not available.</p>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 6 }}>
                  Run the evaluation CLI: <code style={{ background: 'var(--color-bg-card)', border: '1px solid var(--color-border)', borderRadius: 4, padding: '2px 6px', fontSize: 11 }}>python scripts/evaluate.py</code>
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div style={{ height: 240, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
      <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-accent)' }}>
        <TrendingUp size={22} />
      </div>
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', textAlign: 'center', maxWidth: 280 }}>{message}</p>
    </div>
  );
}
