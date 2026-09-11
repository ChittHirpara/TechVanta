import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { documentsApi } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { IconSearch, IconUpload, IconShield, IconRefresh } from '../common/Icons';

export default function Registry({ onSelectDoc, onNavigateToUpload, onDocCountUpdate }) {
  const { t } = useTranslation();
  const { isFieldOfficer } = useAuth();

  const [documents, setDocuments] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 15;

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [districtFilter, setDistrictFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchDocuments = useCallback(
    async (currentPage = 1) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await documentsApi.list({
          page: currentPage,
          pageSize,
          status: statusFilter || undefined,
          district: districtFilter || undefined,
          search: search.trim() || undefined,
        });

        setDocuments(res.items || []);
        setTotal(res.total || 0);
        setPage(currentPage);
        onDocCountUpdate?.(res.total || 0);
      } catch (err) {
        setError(err.message || 'Failed to fetch land records.');
      } finally {
        setIsLoading(false);
      }
    },
    [statusFilter, districtFilter, search, onDocCountUpdate]
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchDocuments(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [fetchDocuments]);

  // Silent auto-refresh for newly uploaded documents without triggering full loader
  useEffect(() => {
    const pollInterval = setInterval(() => {
      documentsApi
        .list({
          page,
          pageSize,
          status: statusFilter || undefined,
          district: districtFilter || undefined,
          search: search.trim() || undefined,
        })
        .then((res) => {
          if (res && res.items) {
            setDocuments(res.items);
            setTotal(res.total || 0);
            onDocCountUpdate?.(res.total || 0);
          }
        })
        .catch(() => {});
    }, 5000);
    return () => clearInterval(pollInterval);
  }, [page, pageSize, statusFilter, districtFilter, search, onDocCountUpdate]);

  const handleResetFilters = () => {
    setSearch('');
    setStatusFilter('');
    setDistrictFilter('');
  };

  const startRecord = (page - 1) * pageSize + 1;
  const endRecord = Math.min(page * pageSize, total);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2 className="card-title">{t('registry.title')}</h2>
          <div className="card-subtitle">
            {t('registry.subtitle')}
          </div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={onNavigateToUpload}>
          <IconUpload size={13} />
          {t('registry.ingest_new')}
        </button>
      </div>

      {/* Filter Toolbar */}
      <div
        style={{
          padding: '12px 20px',
          background: '#fafbfc',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <div style={{ flex: 1, minWidth: 240, position: 'relative' }}>
          <div style={{ position: 'absolute', left: 10, top: 10, color: 'var(--slate-400)', pointerEvents: 'none' }}>
            <IconSearch size={14} />
          </div>
          <input
            type="text"
            className="form-control"
            style={{ paddingLeft: 32 }}
            placeholder={t('registry.search_placeholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div style={{ width: 180 }}>
          <select
            className="form-control"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">{t('registry.filter_all')}</option>
            <option value="needs_review">{t('registry.status.needs_review')}</option>
            <option value="verified">{t('registry.status.verified')}</option>
            <option value="processing">{t('registry.status.processing')}</option>
            <option value="uploaded">{t('registry.status.uploaded')}</option>
          </select>
        </div>

        {!isFieldOfficer && (
          <div style={{ width: 180 }}>
            <input
              type="text"
              className="form-control"
              placeholder={t('registry.filter_district')}
              value={districtFilter}
              onChange={(e) => setDistrictFilter(e.target.value)}
            />
          </div>
        )}

        <button className="btn btn-outline btn-sm" onClick={handleResetFilters}>
          <IconRefresh size={12} />
          {t('registry.btn_reset')}
        </button>
      </div>

      {/* Registry Table */}
      <div className="card-body" style={{ padding: 0 }}>
        {error ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--rose-700)' }}>
            {error}
          </div>
        ) : (
          <div className="table-responsive">
            <table className="gov-table">
              <thead>
                <tr>
                  <th style={{ width: 90 }}>{t('registry.columns.doc_id')}</th>
                  <th>{t('registry.columns.filename')}</th>
                  <th>{t('registry.columns.jurisdiction')}</th>
                  <th>{t('registry.columns.uploaded_date')}</th>
                  <th>{t('registry.columns.status')}</th>
                  <th style={{ textAlign: 'right' }}>{t('registry.columns.action')}</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                      {t('registry.loading')}
                    </td>
                  </tr>
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                      {t('registry.empty')}
                    </td>
                  </tr>
                ) : (
                  documents.map((doc) => {
                    const uploadDate = doc.created_at
                      ? new Date(doc.created_at).toLocaleDateString(undefined, {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '—';

                    const jurisdiction =
                      [doc.district, doc.tehsil, doc.village].filter(Boolean).join(' / ') || 'Not Specified';

                    return (
                      <tr key={doc.id}>
                        <td>
                          <span className="hash-chip">#{doc.id}</span>
                        </td>
                        <td>
                          <strong>{doc.filename}</strong>
                        </td>
                        <td>{jurisdiction}</td>
                        <td style={{ color: 'var(--slate-600)', fontSize: 12 }}>{uploadDate}</td>
                        <td>
                          <span className={`badge badge-${doc.status}`}>
                            <span className={`status-dot status-dot-${doc.status}`} />
                            {t(`registry.status.${doc.status}`) || doc.status.replace('_', ' ')}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => onSelectDoc(doc.id)}
                          >
                            <IconShield size={12} />
                            {doc.status === 'verified' ? t('registry.actions.view') : t('registry.actions.verify')}
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

        {/* Pagination Bar */}
        <div
          style={{
            padding: '12px 20px',
            background: '#fafbfc',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: 12, color: 'var(--slate-600)' }}>
            {total > 0 ? `Showing ${startRecord}-${endRecord} of ${total} records` : '0 records'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn btn-outline btn-sm"
              disabled={page <= 1 || isLoading}
              onClick={() => fetchDocuments(page - 1)}
            >
              {t('registry.prev_page')}
            </button>
            <button
              className="btn btn-outline btn-sm"
              disabled={endRecord >= total || isLoading}
              onClick={() => fetchDocuments(page + 1)}
            >
              {t('registry.next_page')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
