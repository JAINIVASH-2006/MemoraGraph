import { useState, useEffect } from 'react';
import { History, Calendar, Brain, Clock } from 'lucide-react';
import { getQueryHistory, type HistoryItem } from '../services/api';

export default function QueryHistory() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getQueryHistory().then(setHistory).catch(console.error).finally(() => setLoading(false));
  }, []);

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch { return iso; }
  };

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <History size={26} style={{ color: 'var(--color-accent)' }} />
            Query History
          </h1>
          <p className="page-description">Review past queries routed through organizational memory</p>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '80px 0', textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Loading history audit logs...</p>
        </div>
      ) : history.length === 0 ? (
        <div className="placeholder-page">
          <div className="placeholder-icon"><History size={32} /></div>
          <h2 className="placeholder-title">No query history yet</h2>
          <p className="placeholder-text">Submit questions in the AI Assistant page to build your query history log.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {history.map((item) => (
            <div key={item.id} className="card" style={{ transition: 'all 0.15s' }}>
              <div className="card-header" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--color-text-muted)' }}>
                  <Calendar size={13} /> {formatDate(item.created_at)}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    padding: '3px 12px', borderRadius: 999, fontSize: 11, fontWeight: 700,
                    background: 'rgba(99,102,241,0.08)', color: 'var(--color-accent)',
                    border: '1px solid rgba(99,102,241,0.2)',
                  }}>
                    Intent: {item.intent}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                    {(item.intent_confidence * 100).toFixed(0)}% Match
                  </span>
                </div>
              </div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, display: 'block', marginBottom: 6 }}>Question</span>
                  <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)', fontStyle: 'italic' }}>"{item.query_text}"</p>
                </div>
                <div>
                  <span style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, display: 'block', marginBottom: 6 }}>Grounded Answer</span>
                  <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.7, background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 10, padding: '12px 16px', whiteSpace: 'pre-wrap' }}>
                    {item.answer}
                  </p>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 12, borderTop: '1px solid var(--color-border)', fontSize: 12, color: 'var(--color-text-muted)' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Clock size={13} /> Pipeline latency: {item.total_time_ms ? `${item.total_time_ms.toFixed(0)} ms` : 'N/A'}
                  </span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-accent)', fontWeight: 600 }}>
                    <Brain size={13} /> Groundedness: {item.answer_confidence ? `${(item.answer_confidence * 100).toFixed(0)}%` : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
