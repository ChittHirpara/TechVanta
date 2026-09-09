import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { documentsApi } from '../../api/client';

export default function DilrmpModal({ isOpen, docId, onClose, showToast }) {
  const { t } = useTranslation();
  const [payload, setPayload] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && docId) {
      setIsLoading(true);
      setError('');
      documentsApi
        .exportDilrmp(docId)
        .then((data) => setPayload(data))
        .catch((err) => setError(err.message || 'Failed to generate DILRMP 2.0 export.'))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, docId]);

  if (!isOpen) return null;

  const handleCopy = () => {
    if (!payload) return;
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
    showToast?.(t('modals.dilrmp.toast_copied'), 'success');
  };

  const handleDownload = () => {
    if (!payload) return;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `DILRMP_Record_${docId}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast?.(t('modals.dilrmp.toast_downloaded', { docId }), 'success');
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" style={{ maxWidth: 740 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="card-title">{t('workspace.btn_dilrmp_export')}</h3>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: 12.5, color: 'var(--slate-600)', marginBottom: 12 }}>
            {t('modals.dilrmp.schema_line1')} <strong>{t('modals.dilrmp.schema_line2')}</strong>.
          </p>

          {isLoading ? (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--slate-500)' }}>
              {t('modals.dilrmp.generating')}
            </div>
          ) : error ? (
            <div className="gov-alert gov-alert-danger">{error}</div>
          ) : (
            <pre
              style={{
                background: '#0f172a',
                color: '#f8fafc',
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                padding: 16,
                borderRadius: 'var(--radius-sm)',
                maxHeight: 380,
                overflow: 'auto',
                lineHeight: 1.5,
              }}
            >
              {JSON.stringify(payload, null, 2)}
            </pre>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={handleCopy} disabled={!payload}>
            📋 {t('modals.dilrmp.btn_copy')}
          </button>
          <button className="btn btn-primary" onClick={handleDownload} disabled={!payload}>
            💾 {t('modals.dilrmp.btn_download')}
          </button>
          <button className="btn btn-outline" onClick={onClose}>
            {t('modals.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
