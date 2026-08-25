import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { Upload, Trash2, Search, File, Loader, Database, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import { uploadDocument, getDocuments, deleteDocument } from '../services/api';
import type { Document } from '../types';

export default function Documents() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [department, setDepartment] = useState('');
  const [project, setProject] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const data = await getDocuments(query, undefined, 1, 100);
      setDocs(data.documents);
      setTotal(data.total);
    } catch (err) {
      console.error('Error fetching docs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocs(); }, [query]);

  // Auto-refresh when documents are PROCESSING or UPLOADED
  useEffect(() => {
    const isBusy = docs.some((d) => d.status === 'PROCESSING' || d.status === 'UPLOADED');
    if (!isBusy) return;

    const timer = setInterval(() => {
      fetchDocs();
    }, 2500);

    return () => clearInterval(timer);
  }, [docs]);

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    try {
      await uploadDocument(file, department || undefined, project || undefined);
      setFile(null);
      setDepartment('');
      setProject('');
      fetchDocs();
    } catch (err: any) {
      alert(`Upload failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this document? All vector indexes and graph nodes linked will be removed.')) return;
    try {
      await deleteDocument(id);
      fetchDocs();
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  };

  const statusConfig = (status: string) => {
    switch (status) {
      case 'PROCESSED': return { icon: <CheckCircle size={12} />, color: 'var(--color-emerald)', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)' };
      case 'PROCESSING': return { icon: <Loader size={12} className="animate-spin" />, color: 'var(--color-blue)', bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.2)' };
      case 'FAILED': return { icon: <AlertCircle size={12} />, color: 'var(--color-rose)', bg: 'rgba(244,63,94,0.08)', border: 'rgba(244,63,94,0.2)' };
      default: return { icon: <Clock size={12} />, color: 'var(--color-text-muted)', bg: 'var(--color-bg-secondary)', border: 'var(--color-border)' };
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Document Corpus Management</h1>
          <p className="page-description">Ingest organizational reports to index them into Graph RAG</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24, alignItems: 'start' }}>
        {/* Upload Form */}
        <div className="card">
          <div className="card-header">
            <Upload size={18} style={{ color: 'var(--color-accent)' }} />
            <h2 className="card-title">Ingest New Document</h2>
          </div>
          <div className="card-body">
            <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Drop Zone */}
              <div
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onClick={() => document.getElementById('file-input')?.click()}
                style={{
                  border: `2px dashed ${dragOver ? 'var(--color-accent)' : 'var(--color-border)'}`,
                  borderRadius: 12, padding: '28px 20px', textAlign: 'center', cursor: 'pointer',
                  background: dragOver ? 'rgba(99,102,241,0.04)' : 'var(--color-bg-secondary)',
                  transition: 'all 0.15s', position: 'relative',
                }}
              >
                <input id="file-input" type="file" onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} accept=".pdf,.docx,.txt,.csv,.json,.pptx,.md" style={{ display: 'none' }} />
                <File size={32} style={{ color: file ? 'var(--color-accent)' : 'var(--color-text-muted)', margin: '0 auto 10px' }} />
                <div style={{ fontSize: 13, color: file ? 'var(--color-text-primary)' : 'var(--color-text-secondary)', fontWeight: file ? 600 : 400 }}>
                  {file ? file.name : 'Click or drop file here'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>PDF, DOCX, TXT, CSV, JSON (Max 20MB)</div>
              </div>

              {/* Department Field */}
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  Target Department
                </label>
                <input
                  type="text"
                  placeholder="e.g. Engineering"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="form-input"
                />
              </div>

              {/* Project Field */}
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                  Target Project
                </label>
                <input
                  type="text"
                  placeholder="e.g. Q4 Strategy Report"
                  value={project}
                  onChange={(e) => setProject(e.target.value)}
                  className="form-input"
                />
              </div>

              <button type="submit" disabled={!file || uploading} className="btn btn-primary btn-full">
                {uploading ? (
                  <><Loader className="animate-spin" size={15} /> Ingesting Document...</>
                ) : 'Upload and Index'}
              </button>
            </form>
          </div>
        </div>

        {/* Document Table */}
        <div className="card">
          <div className="card-header" style={{ justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Database size={18} style={{ color: 'var(--color-accent)' }} />
              <h2 className="card-title">Document Database ({total})</h2>
            </div>
            <div style={{ position: 'relative', width: 240 }}>
              <input
                type="text"
                placeholder="Search files..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="form-input"
                style={{ paddingLeft: 36, height: 36, padding: '0 12px 0 36px', fontSize: 13 }}
              />
              <Search style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} size={14} />
            </div>
          </div>
          <div className="card-body">
            {loading ? (
              <div style={{ padding: '60px 0', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, color: 'var(--color-text-muted)', fontSize: 13 }}>
                <Loader className="animate-spin" size={18} /> Retrieving document directory...
              </div>
            ) : docs.length === 0 ? (
              <div style={{ padding: '60px 0', textAlign: 'center' }}>
                <div style={{ width: 60, height: 60, borderRadius: 16, background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', color: 'var(--color-accent)' }}>
                  <Database size={26} />
                </div>
                <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-text-primary)' }}>No documents indexed yet</p>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 4 }}>Upload your first document using the form on the left.</p>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                    {['Document Name', 'Status', 'Chunks', 'Entities', 'Edges', ''].map((h, i) => (
                      <th key={i} style={{ padding: '8px 12px', textAlign: i === 5 ? 'right' : 'left', fontSize: 11, fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {docs.map((doc) => {
                    const s = statusConfig(doc.status);
                    return (
                      <tr key={doc.id} style={{ borderBottom: '1px solid var(--color-border)' }}
                        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'var(--color-bg-secondary)'}
                        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
                      >
                        <td style={{ padding: '14px 12px' }}>
                          <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{doc.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 2 }}>{doc.original_filename}</div>
                        </td>
                        <td style={{ padding: '14px 12px' }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>
                            {s.icon} {doc.status}
                          </span>
                        </td>
                        <td style={{ padding: '14px 12px', fontWeight: 600, color: 'var(--color-text-primary)' }}>{doc.chunk_count}</td>
                        <td style={{ padding: '14px 12px', fontWeight: 600, color: 'var(--color-accent)' }}>{doc.entity_count}</td>
                        <td style={{ padding: '14px 12px', fontWeight: 600, color: 'var(--color-accent)' }}>{doc.relationship_count}</td>
                        <td style={{ padding: '14px 12px', textAlign: 'right' }}>
                          <button
                            onClick={() => handleDelete(doc.id)}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 6, borderRadius: 6, color: 'var(--color-text-muted)', transition: 'color 0.15s' }}
                            onMouseEnter={e => (e.currentTarget as HTMLElement).style.color = 'var(--color-rose)'}
                            onMouseLeave={e => (e.currentTarget as HTMLElement).style.color = 'var(--color-text-muted)'}
                            title="Delete document"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
