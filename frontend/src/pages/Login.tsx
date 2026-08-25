import { useState } from 'react';
import { Brain, Eye, EyeOff } from 'lucide-react';
import { login, register, firebaseLoginSync } from '../services/api';
import {
  signInWithFirebaseEmail,
  registerWithFirebaseEmail,
  signInWithGoogle,
} from '../services/firebase';

export default function Login() {
  const [isRegistering, setIsRegistering] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('EMPLOYEE');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // 1. Try Firebase Authentication first if configured
      try {
        if (isRegistering) {
          const cred = await registerWithFirebaseEmail(email, password, name);
          const idToken = await cred.user.getIdToken();
          await firebaseLoginSync(idToken, name, role);
        } else {
          const cred = await signInWithFirebaseEmail(email, password);
          const idToken = await cred.user.getIdToken();
          await firebaseLoginSync(idToken, cred.user.displayName || undefined);
        }
        window.location.href = '/';
        return;
      } catch (fbErr: any) {
        // If Firebase auth throws (e.g. user exists in local DB or custom auth), fallback to local backend auth
        console.debug('Firebase auth fallback to local backend:', fbErr?.message);
        if (isRegistering) {
          await register(email, password, name, role);
        } else {
          await login(email, password);
        }
        window.location.href = '/';
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setGoogleLoading(true);
    setError(null);
    try {
      const cred = await signInWithGoogle();
      const idToken = await cred.user.getIdToken();
      await firebaseLoginSync(idToken, cred.user.displayName || 'Google User', 'MANAGER');
      window.location.href = '/';
    } catch (err: any) {
      console.error('Google Sign-In Error:', err);
      setError(err.message || 'Google Sign-In failed. Please ensure popup is allowed.');
    } finally {
      setGoogleLoading(false);
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

        {/* Google Sign-In Button */}
        <button
          type="button"
          onClick={handleGoogleSignIn}
          disabled={googleLoading || loading}
          className="w-full mb-4 py-2.5 px-4 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-100 rounded-lg text-xs font-semibold flex items-center justify-center gap-3 transition-colors cursor-pointer shadow-sm"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          {googleLoading ? 'Signing in with Google...' : 'Continue with Google'}
        </button>

        <div className="flex items-center my-3 text-xs text-slate-500">
          <div className="flex-1 border-t border-slate-800" />
          <span className="px-3">or continue with email</span>
          <div className="flex-1 border-t border-slate-800" />
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && (
            <div className="p-2.5 text-xs bg-rose-950/50 text-rose-400 border border-rose-900/40 rounded mb-4 text-center">
              {error}
            </div>
          )}

          {isRegistering && (
            <div className="form-group">
              <label className="form-label" htmlFor="name">Full Name</label>
              <input
                id="name"
                type="text"
                className="form-input"
                placeholder="John Doe"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required={isRegistering}
              />
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

          {isRegistering && (
            <div className="form-group">
              <label className="form-label" htmlFor="role">Role</label>
              <select
                id="role"
                className="form-input text-slate-200 bg-slate-900"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="EMPLOYEE">Employee</option>
                <option value="MANAGER">Manager</option>
                <option value="ADMIN">Admin</option>
              </select>
            </div>
          )}

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
            disabled={loading || googleLoading}
          >
            {loading ? (
              <><div className="spinner spinner-sm" /> {isRegistering ? 'Creating Account...' : 'Signing in...'}</>
            ) : (
              isRegistering ? 'Create Account with Firebase' : 'Sign In'
            )}
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors underline cursor-pointer"
            onClick={() => {
              setIsRegistering(!isRegistering);
              setError(null);
            }}
          >
            {isRegistering ? 'Already have an account? Sign In' : "Don't have an account? Create one"}
          </button>
        </div>

        <p className="login-footer mt-6">
          Organizational Intelligence Platform
        </p>
      </div>
    </div>
  );
}
