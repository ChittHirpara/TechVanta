import React, { useState, useEffect } from 'react';
import { IconAlert, IconClose, IconFile, IconShield } from '../common/Icons';
import { documentsApi } from '../../api/client';

export default function DuplicateCompareModal({
  isOpen,
  onClose,
  currentDoc,
  currentFields = [],
  duplicateMatch,
}) {
  const [targetDoc, setTargetDoc] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && duplicateMatch?.document_id) {
      setIsLoading(true);
      documentsApi
        .get(duplicateMatch.document_id)
        .then((data) => setTargetDoc(data))
        .catch((err) => console.error('Failed to load target duplicate doc:', err))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, duplicateMatch]);

  if (!isOpen) return null;

  const currentFieldMap = {};
  currentFields.forEach((f) => {
    currentFieldMap[f.field_name] = f.value;
  });

  const targetFieldMap = {};
  if (targetDoc?.extracted_fields) {
    targetDoc.extracted_fields.forEach((f) => {
      targetFieldMap[f.field_name] = f.value;
    });
  }

  const comparisonFields = [
    { key: 'owner_name', label: 'Primary Owner Name' },
    { key: 'survey_number', label: 'Survey / Plot Number' },
    { key: 'khasra_number', label: 'Khasra Number' },
    { key: 'khata_number', label: 'Khata Number' },
    { key: 'plot_area', label: 'Plot Area' },
    { key: 'district', label: 'District' },
    { key: 'tehsil', label: 'Tehsil' },
    { key: 'village', label: 'Village' },
    { key: 'registration_info', label: 'Registration / Deed Info' },
  ];

  return (
    <div className="modal-backdrop">
      <div className="modal-container" style={{ maxWidth: 900 }}>
        {/* Modal Header */}
        <div className="modal-header" style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ color: '#dc2626' }}>
              <IconAlert size={22} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: 16, color: '#991b1b', fontWeight: 700 }}>
                Fraud Shield — Dual-Title & Parcel Conflict Comparison
              </h3>
              <div style={{ fontSize: 12, color: '#b91c1c' }}>
                Suspected duplicate overlap detected with{' '}
                <strong>
                  {duplicateMatch?.combined_score !== undefined && duplicateMatch?.combined_score !== null
                    ? `${Math.round(duplicateMatch.combined_score)}% token-set similarity`
                    : 'confidence score unavailable'}
                </strong>
              </div>
            </div>
          </div>
          <button className="btn-icon" onClick={onClose} aria-label="Close modal">
            <IconClose size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <div className="gov-alert gov-alert-danger" style={{ marginBottom: 16 }}>
            <IconShield size={18} />
            <div>
              <strong>Potential Revenue Act Title Dispute:</strong> Two separate documents reference overlapping parcel or ownership coordinates. Review discrepancies below before verifying.
            </div>
          </div>

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--slate-500)' }}>
              Loading conflicting document details...
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="gov-table" style={{ width: '100%', fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ width: '25%' }}>Parcel Attribute</th>
                    <th style={{ width: '37%', background: '#f0f4f9' }}>
                      Current Ingestion #{currentDoc?.id} ({currentDoc?.filename})
                    </th>
                    <th style={{ width: '38%', background: '#fffbeb' }}>
                      Existing Registry #{targetDoc?.id || duplicateMatch?.document_id} ({targetDoc?.filename || 'Existing Record'})
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonFields.map(({ key, label }) => {
                    const valA = currentFieldMap[key] || (currentDoc && currentDoc[key]) || '—';
                    const valB = targetFieldMap[key] || (targetDoc && targetDoc[key]) || (key === 'owner_name' ? duplicateMatch?.owner_name : key === 'survey_number' ? duplicateMatch?.survey_number : '—') || '—';
                    const isMismatch = valA !== '—' && valB !== '—' && valA.toLowerCase() !== valB.toLowerCase();
                    const isExactMatch = valA !== '—' && valB !== '—' && valA.toLowerCase() === valB.toLowerCase();

                    return (
                      <tr key={key} style={{ background: isMismatch ? '#fff5f5' : 'transparent' }}>
                        <td style={{ fontWeight: 600, color: 'var(--slate-700)' }}>{label}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                          {valA}
                        </td>
                        <td
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 600,
                            color: isMismatch ? '#dc2626' : isExactMatch ? '#059669' : 'inherit',
                          }}
                        >
                          {valB}
                          {isMismatch && (
                            <span
                              style={{
                                marginLeft: 8,
                                fontSize: 10,
                                background: '#fee2e2',
                                color: '#991b1b',
                                padding: '2px 6px',
                                borderRadius: 4,
                              }}
                            >
                              Mismatch Conflict
                            </span>
                          )}
                          {isExactMatch && (
                            <span
                              style={{
                                marginLeft: 8,
                                fontSize: 10,
                                background: '#dcfce7',
                                color: '#166534',
                                padding: '2px 6px',
                                borderRadius: 4,
                              }}
                            >
                              Duplicate Overlap
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>
            Audit log records this conflict review session automatically.
          </div>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            Close Comparison
          </button>
        </div>
      </div>
    </div>
  );
}
