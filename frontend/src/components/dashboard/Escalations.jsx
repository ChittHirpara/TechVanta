import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { jurisdictionsApi } from '../../api/client';
import { IconAlert, IconClock, IconShield, IconRefresh, IconCheck } from '../common/Icons';

export default function Escalations({ onSelectDoc }) {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [activeSubTab, setActiveSubTab] = useState('unassigned'); // 'unassigned' | 'sla' | 'fraud'
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchEscalations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await jurisdictionsApi.getEscalations();
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to fetch escalation queue.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEscalations();
    const interval = setInterval(() => {
      jurisdictionsApi.getEscalations().then((res) => setData(res)).catch(() => {});
    }, 8000);
    return () => clearInterval(interval);
  }, [fetchEscalations]);

  const unassignedDocs = data?.unassigned_documents || [];
  const slaDocs = data?.sla_breached_documents || [];
  const fraudDocs = data?.fraud_risk_documents || [];

  const currentDocs =
    activeSubTab === 'unassigned'
      ? unassignedDocs
      : activeSubTab === 'sla'
      ? slaDocs
      : fraudDocs;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <IconAlert size={18} className="text-rose-600" />
            Admin Escalation Command Center
          </h2>
          <div className="card-subtitle">
            Critical exceptions requiring immediate administrative intervention and triage
          </div>
        </div>
        <button className="btn btn-outline btn-sm" onClick={fetchEscalations} disabled={isLoading}>
          <IconRefresh size={12} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Escalation Summary KPI Strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 12,
          padding: '16px 20px',
          background: '#f8fafc',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <button
          className={`stat-box ${activeSubTab === 'unassigned' ? 'border-primary' : ''}`}
          style={{
            cursor: 'pointer',
            textAlign: 'left',
            background: activeSubTab === 'unassigned' ? '#eff6ff' : '#fff',
            borderColor: activeSubTab === 'unassigned' ? 'var(--gov-navy-600)' : 'var(--border-subtle)',
          }}
          onClick={() => setActiveSubTab('unassigned')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--slate-600)' }}>Unassigned Jurisdiction</span>
            <span className="badge badge-needs_review">{unassignedDocs.length}</span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4, color: 'var(--amber-700)' }}>
            {unassignedDocs.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>No verifier mapped to area</div>
        </button>

        <button
          className={`stat-box ${activeSubTab === 'sla' ? 'border-primary' : ''}`}
          style={{
            cursor: 'pointer',
            textAlign: 'left',
            background: activeSubTab === 'sla' ? '#eff6ff' : '#fff',
            borderColor: activeSubTab === 'sla' ? 'var(--gov-navy-600)' : 'var(--border-subtle)',
          }}
          onClick={() => setActiveSubTab('sla')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--slate-600)' }}>SLA Breached (&gt;48h)</span>
            <span className="badge badge-needs_review">{slaDocs.length}</span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4, color: 'var(--rose-700)' }}>
            {slaDocs.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>Overdue verification queue</div>
        </button>

        <button
          className={`stat-box ${activeSubTab === 'fraud' ? 'border-primary' : ''}`}
          style={{
            cursor: 'pointer',
            textAlign: 'left',
            background: activeSubTab === 'fraud' ? '#eff6ff' : '#fff',
            borderColor: activeSubTab === 'fraud' ? 'var(--gov-navy-600)' : 'var(--border-subtle)',
          }}
          onClick={() => setActiveSubTab('fraud')}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--slate-600)' }}>High Fraud / Risk</span>
            <span className="badge badge-needs_review">{fraudDocs.length}</span>
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4, color: 'var(--rose-700)' }}>
            {fraudDocs.length}
          </div>
          <div style={{ fontSize: 11, color: 'var(--slate-500)' }}>Major discrepancy flags</div>
        </button>
      </div>

      {/* Escalated Document List */}
      <div className="card-body" style={{ padding: 0 }}>
        {error ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--rose-700)' }}>{error}</div>
        ) : (
          <div className="table-responsive">
            <table className="gov-table">
              <thead>
                <tr>
                  <th style={{ width: 90 }}>ID</th>
                  <th>Filename</th>
                  <th>Jurisdiction</th>
                  <th>Status</th>
                  <th>Escalation Reason</th>
                  <th>Created</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                      Loading escalation records...
                    </td>
                  </tr>
                ) : currentDocs.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                      <IconCheck size={20} className="text-emerald-600" style={{ display: 'inline-block', marginBottom: 6 }} />
                      <div>No escalated documents in this category. All records are healthy.</div>
                    </td>
                  </tr>
                ) : (
                  currentDocs.map((doc) => {
                    const uploadDate = doc.created_at
                      ? new Date(doc.created_at).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '—';

                    const jurisdiction =
                      [doc.district, doc.tehsil, doc.village].filter(Boolean).join(' / ') || 'Unspecified';

                    return (
                      <tr key={doc.id}>
                        <td>
                          <span className="hash-chip">#{doc.id}</span>
                        </td>
                        <td>
                          <strong>{doc.filename}</strong>
                        </td>
                        <td>{jurisdiction}</td>
                        <td>
                          <span className={`badge badge-${doc.status}`}>
                            <span className={`status-dot status-dot-${doc.status}`} />
                            {doc.status}
                          </span>
                        </td>
                        <td>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: 4,
                              background: '#fee2e2',
                              color: '#991b1b',
                              fontSize: 11,
                              fontWeight: 700,
                            }}
                          >
                            {doc.escalation_reason || (activeSubTab === 'sla' ? 'SLA_BREACH' : 'ESCALATED')}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--slate-600)' }}>{uploadDate}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn-primary btn-sm" onClick={() => onSelectDoc(doc.id)}>
                            <IconShield size={12} />
                            Open Workspace
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
