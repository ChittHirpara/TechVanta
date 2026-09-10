import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { documentsApi } from '../../api/client';

export default function AuditModal({ isOpen, docId, onClose }) {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && docId) {
      setIsLoading(true);
      setError('');
      documentsApi
        .getAudit(docId)
        .then((data) => setLogs(data || []))
        .catch((err) => setError(err.message || 'Failed to load audit trail.'))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, docId]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" style={{ maxWidth: 680 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="card-title">📜 {t('modals.audit.title')} — {t('modals.audit.record_header', { id: docId })}</h3>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ maxHeight: '60vh', overflowY: 'auto' }}>
          {isLoading ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--slate-500)' }}>
              {t('modals.audit.loading')}
            </div>
          ) : error ? (
            <div className="gov-alert gov-alert-danger">{error}</div>
          ) : logs.length === 0 ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--slate-500)' }}>
              {t('modals.audit.empty')}
            </div>
          ) : (
            <div style={{ position: 'relative', paddingLeft: 24, borderLeft: '2px solid var(--slate-200)' }}>
              {logs.map((item, idx) => {
                const dateStr = item.timestamp
                  ? new Date(item.timestamp).toLocaleString()
                  : t('modals.audit.timestamp');
                return (
                  <div key={idx} style={{ position: 'relative', marginBottom: 20 }}>
                    {/* Timeline bullet dot */}
                    <div
                      style={{
                        position: 'absolute',
                        left: -31,
                        top: 2,
                        width: 12,
                        height: 12,
                        borderRadius: '50%',
                        background: '#ffffff',
                        border: '3px solid var(--gov-navy-800)',
                      }}
                    />
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--gov-navy-900)' }}>
                      {item.action}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--slate-500)', margin: '2px 0 6px' }}>
                      {t('modals.audit.actor')} <strong>{item.user_id ? t('modals.audit.user_label', { id: item.user_id }) : t('modals.audit.system_pipeline')}</strong> • {dateStr}
                    </div>
                    {item.details && (
                      <pre
                        style={{
                          background: 'var(--slate-50)',
                          padding: '8px 12px',
                          borderRadius: 'var(--radius-xs)',
                          border: '1px solid var(--slate-200)',
                          fontSize: 11.5,
                          fontFamily: 'var(--font-mono)',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-all',
                          color: 'var(--slate-800)',
                        }}
                      >
                        {typeof item.details === 'object' ? JSON.stringify(item.details, null, 2) : item.details}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>
            {t('modals.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
