import { useState } from 'react';
import { Brain, Eye, EyeOff } from 'lucide-react';
import { login } from '../services/api';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      window.location.href = '/';
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid email or password. Please make sure the seeder has been run.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">
            <Brain size={40} />
          </div>
          <h1 className="login-title">MEMORAGRAPH</h1>
          <p className="login-subtitle">Intent-Routed Organizational Memory</p>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && (
            <div className="p-2.5 text-xs bg-rose-950/50 text-rose-400 border border-rose-900/40 rounded mb-4 text-center">
              {error}
            </div>
          )}
          <div className="form-group">
            <label className="form-label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className="form-input"
              placeholder="you@organization.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">Password</label>
            <div className="input-with-icon">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="input-icon-btn"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading}
          >
            {loading ? (
              <><div className="spinner spinner-sm" /> Signing in...</>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <p className="login-footer">
          Organizational Intelligence Platform
        </p>
      </div>
    </div>
  );
}
