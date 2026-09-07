import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { IconEmblem, IconUser, IconLock } from './Icons';

export default function Header({ onOpenAuth }) {
  const { user, isAuthenticated, logout } = useAuth();

  const roleLabels = {
    admin: 'Administrator',
    verifier: 'Verifying Officer',
    field_officer: 'Field Officer',
  };

  return (
    <header className="portal-header">
      <div className="brand-container">
        <div className="national-emblem-badge" title="National Land Records Sovereign Platform">
          <IconEmblem size={22} />
        </div>
        <div className="brand-text">
          <h1>
            BhoomiScan AI
            <span className="hindi-title">भूमिस्कैन एआई</span>
          </h1>
          <p>Autonomous Land Record Digitization, Semantic Verification & Sovereign Governance</p>
        </div>
      </div>

      <div className="header-user-panel">
        {isAuthenticated && user ? (
          <>
            <div className="user-pill">
              <IconUser size={14} className="text-slate-400" />
              <span>
                <strong>{user.full_name || user.username}</strong>
              </span>
              <span className={`user-role-tag role-${user.role}`}>
                {roleLabels[user.role] || user.role}
              </span>
            </div>
            <button className="btn btn-header-outline btn-sm" onClick={logout}>
              Sign Out
            </button>
          </>
        ) : (
          <>
            <button
              className="btn btn-header-outline btn-sm"
              onClick={() => onOpenAuth('login')}
            >
              <IconLock size={13} />
              Sign In
            </button>
            <button
              className="btn btn-saffron btn-sm"
              onClick={() => onOpenAuth('register')}
            >
              Register Officer
            </button>
          </>
        )}
      </div>
    </header>
  );
}
