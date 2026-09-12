import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';
import { IconDashboard, IconFolder, IconUpload, IconShield, IconAlert } from './Icons';

export default function Navigation({ activeTab, onTabChange, docCount, currentDocId }) {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();

  return (
    <nav className="portal-nav">
      <button
        className={`nav-tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
        onClick={() => onTabChange('dashboard')}
      >
        <IconDashboard size={15} />
        {t('nav.dashboard')}
      </button>

      <button
        className={`nav-tab-btn ${activeTab === 'documents' ? 'active' : ''}`}
        onClick={() => onTabChange('documents')}
      >
        <IconFolder size={15} />
        {t('nav.registry')}
        <span className="nav-count-badge">{docCount || 0}</span>
      </button>

      {isAdmin && (
        <>
          <button
            className={`nav-tab-btn ${activeTab === 'escalations' ? 'active' : ''}`}
            onClick={() => onTabChange('escalations')}
          >
            <IconAlert size={15} className="text-rose-600" />
            Escalations
          </button>

          <button
            className={`nav-tab-btn ${activeTab === 'jurisdictions' ? 'active' : ''}`}
            onClick={() => onTabChange('jurisdictions')}
          >
            <IconShield size={15} />
            Jurisdictions
          </button>
        </>
      )}

      <button
        className={`nav-tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
        onClick={() => onTabChange('upload')}
      >
        <IconUpload size={15} />
        {t('nav.ingestion')}
      </button>

      {currentDocId && (
        <button
          className={`nav-tab-btn ${activeTab === 'workspace' ? 'active' : ''}`}
          onClick={() => onTabChange('workspace')}
        >
          <IconShield size={15} />
          {t('nav.workspace', { id: currentDocId })}
        </button>
      )}
    </nav>
  );
}

