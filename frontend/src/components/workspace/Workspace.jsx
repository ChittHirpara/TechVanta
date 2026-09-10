import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { documentsApi, integrationsApi } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import FieldModal from '../modals/FieldModal';
import AuditModal from '../modals/AuditModal';
import DilrmpModal from '../modals/DilrmpModal';
import DuplicateCompareModal from '../modals/DuplicateCompareModal';
import CadastralMapPanel from './CadastralMapPanel';
import {
  IconFile,
  IconDownload,
  IconHistory,
  IconCopy,
  IconRefresh,
  IconCheck,
  IconEdit,
  IconAlert,
  IconShield,
  IconExternal,
} from '../common/Icons';

export default function Workspace({ docId, onBackToRegistry, onReprocess, showToast }) {
  const { t } = useTranslation();
  const { token, isFieldOfficer } = useAuth();

  const [doc, setDoc] = useState(null);
  const [integrity, setIntegrity] = useState(null);
  const [duplicates, setDuplicates] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Modals state
  const [selectedField, setSelectedField] = useState(null);
  const [isFieldModalOpen, setIsFieldModalOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [isDilrmpModalOpen, setIsDilrmpModalOpen] = useState(false);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);

  // Action loading state
  const [isVerifying, setIsVerifying] = useState(false);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [isPushingLrms, setIsPushingLrms] = useState(false);
  const [isPushingGis, setIsPushingGis] = useState(false);

  // OCR Detection Overlay state
  const [showOcrOverlay, setShowOcrOverlay] = useState(false);
  const [ocrData, setOcrData] = useState(null);
  const [isLoadingOcr, setIsLoadingOcr] = useState(false);
  const [activeTokenHighlight, setActiveTokenHighlight] = useState('');

  const toggleOcrOverlay = async () => {
    const next = !showOcrOverlay;
    setShowOcrOverlay(next);
    if (next && !ocrData) {
      setIsLoadingOcr(true);
      try {
        const data = await documentsApi.getOcrBoxes(docId);
        setOcrData(data);
      } catch (err) {
        console.warn('Failed to fetch OCR bounding boxes:', err);
      } finally {
        setIsLoadingOcr(false);
      }
    }
  };

  const fetchWorkspaceData = useCallback(async () => {
    if (!docId) return;
    setIsLoading(true);
    setError('');

    try {
      const [docData, integrityData, duplicatesData] = await Promise.all([
        documentsApi.get(docId),
        documentsApi.getIntegrity(docId),
        documentsApi.getDuplicates(docId).catch(() => null),
      ]);

      setDoc(docData);
      setIntegrity(integrityData);
      setDuplicates(duplicatesData);
    } catch (err) {
      setError(err.message || 'Failed to load document workspace.');
    } finally {
      setIsLoading(false);
    }
  }, [docId]);

  useEffect(() => {
    fetchWorkspaceData();
  }, [fetchWorkspaceData]);

  const handleVerify = async () => {
    if (!window.confirm(`Are you sure you want to sign off and verify Land Record #${docId}?`)) {
      return;
    }

    setIsVerifying(true);
    try {
      await documentsApi.verify(docId);
      showToast?.(t('workspace.toasts.verified', { docId }), 'success');
      fetchWorkspaceData();
    } catch (err) {
      showToast?.(t('workspace.toasts.verify_blocked', { err: err.message }), 'error');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleReprocess = async () => {
    if (!window.confirm(`Re-run full OCR and entity extraction on Document #${docId}?`)) {
      return;
    }

    setIsReprocessing(true);
    try {
      await documentsApi.reprocess(docId);
      showToast?.(t('workspace.toasts.reprocess_triggered', { docId }), 'info');
      onReprocess?.(docId, doc?.filename);
    } catch (err) {
      showToast?.(t('workspace.toasts.reprocess_failed', { err: err.message }), 'error');
    } finally {
      setIsReprocessing(false);
    }
  };

  const handlePushIntegration = async (type) => {
    const isLrms = type === 'lrms';
    if (isLrms) setIsPushingLrms(true);
    else setIsPushingGis(true);

    try {
      const res = isLrms
        ? await integrationsApi.pushLrms(docId)
        : await integrationsApi.pushGis(docId);

      showToast?.(t('workspace.toasts.pushed', { system: res.system, reference_id: res.reference_id, status: res.status }), 'success');
    } catch (err) {
      showToast?.(t('workspace.toasts.push_failed', { err: err.message }), 'error');
    } finally {
      if (isLrms) setIsPushingLrms(false);
      else setIsPushingGis(false);
    }
  };

  if (isLoading) {
    return (
      <div className="card" style={{ padding: 48, textAlign: 'center', color: 'var(--slate-500)' }}>
        Loading Verification Workspace for Record #{docId}...
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="card" style={{ padding: 32 }}>
        <div className="gov-alert gov-alert-danger">
          <IconAlert size={16} />
          <div>{error || 'Document not found.'}</div>
        </div>
        <button className="btn btn-outline" onClick={onBackToRegistry}>
          {t('workspace.btn_back_registry')}
        </button>
      </div>
    );
  }

  const fileUrl = documentsApi.getFileUrl(docId, token);
  const isImage = /\.(png|jpg|jpeg|webp|tiff)$/i.test(doc.filename);
  const jurisdiction =
    [doc.district, doc.tehsil, doc.village].filter(Boolean).join(' / ') || 'Not Specified';

  const suspectedMatch =
    duplicates?.has_suspected_duplicates && duplicates.matches?.[0]
      ? duplicates.matches[0]
      : null;

  return (
    <div>
      {/* Workspace Header Toolbar */}
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-outline btn-sm" onClick={onBackToRegistry}>
            {t('workspace.btn_back_registry')}
          </button>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--gov-navy-900)' }}>
            Record #{doc.id}
          </h2>
          <span className={`badge badge-${doc.status}`}>
            <span className={`status-dot status-dot-${doc.status}`} />
            {t(`registry.status.${doc.status}`) || doc.status.replace('_', ' ')}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-outline btn-sm" onClick={() => setIsAuditModalOpen(true)}>
            <IconHistory size={13} />
            {t('workspace.tabs.audit_trail')}
          </button>
          <button className="btn btn-outline btn-sm" onClick={() => setIsDilrmpModalOpen(true)}>
            <IconCopy size={13} />
            {t('workspace.btn_dilrmp_export')}
          </button>
          <a
            className="btn btn-outline btn-sm"
            href={documentsApi.getCertificateUrl(docId, token)}
            target="_blank"
            rel="noreferrer"
            title={t('workspace.labels.certificate_banner')}
          >
            <IconFile size={13} />
            {t('workspace.btn_certificate')}
          </a>
          <button
            className="btn btn-outline btn-sm"
            onClick={handleReprocess}
            disabled={isReprocessing || isFieldOfficer}
            title={isFieldOfficer ? t('workspace.tooltips.reprocess_blocked') : ''}
          >
            <IconRefresh size={13} className={isReprocessing ? 'animate-spin' : ''} />
            {isReprocessing ? t('workspace.connecting') : t('workspace.btn_reprocess')}
          </button>
          <button
            className="btn btn-success btn-sm"
            onClick={handleVerify}
            disabled={doc.status === 'verified' || isVerifying || isFieldOfficer}
            title={
              isFieldOfficer
                ? t('workspace.tooltips.verify_blocked')
                : doc.status === 'verified'
                ? t('workspace.tooltips.already_verified')
                : ''
            }
          >
            <IconCheck size={14} />
            {isVerifying ? t('workspace.btn_signing') : doc.status === 'verified' ? t('workspace.btn_verified') : t('workspace.btn_verify')}
          </button>
        </div>
      </div>

      {/* Fraud Shield Duplicate Alert */}
      {suspectedMatch && (
        <div className="gov-alert gov-alert-danger">
          <IconAlert size={18} />
          <div>
            <strong>{t('workspace.labels.fraud_shield_warning')}</strong>
            {' '}This parcel closely matches existing Document #{suspectedMatch.document_id} (
            {suspectedMatch.owner_name ? `Owner: ${suspectedMatch.owner_name}, ` : ''}
            Survey #{suspectedMatch.survey_number || 'N/A'}) with{' '}
            <strong className="font-mono">
              {suspectedMatch.combined_score !== undefined && suspectedMatch.combined_score !== null
                ? `${Math.round(suspectedMatch.combined_score)}% similarity`
                : 'Similarity score unavailable'}
            </strong>.
          </div>
        </div>
      )}

      {/* Split-Screen Dual Viewer */}
      <div className="workspace-grid">
        {/* Left Pane: Original Deed Viewer */}
        <div className="document-preview-pane">
          <div className="preview-toolbar">
            <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <IconFile size={14} />
              {doc.filename} (ID: #{doc.id})
            </span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <button
                type="button"
                className={`btn btn-sm ${showOcrOverlay ? 'btn-primary' : 'btn-outline'}`}
                onClick={toggleOcrOverlay}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                title={showOcrOverlay ? t('workspace.ocr_overlay_active') : t('workspace.ocr_overlay_off')}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: showOcrOverlay ? '#10b981' : '#94a3b8',
                    display: 'inline-block',
                  }}
                />
                {t('workspace.ocr_overlay_toggle')}
              </button>
              <a
                href={fileUrl}
                target="_blank"
                rel="noreferrer"
                download={doc.filename}
                className="btn btn-header-outline btn-sm"
              >
                <IconDownload size={13} />
                {t('workspace.btn_download_original')}
              </a>
            </div>
          </div>

          <div className="preview-content">
            {showOcrOverlay ? (
              <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'auto', background: '#0f172a', padding: 8 }}>
                {/* Confidence Legend Bar */}
                <div
                  style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 20,
                    background: 'rgba(15, 23, 42, 0.92)',
                    backdropFilter: 'blur(4px)',
                    color: '#f8fafc',
                    padding: '8px 12px',
                    borderRadius: 6,
                    marginBottom: 8,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: 11,
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(16, 185, 129, 0.4)', border: '1px solid #10b981' }} />
                      {t('workspace.ocr_reliability_high')}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(245, 158, 11, 0.4)', border: '1px solid #f59e0b' }} />
                      {t('workspace.ocr_reliability_med')}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: 'rgba(239, 68, 68, 0.4)', border: '1px solid #ef4444' }} />
                      {t('workspace.ocr_reliability_low')}
                    </span>
                  </div>
                  <div>
                    {isLoadingOcr ? (
                      <span style={{ color: '#93c5fd' }}>{t('workspace.ocr_loading')}</span>
                    ) : ocrData?.tokens ? (
                      <span>{t('workspace.ocr_tokens_detected', { count: ocrData.tokens.length })}</span>
                    ) : null}
                  </div>
                </div>

                {/* Render document image preview with overlay */}
                <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', width: '100%' }}>
                  <img
                    src={documentsApi.getPreviewImageUrl(docId, token)}
                    alt={doc.filename}
                    style={{ width: '100%', height: 'auto', display: 'block', borderRadius: 4 }}
                  />

                  {/* Bounding Box Tokens */}
                  {ocrData?.tokens?.map((tok, idx) => {
                    const [x, y, w, h] = tok.box || [0, 0, 0, 0];
                    const conf = tok.confidence !== undefined ? tok.confidence : 1.0;
                    const pct = Math.round(conf * 100);

                    // High (>=85%): green, Med (70-84%): amber, Low (<70%): crimson
                    let borderColor = '#10b981';
                    let bgColor = 'rgba(16, 185, 129, 0.2)';
                    if (pct < 70) {
                      borderColor = '#ef4444';
                      bgColor = 'rgba(239, 68, 68, 0.25)';
                    } else if (pct < 85) {
                      borderColor = '#f59e0b';
                      bgColor = 'rgba(245, 158, 11, 0.25)';
                    }

                    // Highlight matching tokens if activeTokenHighlight matches
                    const isMatched =
                      activeTokenHighlight &&
                      tok.text &&
                      (activeTokenHighlight.toLowerCase().includes(tok.text.toLowerCase()) ||
                       tok.text.toLowerCase().includes(activeTokenHighlight.toLowerCase()));

                    if (isMatched) {
                      borderColor = '#38bdf8';
                      bgColor = 'rgba(56, 189, 248, 0.5)';
                    }

                    return (
                      <div
                        key={idx}
                        title={`${tok.text} (${pct}% confidence)`}
                        style={{
                          position: 'absolute',
                          left: `${x}%`,
                          top: `${y}%`,
                          width: `${w}%`,
                          height: `${h}%`,
                          border: `1.5px solid ${borderColor}`,
                          backgroundColor: bgColor,
                          boxSizing: 'border-box',
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                          zIndex: isMatched ? 15 : 5,
                        }}
                      />
                    );
                  })}
                </div>
              </div>
            ) : isImage ? (
              <img src={fileUrl} alt={doc.filename} />
            ) : (
              <iframe
                src={fileUrl}
                title={t('workspace.viewer_title')}
                style={{ width: '100%', height: '100%', border: 'none' }}
              />
            )}
          </div>
        </div>

        {/* Right Pane: Cryptographic Seal, Extracted Fields, Integrations */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Integrity Seal Card */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div className="card-header" style={{ padding: '12px 16px' }}>
              <h3 className="card-title" style={{ fontSize: 13 }}>
                <IconShield size={14} />
                {t('workspace.labels.crypto_seal')}
              </h3>
              <span className="badge badge-verified">
                <span className="status-dot status-dot-verified" />
                {t('workspace.labels.status_secured_verified')}
              </span>
            </div>
            <div className="card-body" style={{ padding: '12px 16px', fontSize: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'center' }}>
                <span style={{ color: 'var(--slate-500)' }}>{t('workspace.labels.sha_seal')}</span>
                <span className="hash-chip" title={integrity?.sha256_hash}>
                  {integrity?.sha256_hash ? `${integrity.sha256_hash.substring(0, 24)}...` : 'N/A'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--slate-500)' }}>{t('workspace.labels.jurisdiction')}</span>
                <strong>{jurisdiction}</strong>
              </div>
            </div>
          </div>

          {/* Extracted Fields Table */}
          <div className="card" style={{ marginBottom: 0, flex: 1 }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">{t('workspace.extract_title')}</h3>
                <div className="card-subtitle">
                  {t('workspace.inspect_subtitle')}
                </div>
              </div>
            </div>

            <div className="card-body" style={{ padding: 0 }}>
              <div className="table-responsive">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>{t('workspace.labels.field_identifier')}</th>
                      <th>{t('workspace.labels.extracted_value')}</th>
                      <th style={{ width: 120 }}>{t('workspace.labels.confidence')}</th>
                      <th>{t('registry.columns.status')}</th>
                      <th style={{ textAlign: 'right' }}>{t('workspace.labels.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!doc.extracted_fields || doc.extracted_fields.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--slate-500)' }}>
                          {t('workspace.no_fields_extracted')}
                        </td>
                      </tr>
                    ) : (
                      doc.extracted_fields.map((field) => {
                        const score =
                          field.confidence_score !== null && field.confidence_score !== undefined
                            ? Math.round(field.confidence_score * 100)
                            : 0;

                        let confClass = 'conf-high';
                        if (score < 70) confClass = 'conf-low';
                        else if (score < 85) confClass = 'conf-mid';

                        const isRowHighlighted =
                          activeTokenHighlight &&
                          field.value &&
                          (activeTokenHighlight.toLowerCase().includes(field.value.toLowerCase()) ||
                            field.value.toLowerCase().includes(activeTokenHighlight.toLowerCase()));

                        return (
                          <tr
                            key={field.field_name}
                            onMouseEnter={() => setActiveTokenHighlight(field.value || '')}
                            onMouseLeave={() => setActiveTokenHighlight('')}
                            style={{
                              backgroundColor: isRowHighlighted ? 'rgba(56, 189, 248, 0.1)' : undefined,
                              transition: 'background-color 0.15s ease',
                              cursor: 'pointer',
                            }}
                          >
                            <td>
                              <code className="font-mono text-xs text-gov-navy-900 font-semibold">
                                {field.field_name}
                              </code>
                            </td>
                            <td>
                              <strong style={{ fontSize: 13 }}>{field.value || '—'}</strong>
                            </td>
                            <td>
                              <div className="font-mono text-xs font-semibold">{score}%</div>
                              <div className="confidence-meter">
                                <div
                                  className={`confidence-fill ${confClass}`}
                                  style={{ width: `${score}%` }}
                                />
                              </div>
                            </td>
                            <td>
                              {field.is_flagged ? (
                                <span className="badge badge-flagged">
                                  <span className="status-dot status-dot-flagged" />
                                  {t('dashboard.stats.needs_review')}
                                </span>
                              ) : (
                                <span className="badge badge-verified">
                                  <span className="status-dot status-dot-verified" />
                                  {t('registry.status.verified')}
                                </span>
                              )}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <button
                                className="btn btn-outline btn-sm"
                                disabled={isFieldOfficer}
                                title={isFieldOfficer ? t('workspace.tooltips.edit_blocked') : ''}
                                onClick={() => {
                                  setSelectedField(field);
                                  setIsFieldModalOpen(true);
                                }}
                              >
                                <IconEdit size={12} />
                                {t('workspace.labels.correct_field')}
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* State Revenue Integrations */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div className="card-header" style={{ padding: '12px 16px' }}>
              <h3 className="card-title" style={{ fontSize: 13 }}>
                <IconExternal size={14} />
                {t('workspace.gateways_title')}
              </h3>
            </div>
            <div
              className="card-body"
              style={{ padding: '12px 16px', display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}
            >
              <button
                className="btn btn-outline btn-sm"
                onClick={() => handlePushIntegration('lrms')}
                disabled={isPushingLrms || isFieldOfficer}
                title={isFieldOfficer ? t('workspace.tooltips.push_blocked') : ''}
              >
                {isPushingLrms ? t('workspace.connecting') : t('workspace.btn_push_lrms')}
              </button>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => handlePushIntegration('gis')}
                disabled={isPushingGis || isFieldOfficer}
                title={isFieldOfficer ? t('workspace.tooltips.push_blocked') : ''}
              >
                {isPushingGis ? t('workspace.connecting') : t('workspace.btn_push_gis')}
              </button>
              <span style={{ fontSize: 11, color: 'var(--slate-500)' }}>
                {t('workspace.gateways_disclaimer')}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Cadastral Geolocation Map Inspector */}
      <CadastralMapPanel doc={doc} fields={doc.extracted_fields || []} />

      {/* Modals */}
      <FieldModal
        isOpen={isFieldModalOpen}
        docId={docId}
        field={selectedField}
        onClose={() => {
          setIsFieldModalOpen(false);
          setSelectedField(null);
        }}
        onUpdated={fetchWorkspaceData}
        showToast={showToast}
      />

      <AuditModal
        isOpen={isAuditModalOpen}
        docId={docId}
        onClose={() => setIsAuditModalOpen(false)}
      />

      <DilrmpModal
        isOpen={isDilrmpModalOpen}
        docId={docId}
        onClose={() => setIsDilrmpModalOpen(false)}
        showToast={showToast}
      />

      <DuplicateCompareModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        currentDoc={doc}
        currentFields={doc.extracted_fields || []}
        duplicateMatch={suspectedMatch}
      />
    </div>
  );
}
