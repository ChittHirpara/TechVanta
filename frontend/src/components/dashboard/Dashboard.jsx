import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { dashboardApi } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { IconRefresh, IconUpload, IconFolder, IconCheck, IconAlert, IconShield } from '../common/Icons';

export default function Dashboard({ onNavigateToUpload, onNavigateToRegistry }) {
  const { t } = useTranslation();
  const { user, isFieldOfficer } = useAuth();
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await dashboardApi.getStats();
      setStats(data);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard metrics.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return (
    <div className="dashboard-container">
      {isFieldOfficer && (
        <div className="gov-alert gov-alert-info">
          <IconShield size={16} />
          <div>
            <strong>{t('dashboard.stats.field_officer_mode')}:</strong> {t('dashboard.jurisdiction_scoped', { jurisdiction: `uploaded_by = ${user?.username}` })}
          </div>
        </div>
      )}

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-box">
          <div className="stat-header-row">
            <span className="stat-label">{t('dashboard.stats.total_deeds')}</span>
            <IconFolder size={18} className="stat-box-icon text-slate-400" />
          </div>
          <div className="stat-value">{isLoading ? '—' : (stats?.total_documents || 0).toLocaleString()}</div>
          <div className="stat-hint">{t('dashboard.stats.total_deeds_desc')}</div>
        </div>

        <div className="stat-box stat-accent-emerald">
          <div className="stat-header-row">
            <span className="stat-label">{t('dashboard.stats.verified_sealed')}</span>
            <IconCheck size={18} className="stat-box-icon text-emerald-600" />
          </div>
          <div className="stat-value text-emerald-700">
            {isLoading ? '—' : (stats?.verified || 0).toLocaleString()}
          </div>
          <div className="stat-hint">{t('dashboard.stats.verified_sealed_desc')}</div>
        </div>

        <div className="stat-box stat-accent-amber">
          <div className="stat-header-row">
            <span className="stat-label">{t('dashboard.stats.needs_review')}</span>
            <IconAlert size={18} className="stat-box-icon text-amber-600" />
          </div>
          <div className="stat-value text-amber-700">
            {isLoading ? '—' : (stats?.pending_review || 0).toLocaleString()}
          </div>
          <div className="stat-hint">{t('dashboard.stats.awaiting_audit')}</div>
        </div>

        <div className="stat-box stat-accent-rose">
          <div className="stat-header-row">
            <span className="stat-label">{t('dashboard.district_breakdown.flagged')}</span>
            <IconAlert size={18} className="stat-box-icon text-rose-600" />
          </div>
          <div className="stat-value text-rose-700">
            {isLoading ? '—' : (stats?.flagged_field_count || 0).toLocaleString()}
          </div>
          <div className="stat-hint">{t('dashboard.stats.needs_review_desc')}</div>
        </div>

        <div className="stat-box stat-accent-navy">
          <div className="stat-header-row">
            <span className="stat-label">{t('dashboard.stats.avg_confidence')}</span>
            <IconShield size={18} className="stat-box-icon text-navy-600" />
          </div>
          <div className="stat-value text-gov-navy-900">
            {isLoading ? '—' : stats?.avg_confidence !== null && stats?.avg_confidence !== undefined ? `${Math.round(stats.avg_confidence * 100)}%` : 'N/A'}
          </div>
          <div className="stat-hint">{t('dashboard.stats.avg_confidence_desc')}</div>
        </div>
      </div>

      {/* District Digitization Breakdown Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">{t('dashboard.district_breakdown.title')}</h2>
            <div className="card-subtitle">{t('dashboard.district_breakdown.subtitle')}</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-outline btn-sm" onClick={fetchStats} disabled={isLoading}>
              <IconRefresh size={13} className={isLoading ? 'animate-spin' : ''} />
              {isLoading ? 'Refreshing...' : t('dashboard.refresh')}
            </button>
            <button className="btn btn-primary btn-sm" onClick={onNavigateToUpload}>
              <IconUpload size={13} />
              {t('nav.ingestion')}
            </button>
          </div>
        </div>

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
                    <th>{t('dashboard.district_breakdown.district')}</th>
                    <th>{t('dashboard.district_breakdown.total')}</th>
                    <th>{t('dashboard.district_breakdown.verified')}</th>
                    <th>{t('dashboard.stats.needs_review')}</th>
                    <th>{t('registry.status.processing')}</th>
                    <th>{t('dashboard.district_breakdown.completion')}</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                        {t('dashboard.loading_metrics')}
                      </td>
                    </tr>
                  ) : !stats?.district_breakdown || stats.district_breakdown.length === 0 ? (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                        {t('dashboard.no_districts')}
                      </td>
                    </tr>
                  ) : (
                    stats.district_breakdown.map((d, index) => {
                      const total = d.total_documents || 0;
                      const verified = d.verified || 0;
                      const rate = total > 0 ? Math.round((verified / total) * 100) : 0;
                      return (
                        <tr key={d.district || index}>
                          <td>
                            <strong>{d.district || t('dashboard.unassigned_district')}</strong>
                          </td>
                          <td className="font-mono">{total.toLocaleString()}</td>
                          <td>
                            <span className="badge badge-verified">{verified}</span>
                          </td>
                          <td>
                            <span className="badge badge-needs_review">{d.needs_review}</span>
                          </td>
                          <td>
                            <span className="badge badge-processing">{d.processing}</span>
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <div
                                style={{
                                  flex: 1,
                                  height: 6,
                                  background: 'var(--slate-200)',
                                  borderRadius: 999,
                                  overflow: 'hidden',
                                  minWidth: 80,
                                }}
                              >
                                <div
                                  style={{
                                    height: '100%',
                                    width: `${rate}%`,
                                    background: 'var(--emerald-600)',
                                    borderRadius: 999,
                                  }}
                                />
                              </div>
                              <span className="font-mono text-xs font-bold">{rate}%</span>
                            </div>
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
    </div>
  );
}
