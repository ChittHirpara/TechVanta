import React, { useState, useEffect } from 'react';
import { documentsApi } from '../../api/client';

export default function DilrmpModal({ isOpen, docId, onClose, showToast }) {
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
    showToast?.('DILRMP 2.0 JSON payload copied to clipboard!', 'success');
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
    showToast?.(`Downloaded DILRMP_Record_${docId}.json`, 'success');
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" style={{ maxWidth: 740 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="card-title">📋 DILRMP 2.0 Standard National Export</h3>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: 12.5, color: 'var(--slate-600)', marginBottom: 12 }}>
            Standardized revenue interchange schema conforming to the <strong>Digital India Land Records Modernization Technical Specifications</strong>.
          </p>

          {isLoading ? (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--slate-500)' }}>
              Generating DILRMP 2.0 standard payload...
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
            📋 Copy JSON
          </button>
          <button className="btn btn-primary" onClick={handleDownload} disabled={!payload}>
            💾 Download File
          </button>
          <button className="btn btn-outline" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
