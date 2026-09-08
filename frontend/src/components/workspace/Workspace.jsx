import React, { useState, useEffect, useCallback } from 'react';
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
      showToast?.(`Document #${docId} verified & cryptographically sealed!`, 'success');
      fetchWorkspaceData();
    } catch (err) {
      showToast?.(`Verification blocked: ${err.message}`, 'error');
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
      showToast?.(`Reprocessing triggered for Document #${docId}.`, 'info');
      onReprocess?.(docId, doc?.filename);
    } catch (err) {
      showToast?.(`Reprocess request failed: ${err.message}`, 'error');
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

      showToast?.(`Pushed to ${res.system}! Reference: ${res.reference_id} (${res.status})`, 'success');
    } catch (err) {
      showToast?.(`Gateway push failed: ${err.message}`, 'error');
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
          ← Back to Registry
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
            ← Back to Registry
          </button>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--gov-navy-900)' }}>
            Record #{doc.id}
          </h2>
          <span className={`badge badge-${doc.status}`}>
            <span className={`status-dot status-dot-${doc.status}`} />
            {doc.status.replace('_', ' ')}
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-outline btn-sm" onClick={() => setIsAuditModalOpen(true)}>
            <IconHistory size={13} />
            Audit Trail
          </button>
          <button className="btn btn-outline btn-sm" onClick={() => setIsDilrmpModalOpen(true)}>
            <IconCopy size={13} />
            DILRMP 2.0 Export
          </button>
          <a
            className="btn btn-outline btn-sm"
            href={documentsApi.getCertificateUrl(docId, token)}
            target="_blank"
            rel="noreferrer"
            title="View and print official sovereign verification certificate with tamper-evident QR seal"
          >
            <IconFile size={13} />
            Sovereign Certificate
          </a>
          <button
            className="btn btn-outline btn-sm"
            onClick={handleReprocess}
            disabled={isReprocessing || isFieldOfficer}
            title={isFieldOfficer ? 'Field Officers cannot reprocess documents.' : ''}
          >
            <IconRefresh size={13} className={isReprocessing ? 'animate-spin' : ''} />
            {isReprocessing ? 'Enqueueing...' : 'Reprocess'}
          </button>
          <button
            className="btn btn-success btn-sm"
            onClick={handleVerify}
            disabled={doc.status === 'verified' || isVerifying || isFieldOfficer}
            title={
              isFieldOfficer
                ? 'Only Verifying Officers and Admins may verify documents.'
                : doc.status === 'verified'
                ? 'Document is already verified.'
                : ''
            }
          >
            <IconCheck size={14} />
            {isVerifying ? 'Signing...' : doc.status === 'verified' ? 'Verified & Sealed' : 'Sign & Verify Record'}
          </button>
        </div>
      </div>

      {/* Fraud Shield Duplicate Alert */}
      {suspectedMatch && (
        <div className="gov-alert gov-alert-danger">
          <IconAlert size={18} />
          <div>
            <strong>Fraud Shield Warning — Potential Duplicate Land Record Detected:</strong>
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
            <a
              href={fileUrl}
              target="_blank"
              rel="noreferrer"
              download={doc.filename}
              className="btn btn-header-outline btn-sm"
            >
              <IconDownload size={13} />
              Download Original
            </a>
          </div>

          <div className="preview-content">
            {isImage ? (
              <img src={fileUrl} alt={doc.filename} />
            ) : (
              <iframe
                src={fileUrl}
                title="Scanned Deed Document Viewer"
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
                Cryptographic Integrity & SHA-256 Seal
              </h3>
              <span className="badge badge-verified">
                <span className="status-dot status-dot-verified" />
                SECURED_VERIFIED
              </span>
            </div>
            <div className="card-body" style={{ padding: '12px 16px', fontSize: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'center' }}>
                <span style={{ color: 'var(--slate-500)' }}>SHA-256 File Seal:</span>
                <span className="hash-chip" title={integrity?.sha256_hash}>
                  {integrity?.sha256_hash ? `${integrity.sha256_hash.substring(0, 24)}...` : 'N/A'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--slate-500)' }}>Jurisdiction:</span>
                <strong>{jurisdiction}</strong>
              </div>
            </div>
          </div>

          {/* Extracted Fields Table */}
          <div className="card" style={{ marginBottom: 0, flex: 1 }}>
            <div className="card-header">
              <div>
                <h3 className="card-title">Extracted Legal Entities & Confidence Scores</h3>
                <div className="card-subtitle">
                  Inspect extracted survey numbers, owners, and stamp details before verification
                </div>
              </div>
            </div>

            <div className="card-body" style={{ padding: 0 }}>
              <div className="table-responsive">
                <table className="gov-table">
                  <thead>
                    <tr>
                      <th>Entity Field</th>
                      <th>Extracted Value</th>
                      <th style={{ width: 120 }}>Confidence</th>
                      <th>Status</th>
                      <th style={{ textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!doc.extracted_fields || doc.extracted_fields.length === 0 ? (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', padding: 24, color: 'var(--slate-500)' }}>
                          No entity fields extracted yet. Document may still be processing.
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

                        return (
                          <tr key={field.field_name}>
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
                                  Needs Review
                                </span>
                              ) : (
                                <span className="badge badge-verified">
                                  <span className="status-dot status-dot-verified" />
                                  Verified
                                </span>
                              )}
                            </td>
                            <td style={{ textAlign: 'right' }}>
                              <button
                                className="btn btn-outline btn-sm"
                                disabled={isFieldOfficer}
                                title={isFieldOfficer ? 'Field Officers cannot edit extracted fields.' : ''}
                                onClick={() => {
                                  setSelectedField(field);
                                  setIsFieldModalOpen(true);
                                }}
                              >
                                <IconEdit size={12} />
                                Correct
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
                State Revenue Gateways (Mock Integrations)
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
                title={isFieldOfficer ? 'Field Officers cannot push integrations.' : ''}
              >
                {isPushingLrms ? 'Connecting...' : 'Push to State LRMS'}
              </button>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => handlePushIntegration('gis')}
                disabled={isPushingGis || isFieldOfficer}
                title={isFieldOfficer ? 'Field Officers cannot push integrations.' : ''}
              >
                {isPushingGis ? 'Connecting...' : 'Push to State GIS Portal'}
              </button>
              <span style={{ fontSize: 11, color: 'var(--slate-500)' }}>
                *Official gateway for Land Records Modernization System & Cadastral GIS layers.
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
