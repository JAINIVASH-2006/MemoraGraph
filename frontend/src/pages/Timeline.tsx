import { useState, useEffect } from 'react';
import { Clock, Calendar, Bookmark, AlertCircle } from 'lucide-react';
import { getTimeline } from '../services/api';
import type { TimelineEvent } from '../types';

const EVENT_TYPE_COLORS: Record<string, { bg: string; border: string; dot: string; label: string }> = {
  Project:  { bg: 'rgba(99,102,241,0.08)',  border: 'rgba(99,102,241,0.2)',  dot: 'var(--color-accent)',   label: 'Project' },
  Risk:     { bg: 'rgba(244,63,94,0.08)',   border: 'rgba(244,63,94,0.2)',   dot: 'var(--color-rose)',     label: 'Risk' },
  Decision: { bg: 'rgba(59,130,246,0.08)',  border: 'rgba(59,130,246,0.2)',  dot: 'var(--color-blue)',     label: 'Decision' },
  Meeting:  { bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)',  dot: 'var(--color-emerald)',  label: 'Meeting' },
  Outcome:  { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)',  dot: 'var(--color-amber)',    label: 'Outcome' },
  Event:    { bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.2)',  dot: 'var(--color-purple)',   label: 'Event' },
};

const getTypeStyle = (type: string) => EVENT_TYPE_COLORS[type] || EVENT_TYPE_COLORS['Event'];

export default function Timeline() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTimeline()
      .then(data => setEvents([...data].sort((a, b) => a.date.localeCompare(b.date))))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Clock size={26} style={{ color: 'var(--color-accent)' }} />
            Organizational Memory Timeline
          </h1>
          <p className="page-description">Chronological sequence of extracted events, risks, decisions, and outcomes</p>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '80px 0', textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>Reconstructing history timeline...</p>
        </div>
      ) : events.length === 0 ? (
        <div className="placeholder-page">
          <div className="placeholder-icon"><AlertCircle size={32} /></div>
          <h2 className="placeholder-title">No timeline events yet</h2>
          <p className="placeholder-text">Timeline is populated automatically when documents are uploaded and processed. Upload organizational reports to extract events.</p>
        </div>
      ) : (
        <div style={{ position: 'relative', paddingLeft: 28 }}>
          {/* Vertical line */}
          <div style={{ position: 'absolute', left: 7, top: 8, bottom: 8, width: 2, background: 'var(--color-border)', borderRadius: 2 }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {events.map((event) => {
              const style = getTypeStyle(event.entity_type);
              return (
                <div key={event.id} style={{ position: 'relative', display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {/* Timeline dot */}
                  <div style={{
                    position: 'absolute', left: -24, top: 14,
                    width: 14, height: 14, borderRadius: '50%',
                    background: 'var(--color-bg-card)',
                    border: `3px solid ${style.dot}`,
                    boxShadow: `0 0 0 3px rgba(255,255,255,0.8)`,
                    transition: 'transform 0.15s',
                  }} />

                  {/* Event Card */}
                  <div
                    className="card"
                    style={{ borderLeft: `3px solid ${style.dot}`, transition: 'all 0.15s' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.transform = 'translateX(3px)'; (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-md)'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = 'none'; (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-sm)'; }}
                  >
                    <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: style.dot }}>
                          <Calendar size={13} /> {event.date}
                        </span>
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 999,
                          background: style.bg, color: style.dot, border: `1px solid ${style.border}`,
                          textTransform: 'uppercase', letterSpacing: '0.06em',
                        }}>
                          {event.entity_type}
                        </span>
                      </div>
                      <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)' }}>{event.title}</h2>
                      <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>{event.description}</p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--color-text-muted)', paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
                        <Bookmark size={11} />
                        <span>Entity Ref: <code style={{ fontFamily: 'monospace', fontSize: 10 }}>{event.entity_id}</code></span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
