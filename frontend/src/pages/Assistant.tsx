import { useState, useEffect, useRef } from 'react';
import type { FormEvent } from 'react';
import { Send, Brain, FileText, Share2, Sparkles, ThumbsUp, ThumbsDown, ChevronDown, ChevronRight, Layers } from 'lucide-react';
import { askQuestion, submitFeedback } from '../services/api';
import type { QueryResult, EvidenceItem } from '../types';

interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: Date;
  result?: QueryResult;
}

const EXAMPLE_QUESTIONS = [
  "Summarize the key decisions in the uploaded documents.",
  "What risks have been identified across projects?",
  "Who are the key stakeholders mentioned?",
  "What are the major project outcomes and timelines?",
];

export default function Assistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedResult, setSelectedResult] = useState<QueryResult | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Record<number, boolean>>({});
  const [expandedChunks, setExpandedChunks] = useState<Record<number, boolean>>({});
  const [expandedDocs, setExpandedDocs] = useState<Record<number, boolean>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    const queryText = input;
    setInput('');
    setLoading(true);

    try {
      const response = await askQuestion(queryText);
      const aiMsg: Message = {
        id: response.query_id || Date.now().toString(),
        sender: 'ai',
        text: response.answer,
        timestamp: new Date(),
        result: response,
      };
      setMessages((prev) => [...prev, aiMsg]);
      setSelectedResult(response);
      setExpandedPaths({});
      setExpandedChunks({});
      setExpandedDocs({});
    } catch (error: any) {
      const errMsg: Message = {
        id: Date.now().toString(),
        sender: 'ai',
        text: `Retrieval failed. ${error.response?.data?.detail || error.message}. Please check that backend services are active.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgId: string, helpful: boolean) => {
    try {
      await submitFeedback(msgId, helpful);
      alert('Thank you for your feedback!');
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

  const togglePath = (idx: number) => setExpandedPaths(prev => ({ ...prev, [idx]: !prev[idx] }));
  const toggleChunk = (idx: number) => setExpandedChunks(prev => ({ ...prev, [idx]: !prev[idx] }));
  const toggleDoc = (idx: number) => setExpandedDocs(prev => ({ ...prev, [idx]: !prev[idx] }));

  return (
    <div style={{ display: 'flex', flexDirection: 'row', height: 'calc(100vh - 80px)', padding: 0, background: 'var(--color-bg-secondary)' }}>
      {/* Chat Thread Panel */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--color-bg-card)', borderRight: '1px solid var(--color-border)' }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={20} style={{ color: 'var(--color-accent)' }} />
              AI Memory Assistant
            </h1>
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 2 }}>Intent-Routed Graph RAG Search</p>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {messages.length === 0 && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', gap: 16, padding: 32 }}>
              <div style={{ padding: 20, background: 'var(--color-bg-secondary)', borderRadius: '50%', color: 'var(--color-accent)', border: '1px solid var(--color-border)' }}>
                <Brain size={44} />
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>Query Organizational Memory</h2>
              <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', maxWidth: 380 }}>
                Ask about projects, timelines, risks, and approvals. MemoraGraph will route your question dynamically.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, maxWidth: 620, marginTop: 12 }}>
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    style={{
                      padding: '12px 16px',
                      background: 'var(--color-bg-secondary)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 12,
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: 13,
                      color: 'var(--color-text-primary)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-accent)'; (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-md)'; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--color-border)'; (e.currentTarget as HTMLElement).style.boxShadow = 'none'; }}
                  >
                    <Sparkles size={14} style={{ color: 'var(--color-accent)', marginTop: 2, flexShrink: 0 }} />
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{ display: 'flex', gap: 12, maxWidth: '80%', marginLeft: msg.sender === 'user' ? 'auto' : undefined, flexDirection: msg.sender === 'user' ? 'row-reverse' : 'row' }}
            >
              <div style={{
                padding: '12px 16px',
                borderRadius: msg.sender === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                fontSize: 13,
                lineHeight: 1.6,
                background: msg.sender === 'user' ? 'var(--color-accent)' : 'var(--color-bg-secondary)',
                color: msg.sender === 'user' ? '#fff' : 'var(--color-text-primary)',
                border: msg.sender === 'ai' ? '1px solid var(--color-border)' : 'none',
                boxShadow: 'var(--shadow-sm)',
              }}>
                {msg.text}

                {msg.sender === 'ai' && msg.result && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <button
                      onClick={() => setSelectedResult(msg.result!)}
                      style={{ fontSize: 12, color: 'var(--color-accent)', cursor: 'pointer', background: 'none', border: 'none', display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Brain size={12} /> Inspect Pipeline Evidence
                    </button>
                    <div style={{ display: 'flex', gap: 8, color: 'var(--color-text-muted)' }}>
                      <button onClick={() => handleFeedback(msg.id, true)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }} title="Helpful">
                        <ThumbsUp size={14} />
                      </button>
                      <button onClick={() => handleFeedback(msg.id, false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }} title="Not helpful">
                        <ThumbsDown size={14} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ display: 'flex', gap: 12, maxWidth: '80%' }}>
              <div style={{ padding: '14px 18px', background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: '18px 18px 18px 4px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 16, height: 16, border: '2px solid var(--color-accent)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                <div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-primary)' }}>Generating grounded answer...</p>
                  <p style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>Routing intent & executing Neo4j edge checks</p>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSend} style={{ padding: '16px 20px', background: 'var(--color-bg-card)', borderTop: '1px solid var(--color-border)', display: 'flex', gap: 10 }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about projects, employees, decisions, risks..."
            style={{
              flex: 1, padding: '12px 16px', background: 'var(--color-bg-input)', border: '1px solid var(--color-border)',
              borderRadius: 10, fontSize: 13, color: 'var(--color-text-primary)', outline: 'none', fontFamily: 'inherit',
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            style={{ padding: '12px 16px', background: 'var(--color-accent)', color: '#fff', border: 'none', borderRadius: 10, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.6 : 1 }}
          >
            <Send size={18} />
          </button>
        </form>
      </div>

      {/* Evidence Inspection Panel */}
      {selectedResult && (
        <div style={{ width: 440, background: 'var(--color-bg-card)', borderLeft: '1px solid var(--color-border)', overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <h2 style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-primary)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', alignItems: 'center', gap: 8, paddingBottom: 12, borderBottom: '1px solid var(--color-border)' }}>
            <Brain size={16} style={{ color: 'var(--color-accent)' }} /> Pipeline Grounding Inspector
          </h2>

          {/* Metadata */}
          <div style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { label: 'Query Intent', value: selectedResult.intent, highlight: true },
              { label: 'Classifier Confidence', value: `${(selectedResult.intent_confidence * 100).toFixed(0)}%` },
              { label: 'Retrieval Mode', value: selectedResult.retrieval_mode?.replace('_', ' ') || 'Intent Routed' },
              { label: 'Answer Groundedness', value: `${(selectedResult.confidence * 100).toFixed(0)}%`, green: true },
              ...(selectedResult.latency_ms !== undefined ? [{ label: 'Pipeline Latency', value: `${selectedResult.latency_ms.toFixed(0)} ms` }] : []),
            ].map((row, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 12 }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>{row.label}:</span>
                <span style={{
                  fontWeight: 600,
                  color: row.green ? 'var(--color-emerald)' : row.highlight ? 'var(--color-accent)' : 'var(--color-text-primary)',
                  background: row.highlight ? 'rgba(99,102,241,0.08)' : undefined,
                  padding: row.highlight ? '2px 8px' : undefined,
                  borderRadius: row.highlight ? 6 : undefined,
                  border: row.highlight ? '1px solid rgba(99,102,241,0.2)' : undefined,
                }}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>

          {/* Graph Paths */}
          <InspectSection title="Traversed Graph Paths" icon={<Share2 size={13} style={{ color: 'var(--color-accent)' }} />}>
            {selectedResult.graph_paths.length === 0 ? (
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No structured graph relationships traversed.</p>
            ) : selectedResult.graph_paths.map((p, i) => (
              <CollapsibleRow
                key={i}
                label={p.description ?? 'Graph Path'}
                isOpen={!!expandedPaths[i]}
                toggle={() => togglePath(i)}
              >
                <div style={{ fontSize: 11 }}>
                  <div style={{ color: 'var(--color-text-secondary)', fontWeight: 600, marginBottom: 6 }}>Constituent Nodes:</div>
                  {p.nodes.map((node, nIdx) => (
                    <div key={nIdx} style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--color-text-primary)', fontFamily: 'monospace', fontSize: 10, padding: '2px 4px' }}>
                      <span>{node.type}: <strong style={{ color: 'var(--color-accent)' }}>{node.label}</strong></span>
                    </div>
                  ))}
                </div>
              </CollapsibleRow>
            ))}
          </InspectSection>

          {/* Evidence Chunks */}
          <InspectSection title="Validated Evidence Chunks" icon={<Layers size={13} style={{ color: 'var(--color-accent)' }} />}>
            {!selectedResult.evidence?.length ? (
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No validated context chunks resolved.</p>
            ) : (selectedResult.evidence || []).map((ev: EvidenceItem, i: number) => (
              <CollapsibleRow
                key={i}
                label={ev.text.substring(0, 55) + '...'}
                sublabel={`Doc ID: ${ev.source_document_id}`}
                isOpen={!!expandedChunks[i]}
                toggle={() => toggleChunk(i)}
              >
                <p style={{ fontSize: 12, color: 'var(--color-text-primary)', lineHeight: 1.6, background: 'var(--color-bg-secondary)', padding: '10px 12px', borderRadius: 8 }}>{ev.text}</p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 11, color: 'var(--color-text-secondary)', marginTop: 6 }}>
                  <div><strong>Chunk ID:</strong> {ev.chunk_id}</div>
                  <div><strong>Score:</strong> {ev.score.toFixed(3)}</div>
                </div>
              </CollapsibleRow>
            ))}
          </InspectSection>

          {/* Source Documents */}
          <InspectSection title="Source Documents Cited" icon={<FileText size={13} style={{ color: 'var(--color-accent)' }} />}>
            {selectedResult.sources.length === 0 ? (
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>No source documents referenced.</p>
            ) : selectedResult.sources.map((s, i) => (
              <CollapsibleRow
                key={i}
                label={s.document_name}
                isOpen={!!expandedDocs[i]}
                toggle={() => toggleDoc(i)}
              >
                <div style={{ fontSize: 11, color: 'var(--color-text-primary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div><strong>Document ID:</strong> {s.document_id}</div>
                  <div><strong>Vector Match Score:</strong> {s.score.toFixed(4)}</div>
                </div>
              </CollapsibleRow>
            ))}
          </InspectSection>
        </div>
      )}
    </div>
  );
}

function InspectSection({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <h3 style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        {icon} {title}
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{children}</div>
    </div>
  );
}

function CollapsibleRow({ label, sublabel, isOpen, toggle, children }: { label: string; sublabel?: string; isOpen: boolean; toggle: () => void; children: React.ReactNode }) {
  return (
    <div style={{ border: '1px solid var(--color-border)', borderRadius: 8, overflow: 'hidden', background: 'var(--color-bg-secondary)' }}>
      <button
        onClick={toggle}
        style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 12px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
      >
        <div>
          <div style={{ fontSize: 12, color: 'var(--color-text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 310 }}>{label}</div>
          {sublabel && <div style={{ fontSize: 10, color: 'var(--color-text-muted)', marginTop: 2 }}>{sublabel}</div>}
        </div>
        {isOpen ? <ChevronDown size={14} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} /> : <ChevronRight size={14} style={{ color: 'var(--color-text-muted)', flexShrink: 0 }} />}
      </button>
      {isOpen && (
        <div style={{ padding: '10px 12px', borderTop: '1px solid var(--color-border)', background: 'var(--color-bg-card)' }}>
          {children}
        </div>
      )}
    </div>
  );
}
