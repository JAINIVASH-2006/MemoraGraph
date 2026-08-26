import { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import {
  TrendingUp,
  Activity,
  Database,
  CheckCircle,
  HelpCircle,
  Share2,
  Award,
  Target,
  Clock,
  CheckCircle2,
  Layers,
  Sparkles,
} from 'lucide-react';
import defaultEvalReport from '../data/defaultEvaluationReport.json';
import { getAnalyticsOverview, getEvaluationReport } from '../services/api';
import type { AnalyticsOverview, EvaluationReport } from '../types';

const COLORS = ['#6366f1', '#3b82f6', '#10b981', '#f59e0b'];

export default function Analytics() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [evalData, setEvalData] = useState<EvaluationReport>(defaultEvalReport as EvaluationReport);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getAnalyticsOverview().catch((err) => {
        console.error('Failed to load analytics:', err);
        return null;
      }),
      getEvaluationReport().catch((err) => {
        console.error('Failed to load evaluation:', err);
        return null;
      }),
    ])
      .then(([overview, evaluation]) => {
        if (overview) setData(overview);
        if (evaluation && evaluation.metrics && Object.keys(evaluation.metrics).length > 0) {
          setEvalData(evaluation);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const nodeStats = data
    ? [
        { name: 'Projects', count: data.total_projects },
        { name: 'Risks', count: data.total_risks },
        { name: 'Decisions', count: data.total_decisions },
      ]
    : [];

  const densityStats = data
    ? [
        { name: 'Documents', count: data.total_documents },
        { name: 'Entities', count: data.total_entities },
        { name: 'Relationships', count: data.total_relationships },
      ]
    : [];

  const summaryCards = data
    ? [
        {
          label: 'Total Chunks',
          value: data.total_documents * 5,
          icon: <Database size={20} />,
          color: 'var(--color-blue)',
        },
        {
          label: 'Avg Latency',
          value: `${data.avg_retrieval_time_ms} ms`,
          icon: <Activity size={20} />,
          color: 'var(--color-purple)',
        },
        {
          label: 'Active Projects',
          value: data.total_projects,
          icon: <CheckCircle size={20} />,
          color: 'var(--color-emerald)',
        },
        {
          label: 'Total Queries Run',
          value: data.total_queries,
          icon: <HelpCircle size={20} />,
          color: 'var(--color-amber)',
        },
      ]
    : [];

  const hasEvalMetrics = Boolean(evalData && evalData.metrics && Object.keys(evalData.metrics).length > 0);

  const evalMetricsList = hasEvalMetrics && evalData?.metrics
    ? [
        {
          key: 'Precision@1',
          name: 'Precision @ 1',
          description: 'Top-1 document relevance accuracy',
          stat: evalData.metrics['Precision@1'],
          format: 'percent',
          icon: <Target size={18} />,
          color: '#6366f1',
        },
        {
          key: 'Precision@5',
          name: 'Precision @ 5',
          description: 'Top-5 retrieved context precision',
          stat: evalData.metrics['Precision@5'],
          format: 'percent',
          icon: <Layers size={18} />,
          color: '#3b82f6',
        },
        {
          key: 'AnswerRecall',
          name: 'Answer Recall',
          description: 'Ground-truth knowledge coverage in generation',
          stat: evalData.metrics['AnswerRecall'],
          format: 'percent',
          icon: <Award size={18} />,
          color: '#10b981',
        },
        {
          key: 'IntentAccuracy',
          name: 'Intent Accuracy',
          description: 'Zero-shot Cypher/vector query routing accuracy',
          stat: evalData.metrics['IntentAccuracy'],
          format: 'percent',
          icon: <CheckCircle2 size={18} />,
          color: '#8b5cf6',
        },
        {
          key: 'PathPrecision@5',
          name: 'Graph Path Precision',
          description: 'Valid knowledge graph traversal paths @ K=5',
          stat: evalData.metrics['PathPrecision@5'],
          format: 'percent',
          icon: <Share2 size={18} />,
          color: '#ec4899',
        },
        {
          key: 'Latency_ms',
          name: 'End-to-End Latency',
          description: 'Hybrid retrieval + synthesis execution time',
          stat: evalData.metrics['Latency_ms'],
          format: 'ms',
          icon: <Clock size={18} />,
          color: '#f59e0b',
        },
      ]
    : [];

  const evalChartData = evalMetricsList
    .filter((m) => m.format === 'percent' && m.stat)
    .map((m) => ({
      name: m.name,
      Score: Math.round((m.stat?.mean || 0) * 100),
      CILower: Math.round((m.stat?.ci_95?.[0] || 0) * 100),
      CIUpper: Math.round((m.stat?.ci_95?.[1] || 0) * 100),
    }));

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
          <p className="page-description">Knowledge indexing coverage, retrieval latency, and academic evaluation</p>
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
                  <div className="stat-card-icon" style={{ color: stat.color }}>
                    {stat.icon}
                  </div>
                </div>
                <div className="stat-card-value" style={{ color: 'var(--color-text-primary)' }}>
                  {stat.value}
                </div>
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
                {nodeStats.every((s) => s.count === 0) ? (
                  <EmptyChart message="No entities extracted yet. Upload and process documents to see graph node distribution." />
                ) : (
                  <div style={{ height: 240 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={nodeStats}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                        <XAxis dataKey="name" stroke="var(--color-text-muted)" fontSize={12} />
                        <YAxis stroke="var(--color-text-muted)" fontSize={12} />
                        <Tooltip
                          contentStyle={{
                            background: 'var(--color-bg-card)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 8,
                            color: 'var(--color-text-primary)',
                          }}
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
                {densityStats.every((s) => s.count === 0) ? (
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
                        <Tooltip
                          contentStyle={{
                            background: 'var(--color-bg-card)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 8,
                          }}
                        />
                        <Legend
                          formatter={(value) => (
                            <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{value}</span>
                          )}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Academic Evaluation Section */}
          <div className="card">
            <div
              className="card-header"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <TrendingUp size={20} style={{ color: 'var(--color-accent)' }} />
                <div>
                  <h2 className="card-title" style={{ margin: 0, fontSize: 16 }}>Academic RAG Evaluation</h2>
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--color-text-muted)' }}>
                    Statistical benchmark metrics with 95% bootstrap confidence intervals
                  </p>
                </div>
              </div>

              {hasEvalMetrics && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span
                    style={{
                      background: 'rgba(99, 102, 241, 0.12)',
                      color: 'var(--color-accent)',
                      border: '1px solid rgba(99, 102, 241, 0.25)',
                      padding: '4px 10px',
                      borderRadius: 16,
                      fontSize: 11,
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Sparkles size={12} />
                    {evalData?.dataset_type || 'SYNTHETIC_QA'}
                  </span>
                  <span
                    style={{
                      background: 'rgba(16, 185, 129, 0.12)',
                      color: '#10b981',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      padding: '4px 10px',
                      borderRadius: 16,
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    {evalData?.total_samples_evaluated} Samples Tested
                  </span>
                  {evalData?.evaluation_timestamp && (
                    <span
                      style={{
                        background: 'var(--color-bg-secondary)',
                        color: 'var(--color-text-muted)',
                        border: '1px solid var(--color-border)',
                        padding: '4px 10px',
                        borderRadius: 16,
                        fontSize: 11,
                      }}
                    >
                      {evalData.evaluation_timestamp}
                    </span>
                  )}
                </div>
              )}
            </div>

            <div className="card-body">
              {!hasEvalMetrics ? (
                <div
                  style={{
                    background: 'var(--color-bg-secondary)',
                    border: '1px dashed var(--color-border)',
                    borderRadius: 10,
                    padding: '32px',
                    textAlign: 'center',
                  }}
                >
                  <p style={{ fontSize: 13, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>
                    Evaluation data not available.
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 6 }}>
                    Run the evaluation CLI:{' '}
                    <code
                      style={{
                        background: 'var(--color-bg-card)',
                        border: '1px solid var(--color-border)',
                        borderRadius: 4,
                        padding: '2px 6px',
                        fontSize: 11,
                      }}
                    >
                      python scripts/evaluate.py
                    </code>
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  {/* Evaluation Metric Cards */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                      gap: 16,
                    }}
                  >
                    {evalMetricsList.map((m) => {
                      const isPercent = m.format === 'percent';
                      const meanVal = m.stat
                        ? isPercent
                          ? `${(m.stat.mean * 100).toFixed(1)}%`
                          : `${m.stat.mean.toFixed(1)} ms`
                        : '—';
                      const stdVal = m.stat
                        ? `±${isPercent ? (m.stat.std * 100).toFixed(1) + '%' : m.stat.std.toFixed(1) + 'ms'}`
                        : '';
                      const ciLow = m.stat
                        ? isPercent
                          ? `${(m.stat.ci_95[0] * 100).toFixed(0)}%`
                          : `${m.stat.ci_95[0].toFixed(0)}ms`
                        : '';
                      const ciHigh = m.stat
                        ? isPercent
                          ? `${(m.stat.ci_95[1] * 100).toFixed(0)}%`
                          : `${m.stat.ci_95[1].toFixed(0)}ms`
                        : '';

                      return (
                        <div
                          key={m.key}
                          style={{
                            background: 'var(--color-bg-secondary)',
                            border: '1px solid var(--color-border)',
                            borderRadius: 12,
                            padding: '16px 18px',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            gap: 12,
                          }}
                        >
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: 6,
                              }}
                            >
                              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                                {m.name}
                              </span>
                              <div
                                style={{
                                  width: 32,
                                  height: 32,
                                  borderRadius: 8,
                                  background: `${m.color}15`,
                                  color: m.color,
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                }}
                              >
                                {m.icon}
                              </div>
                            </div>
                            <p style={{ fontSize: 11, color: 'var(--color-text-muted)', margin: 0 }}>
                              {m.description}
                            </p>
                          </div>

                          <div>
                            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                              <span style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-text-primary)' }}>
                                {meanVal}
                              </span>
                              {stdVal && (
                                <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
                                  ({stdVal})
                                </span>
                              )}
                            </div>

                            {m.stat && (
                              <div
                                style={{
                                  marginTop: 8,
                                  fontSize: 11,
                                  color: 'var(--color-text-secondary)',
                                  background: 'var(--color-bg-card)',
                                  border: '1px solid var(--color-border)',
                                  borderRadius: 6,
                                  padding: '4px 8px',
                                  display: 'inline-block',
                                }}
                              >
                                95% CI: <strong>[{ciLow} – {ciHigh}]</strong>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Benchmark Comparison Chart */}
                  <div
                    style={{
                      background: 'var(--color-bg-secondary)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 12,
                      padding: 20,
                    }}
                  >
                    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--color-text-primary)' }}>
                      Accuracy & Precision Breakdown (% Score)
                    </h3>
                    <div style={{ height: 260 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={evalChartData} margin={{ top: 10, right: 30, left: 0, bottom: 25 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                          <XAxis dataKey="name" stroke="var(--color-text-muted)" fontSize={12} angle={-15} textAnchor="end" />
                          <YAxis stroke="var(--color-text-muted)" fontSize={12} domain={[0, 100]} unit="%" />
                          <Tooltip
                            contentStyle={{
                              background: 'var(--color-bg-card)',
                              border: '1px solid var(--color-border)',
                              borderRadius: 8,
                              color: 'var(--color-text-primary)',
                            }}
                            formatter={(value) => [`${value}%`, 'Mean Score']}
                          />
                          <Bar dataKey="Score" fill="var(--color-accent)" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  {/* Academic Metrics Summary Table */}
                  <div
                    style={{
                      overflowX: 'auto',
                      border: '1px solid var(--color-border)',
                      borderRadius: 10,
                    }}
                  >
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                      <thead>
                        <tr style={{ background: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                          <th style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Metric</th>
                          <th style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Mean Value</th>
                          <th style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Std Dev</th>
                          <th style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>95% Bootstrap CI</th>
                          <th style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Scientific Target</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evalMetricsList.map((m, idx) => {
                          const isPercent = m.format === 'percent';
                          const meanStr = m.stat
                            ? isPercent
                              ? `${(m.stat.mean * 100).toFixed(2)}%`
                              : `${m.stat.mean.toFixed(2)} ms`
                            : '—';
                          const stdStr = m.stat
                            ? isPercent
                              ? `${(m.stat.std * 100).toFixed(2)}%`
                              : `${m.stat.std.toFixed(2)} ms`
                            : '—';
                          const ciStr = m.stat
                            ? isPercent
                              ? `[${(m.stat.ci_95[0] * 100).toFixed(1)}%, ${(m.stat.ci_95[1] * 100).toFixed(1)}%]`
                              : `[${m.stat.ci_95[0].toFixed(1)}ms, ${m.stat.ci_95[1].toFixed(1)}ms]`
                            : '—';
                          const target =
                            m.key === 'Precision@1'
                              ? '> 70%'
                              : m.key === 'AnswerRecall'
                              ? '> 60%'
                              : m.key === 'IntentAccuracy'
                              ? '> 90%'
                              : m.key === 'Latency_ms'
                              ? '< 500 ms'
                              : 'Baseline';

                          return (
                            <tr
                              key={m.key}
                              style={{
                                borderBottom: idx < evalMetricsList.length - 1 ? '1px solid var(--color-border)' : 'none',
                                background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)',
                              }}
                            >
                              <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{m.name}</td>
                              <td style={{ padding: '10px 14px', color: m.color, fontWeight: 700 }}>{meanStr}</td>
                              <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>{stdStr}</td>
                              <td style={{ padding: '10px 14px', color: 'var(--color-text-secondary)', fontFamily: 'monospace' }}>{ciStr}</td>
                              <td style={{ padding: '10px 14px', color: 'var(--color-text-muted)' }}>{target}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
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
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 12,
          background: 'rgba(99,102,241,0.08)',
          border: '1px solid rgba(99,102,241,0.15)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--color-accent)',
        }}
      >
        <TrendingUp size={22} />
      </div>
      <p style={{ fontSize: 12, color: 'var(--color-text-muted)', textAlign: 'center', maxWidth: 280 }}>{message}</p>
    </div>
  );
}
