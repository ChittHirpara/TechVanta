import React, { useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from './context/AuthContext';
import GovStrip from './components/common/GovStrip';
import Header from './components/common/Header';
import Navigation from './components/common/Navigation';
import Toast from './components/common/Toast';
import AuthModal from './components/auth/AuthModal';
import Dashboard from './components/dashboard/Dashboard';
import Escalations from './components/dashboard/Escalations';
import JurisdictionManagement from './components/dashboard/JurisdictionManagement';
import Registry from './components/registry/Registry';
import Ingestion from './components/ingestion/Ingestion';
import Workspace from './components/workspace/Workspace';
import { IconEmblem, IconLock, IconShield, IconCheck } from './components/common/Icons';


export default function App() {
  const { t } = useTranslation();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    document.title = t('app.document_title');
  }, [t]);

  const [activeTab, setActiveTab] = useState('dashboard');
  const [currentDocId, setCurrentDocId] = useState(null);
  const [docCount, setDocCount] = useState(0);

  // Auth modal state
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState('login');

  // Toasts
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const handleDismissToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handleOpenAuth = (tab = 'login') => {
    setAuthModalTab(tab);
    setIsAuthModalOpen(true);
  };

  const handleSelectDoc = (id) => {
    setCurrentDocId(id);
    setActiveTab('workspace');
  };

  const handleReprocessDoc = (id) => {
    setCurrentDocId(id);
    setActiveTab('upload');
  };

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--gov-navy-950)',
          color: '#ffffff',
          fontFamily: 'var(--font-sans)',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div className="national-emblem-badge" style={{ margin: '0 auto 16px', width: 56, height: 56 }}>
            <IconEmblem size={28} />
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.01em' }}>
            {t('app.loading_portal')}
          </div>
          <div style={{ fontSize: 12, color: 'var(--slate-400)', marginTop: 6 }} className="font-mono">
            {t('app.loading_subtext')}
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <GovStrip />
      <Header onOpenAuth={handleOpenAuth} />

      {isAuthenticated && (
        <Navigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
          docCount={docCount}
          currentDocId={currentDocId}
        />
      )}

      <main className="portal-main">
        {!isAuthenticated ? (
          /* Unauthenticated Landing */
          <div>
            <div className="gov-alert gov-alert-info">
              <IconShield size={16} />
              <div>
                <strong>{t('app.dept_banner_title')}</strong>
                {' '}{t('app.dept_banner_desc')}
              </div>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: 24,
                marginTop: 24,
              }}
            >
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    <IconLock size={15} />
                    {t('app.dept_access_title')}
                  </h2>
                </div>
                <div className="card-body">
                  <p style={{ color: 'var(--slate-600)', marginBottom: 20, fontSize: 13 }}>
                    {t('app.dept_access_desc')}
                  </p>
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <button className="btn btn-primary" onClick={() => handleOpenAuth('login')}>
                      <IconLock size={13} />
                      {t('app.sign_in_workspace')}
                    </button>
                    <button className="btn btn-saffron" onClick={() => handleOpenAuth('register')}>
                      {t('app.new_officer_reg')}
                    </button>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    <IconShield size={15} />
                    {t('app.architecture_title')}
                  </h2>
                </div>
                <div className="card-body" style={{ fontSize: 13, color: 'var(--slate-700)' }}>
                  <ul style={{ paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>{t('app.ocr_title')}</strong> {t('app.ocr_desc')}</span>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>{t('app.dilrmp_title')}</strong> {t('app.dilrmp_desc')}</span>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>{t('app.crypto_title')}</strong> {t('app.crypto_desc')}</span>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>{t('app.fraud_title')}</strong> {t('app.fraud_desc')}</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Authenticated Views */
          <div>
            {activeTab === 'dashboard' && (
              <Dashboard
                onNavigateToUpload={() => setActiveTab('upload')}
                onNavigateToRegistry={() => setActiveTab('documents')}
              />
            )}

            {activeTab === 'escalations' && (
              <Escalations
                onSelectDoc={handleSelectDoc}
              />
            )}

            {activeTab === 'jurisdictions' && (
              <JurisdictionManagement
                showToast={showToast}
              />
            )}

            {activeTab === 'documents' && (
              <Registry
                onSelectDoc={handleSelectDoc}
                onNavigateToUpload={() => setActiveTab('upload')}
                onDocCountUpdate={setDocCount}
              />
            )}


            {activeTab === 'upload' && (
              <Ingestion
                onOpenWorkspace={handleSelectDoc}
                showToast={showToast}
              />
            )}

            {activeTab === 'workspace' && currentDocId && (
              <Workspace
                docId={currentDocId}
                onBackToRegistry={() => setActiveTab('documents')}
                onReprocess={handleReprocessDoc}
                showToast={showToast}
              />
            )}
          </div>
        )}
      </main>

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        initialTab={authModalTab}
        onClose={() => setIsAuthModalOpen(false)}
        showToast={showToast}
        onSuccess={() => setActiveTab('dashboard')}
      />

      {/* Toast Notification Container */}
      <Toast toasts={toasts} onDismiss={handleDismissToast} />

      {/* Institutional Footer */}
      <footer className="gov-footer">
        <div>{t('app.footer_line1')}</div>
        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.8 }} className="font-mono">
          {t('app.footer_line2')}
        </div>
      </footer>
    </>
  );
}
