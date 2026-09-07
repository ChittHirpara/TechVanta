import React from 'react';
import { IconDashboard, IconFolder, IconUpload, IconShield } from './Icons';

export default function Navigation({ activeTab, onTabChange, docCount, currentDocId }) {
  return (
    <nav className="portal-nav">
      <button
        className={`nav-tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
        onClick={() => onTabChange('dashboard')}
      >
        <IconDashboard size={15} />
        Operations Dashboard
      </button>

      <button
        className={`nav-tab-btn ${activeTab === 'documents' ? 'active' : ''}`}
        onClick={() => onTabChange('documents')}
      >
        <IconFolder size={15} />
        Land Record Registry
        <span className="nav-count-badge">{docCount || 0}</span>
      </button>

      <button
        className={`nav-tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
        onClick={() => onTabChange('upload')}
      >
        <IconUpload size={15} />
        Ingest Deed
      </button>

      {currentDocId && (
        <button
          className={`nav-tab-btn ${activeTab === 'workspace' ? 'active' : ''}`}
          onClick={() => onTabChange('workspace')}
        >
          <IconShield size={15} />
          Verification Workspace #{currentDocId}
        </button>
      )}
    </nav>
  );
}
