import React, { useState, useCallback } from 'react';
import { useAuth } from './context/AuthContext';
import GovStrip from './components/common/GovStrip';
import Header from './components/common/Header';
import Navigation from './components/common/Navigation';
import Toast from './components/common/Toast';
import AuthModal from './components/auth/AuthModal';
import Dashboard from './components/dashboard/Dashboard';
import Registry from './components/registry/Registry';
import Ingestion from './components/ingestion/Ingestion';
import Workspace from './components/workspace/Workspace';
import { IconEmblem, IconLock, IconShield, IconCheck } from './components/common/Icons';

export default function App() {
  const { isAuthenticated, isLoading } = useAuth();

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
            Initializing BhoomiScan AI Portal...
          </div>
          <div style={{ fontSize: 12, color: 'var(--slate-400)', marginTop: 6 }} className="font-mono">
            Verifying sovereign security credentials &amp; endpoints
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
                <strong>Department of Land Resources &amp; Revenue Administration:</strong>
                {' '}Authorized departmental access required. Please sign in to access jurisdiction records, verification queues, and GIS push integrations.
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
                    Official Departmental Access
                  </h2>
                </div>
                <div className="card-body">
                  <p style={{ color: 'var(--slate-600)', marginBottom: 20, fontSize: 13 }}>
                    Access role-governed verification queues for Field Officers (Patwaris), Verifying Officers (Tehsildars), and District Administrators.
                  </p>
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                    <button className="btn btn-primary" onClick={() => handleOpenAuth('login')}>
                      <IconLock size={13} />
                      Sign In to Workspace
                    </button>
                    <button className="btn btn-saffron" onClick={() => handleOpenAuth('register')}>
                      New Officer Registration
                    </button>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">
                    <IconShield size={15} />
                    System Architecture &amp; Standards
                  </h2>
                </div>
                <div className="card-body" style={{ fontSize: 13, color: 'var(--slate-700)' }}>
                  <ul style={{ paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>Multimodal OCR:</strong> EasyOCR deep learning + Tesseract cascade for Indic scripts.</span>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>DILRMP 2.0:</strong> Automated 14-digit ULPIN allocation &amp; cadastral mapping.</span>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>Cryptographic Seal:</strong> SHA-256 tamper-evident integrity hashing.</span>
                    </li>
                    <li style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <IconCheck size={14} className="text-emerald-600 mt-0.5" />
                      <span><strong>Fraud Shield:</strong> Token-set fuzzy duplicate record detection against registry.</span>
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
        <div>BhoomiScan AI • National Land Record Modernization &amp; AI Verification Engine</div>
        <div style={{ marginTop: 4, fontSize: 11, opacity: 0.8 }} className="font-mono">
          Smart India Hackathon (SIH) Innovation • GIGW &amp; DILRMP 2.0 Compliant
        </div>
      </footer>
    </>
  );
}
