import { NavLink } from 'react-router-dom';
import { logout } from '../services/api';
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  Share2,
  Clock,
  BarChart3,
  History,
  Settings,
  LogOut,
  Brain,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/assistant', icon: MessageSquare, label: 'AI Assistant' },
  { to: '/documents', icon: FileText, label: 'Documents' },
  { to: '/graph', icon: Share2, label: 'Knowledge Graph' },
  { to: '/timeline', icon: Clock, label: 'Timeline' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/history', icon: History, label: 'Query History' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <Brain size={28} />
        </div>
        <div className="sidebar-brand-text">
          <span className="sidebar-title">MEMORAGRAPH</span>
          <span className="sidebar-subtitle">Organizational Memory</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`
            }
          >
            <item.icon size={20} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="sidebar-link" onClick={logout}>
          <LogOut size={20} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
