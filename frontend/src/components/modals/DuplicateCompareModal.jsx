import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { IconAlert, IconClose, IconFile, IconShield } from '../common/Icons';
import { documentsApi } from '../../api/client';
import { useAuth } from '../../context/AuthContext';

export default function DuplicateCompareModal({
  isOpen,
  onClose,
  currentDoc,
  currentFields = [],
  duplicateMatch,
}) {
  const { t } = useTranslation();
  const { isVerifier, isFieldOfficer } = useAuth();
  const [targetDoc, setTargetDoc] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isForbidden, setIsForbidden] = useState(false);

  useEffect(() => {
    if (isOpen && duplicateMatch?.document_id) {
      if (isFieldOfficer) {
        // Field officers are restricted from cross-officer detailed document inspection
        setIsForbidden(true);
        setIsLoading(false);
        setTargetDoc(null);
        return;
      }
      setIsLoading(true);
      setIsForbidden(false);
      documentsApi
        .get(duplicateMatch.document_id)
        .then((data) => {
          setTargetDoc(data);
          setIsForbidden(false);
        })
        .catch((err) => {
          console.error('Failed to load target duplicate doc:', err);
          if (err?.response?.status === 403 || err?.status === 403) {
            setIsForbidden(true);
          }
        })
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, duplicateMatch, isFieldOfficer]);

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
                {t('modals.duplicate.title')}
              </h3>
              <div style={{ fontSize: 12, color: '#b91c1c' }}>
                {t('modals.duplicate.suspected_overlap')}{' '}
                <strong>
                  {duplicateMatch?.combined_score !== undefined && duplicateMatch?.combined_score !== null
                    ? t('modals.duplicate.token_similarity', { score: Math.round(duplicateMatch.combined_score) })
                    : t('modals.duplicate.confidence_unavailable')}
                </strong>
              </div>
            </div>
          </div>
          <button className="btn-icon" onClick={onClose} aria-label={t('modals.close')}>
            <IconClose size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <div className="gov-alert gov-alert-danger" style={{ marginBottom: 16 }}>
            <IconShield size={18} />
            <div>
              <strong>{t('modals.duplicate.dispute_title')}</strong> {t('modals.duplicate.dispute_desc')}
            </div>
          </div>

          {isLoading ? (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--slate-500)' }}>
              {t('modals.duplicate.loading')}
            </div>
          ) : (isFieldOfficer || isForbidden) ? (
            /* Role-Restricted View for Field Officers (Institutional Workflow Governance) */
            <div className="role-restricted-container" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span
                  className="badge"
                  style={{
                    background: '#eff6ff',
                    color: '#1d4ed8',
                    border: '1px solid #bfdbfe',
                    padding: '6px 14px',
                    fontSize: 12,
                    fontWeight: 700,
                    borderRadius: 6,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <IconShield size={16} />
                  {t('modals.duplicate.role_restricted_badge')}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    background: '#fef3c7',
                    color: '#92400e',
                    border: '1px solid #fde68a',
                    padding: '4px 10px',
                    borderRadius: 6,
                    fontWeight: 600,
                  }}
                >
                  {duplicateMatch?.combined_score !== undefined && duplicateMatch?.combined_score !== null
                    ? `${Math.round(duplicateMatch.combined_score)}% Match`
                    : 'Match Detected'}
                </span>
              </div>

              <div className="gov-alert gov-alert-warning" style={{ margin: 0 }}>
                <div>
                  <strong>{t('modals.duplicate.role_restricted_title')}</strong>{' '}
                  {t('modals.duplicate.role_restricted_desc')}
                </div>
              </div>

              <div
                style={{
                  background: 'var(--slate-50)',
                  border: '1px solid var(--slate-200)',
                  borderRadius: 8,
                  padding: 16,
                }}
              >
                <h4 style={{ margin: '0 0 12px 0', fontSize: 13, color: 'var(--slate-800)', fontWeight: 700 }}>
                  {t('modals.duplicate.matched_summary_title')}
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, fontSize: 13 }}>
                  <div style={{ background: '#ffffff', padding: 12, borderRadius: 6, border: '1px solid var(--slate-200)' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--slate-500)', textTransform: 'uppercase', marginBottom: 6 }}>
                      {t('modals.duplicate.current_ingestion_label', { id: currentDoc?.id, filename: currentDoc?.filename })}
                    </div>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: 'var(--slate-600)', fontSize: 12 }}>{t('workspace.labels.field_identifier')}: </span>
                      <strong style={{ fontFamily: 'var(--font-mono)' }}>#{currentDoc?.id}</strong>
                    </div>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: 'var(--slate-600)', fontSize: 12 }}>Owner: </span>
                      <strong style={{ fontFamily: 'var(--font-mono)' }}>{currentFieldMap['owner_name'] || currentDoc?.owner_name || '—'}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--slate-600)', fontSize: 12 }}>Survey No: </span>
                      <strong style={{ fontFamily: 'var(--font-mono)' }}>{currentFieldMap['survey_number'] || currentDoc?.survey_number || '—'}</strong>
                    </div>
                  </div>

                  <div style={{ background: '#fffbeb', padding: 12, borderRadius: 6, border: '1px solid #fde68a' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#92400e', textTransform: 'uppercase', marginBottom: 6 }}>
                      {t('modals.duplicate.existing_record')}
                    </div>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: 'var(--slate-600)', fontSize: 12 }}>{t('modals.duplicate.matched_record_id')}: </span>
                      <strong style={{ fontFamily: 'var(--font-mono)', color: '#92400e' }}>#{duplicateMatch?.document_id}</strong>
                    </div>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ color: 'var(--slate-600)', fontSize: 12 }}>{t('modals.duplicate.matched_owner')}: </span>
                      <strong style={{ fontFamily: 'var(--font-mono)', color: '#92400e' }}>{duplicateMatch?.owner_name || '—'}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--slate-600)', fontSize: 12 }}>{t('modals.duplicate.matched_survey')}: </span>
                      <strong style={{ fontFamily: 'var(--font-mono)', color: '#92400e' }}>{duplicateMatch?.survey_number || '—'}</strong>
                    </div>
                  </div>
                </div>
              </div>

              <div
                style={{
                  background: '#f8fafc',
                  borderLeft: '4px solid #0284c7',
                  padding: '10px 14px',
                  borderRadius: 4,
                  fontSize: 12,
                  color: 'var(--slate-700)',
                }}
              >
                {t('modals.duplicate.escalation_notice')}
              </div>
            </div>
          ) : (
            /* Full Side-by-Side Comparison for Verifying Officers & Admins */
            <div>
              <div style={{ marginBottom: 12 }}>
                <span
                  className="badge"
                  style={{
                    background: '#ecfdf5',
                    color: '#065f46',
                    border: '1px solid #a7f3d0',
                    padding: '4px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    borderRadius: 4,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <IconShield size={14} />
                  {t('modals.duplicate.verifier_audit_badge')}
                </span>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="gov-table" style={{ width: '100%', fontSize: 13 }}>
                  <thead>
                    <tr>
                      <th style={{ width: '25%' }}>{t('modals.duplicate.parcel_attribute')}</th>
                      <th style={{ width: '37%', background: '#f0f4f9' }}>
                        {t('modals.duplicate.current_ingestion_label', { id: currentDoc?.id, filename: currentDoc?.filename })}
                      </th>
                      <th style={{ width: '38%', background: '#fffbeb' }}>
                        {t('modals.duplicate.existing_registry_label', { id: targetDoc?.id || duplicateMatch?.document_id, filename: targetDoc?.filename || t('modals.duplicate.existing_record') })}
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
                                {t('modals.duplicate.mismatch_conflict')}
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
                                {t('modals.duplicate.duplicate_overlap')}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>
            {t('modals.duplicate.audit_note')}
          </div>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            {t('modals.close')}
          </button>
        </div>
      </div>
    </div>
  );
}
