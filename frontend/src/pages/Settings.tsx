import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Shield, Server, User, Database, Share2, Key, Bell } from 'lucide-react';
import { getMe } from '../services/api';
import type { User as UserType } from '../types';

export default function Settings() {
  const [me, setMe] = useState<UserType | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMe().then(setMe).catch(console.error).finally(() => setLoading(false));
  }, []);

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <SettingsIcon size={26} style={{ color: 'var(--color-accent)' }} />
            System Settings & Profile
          </h1>
          <p className="page-description">Configure account preferences and view database endpoints</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 24 }}>
        {/* Profile Card */}
        <div className="card" style={{ height: 'fit-content' }}>
          <div className="card-header">
            <User size={18} style={{ color: 'var(--color-accent)' }} />
            <h2 className="card-title">User Profile</h2>
          </div>
          <div className="card-body">
            {loading ? (
              <div style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Loading profile...</div>
            ) : !me ? (
              <div style={{ fontSize: 13, color: 'var(--color-text-muted)', fontStyle: 'italic' }}>Profile unavailable</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                <ProfileField label="Full Name" value={me.name} large />
                <ProfileField label="Email Address" value={me.email} mono />
                <div>
                  <label style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 6 }}>System Role</label>
                  <span style={{
                    display: 'inline-flex', padding: '3px 12px', borderRadius: 999,
                    fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em',
                    background: 'rgba(99,102,241,0.1)', color: 'var(--color-accent)',
                    border: '1px solid rgba(99,102,241,0.25)',
                  }}>
                    {me.role}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Active Service Pipelines */}
          <div className="card">
            <div className="card-header">
              <Server size={18} style={{ color: 'var(--color-accent)' }} />
              <h2 className="card-title">Active Service Pipelines</h2>
            </div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                <ServiceTile
                  icon={<Database size={15} />}
                  label="Vector Database"
                  name="Qdrant Server"
                  detail="Collection: organizational_memory"
                />
                <ServiceTile
                  icon={<Share2 size={15} />}
                  label="Knowledge Graph"
                  name="Neo4j Database"
                  detail="Bolt Port: 7687"
                />
                <ServiceTile
                  icon={<Key size={15} />}
                  label="Embedding Model"
                  name="BAAI/bge-small-en"
                  detail="Dimension: 384"
                />
                <ServiceTile
                  icon={<Bell size={15} />}
                  label="LLM Provider"
                  name="Mock Provider"
                  detail="Offline mode active"
                />
              </div>
            </div>
          </div>

          {/* Access Control Policy */}
          <div className="card">
            <div className="card-header">
              <Shield size={18} style={{ color: 'var(--color-accent)' }} />
              <h2 className="card-title">Access Control Policy</h2>
            </div>
            <div className="card-body">
              <div style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 10, padding: 16 }}>
                <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.7 }}>
                  Role-Based Access Control (RBAC) is active. File management operations (uploading and deleting)
                  are restricted to users with{' '}
                  <strong style={{ color: 'var(--color-text-primary)' }}>ADMIN</strong>{' '}
                  or{' '}
                  <strong style={{ color: 'var(--color-text-primary)' }}>MANAGER</strong>{' '}
                  roles. Standard employees hold read-only query permissions.
                </p>
              </div>
              <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                {[
                  { role: 'ADMIN', perms: 'Full access' },
                  { role: 'MANAGER', perms: 'Upload & query' },
                  { role: 'EMPLOYEE', perms: 'Query only' },
                ].map(r => (
                  <div key={r.role} style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 8, padding: '12px 14px', textAlign: 'center' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-accent)', letterSpacing: '0.06em' }}>{r.role}</div>
                    <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>{r.perms}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ProfileField({ label, value, mono, large }: { label: string; value: string; mono?: boolean; large?: boolean }) {
  return (
    <div>
      <label style={{ fontSize: 10, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 4 }}>{label}</label>
      <span style={{ fontSize: large ? 16 : 13, fontWeight: large ? 600 : 400, color: 'var(--color-text-primary)', fontFamily: mono ? 'monospace' : 'inherit' }}>{value}</span>
    </div>
  );
}

function ServiceTile({ icon, label, name, detail }: { icon: React.ReactNode; label: string; name: string; detail: string }) {
  return (
    <div style={{ background: 'var(--color-bg-secondary)', border: '1px solid var(--color-border)', borderRadius: 10, padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--color-accent)', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
        {icon} {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-primary)' }}>{name}</div>
      <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 3 }}>{detail}</div>
    </div>
  );
}
