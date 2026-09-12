import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { jurisdictionsApi } from '../../api/client';
import { IconShield, IconPlus, IconRefresh, IconTrash, IconCheck } from '../common/Icons';

export default function JurisdictionManagement({ showToast }) {
  const { t } = useTranslation();
  const [jurisdictions, setJurisdictions] = useState([]);
  const [verifiers, setVerifiers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Form State
  const [selectedUserId, setSelectedUserId] = useState('');
  const [district, setDistrict] = useState('');
  const [tehsil, setTehsil] = useState('');
  const [village, setVillage] = useState('');

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [jList, vList] = await Promise.all([
        jurisdictionsApi.list(),
        jurisdictionsApi.getVerifiers(),
      ]);
      setJurisdictions(jList || []);
      setVerifiers(vList || []);
      if (vList && vList.length > 0 && !selectedUserId) {
        setSelectedUserId(String(vList[0].id));
      }
    } catch (err) {
      setError(err.message || 'Failed to load jurisdiction mappings.');
    } finally {
      setIsLoading(false);
    }
  }, [selectedUserId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAssign = async (e) => {
    e.preventDefault();
    if (!selectedUserId || !district.trim()) {
      showToast?.('Please select a verifier and enter a district.', 'warning');
      return;
    }
    setIsSubmitting(true);
    try {
      await jurisdictionsApi.create({
        user_id: parseInt(selectedUserId, 10),
        district: district.trim(),
        tehsil: tehsil.trim() || undefined,
        village: village.trim() || undefined,
      });
      showToast?.('Jurisdiction assigned successfully.', 'success');
      setDistrict('');
      setTehsil('');
      setVillage('');
      fetchData();
    } catch (err) {
      showToast?.(err.message || 'Failed to assign jurisdiction.', 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Remove jurisdiction mapping #${id}?`)) return;
    try {
      await jurisdictionsApi.delete(id);
      showToast?.('Jurisdiction assignment removed.', 'info');
      fetchData();
    } catch (err) {
      showToast?.(err.message || 'Failed to delete assignment.', 'error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Assignment Creation Form */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <IconShield size={16} />
              Assign Verifier Jurisdiction
            </h2>
            <div className="card-subtitle">
              Map revenue boundaries (District, Tehsil, Village) to specific verifiers for auto-routing
            </div>
          </div>
        </div>

        <div className="card-body">
          <form onSubmit={handleAssign} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, alignItems: 'flex-end' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Verifier Officer</label>
              <select
                className="form-control"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                required
              >
                {verifiers.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.username} ({v.role} - {v.jurisdiction_count} assigned)
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">District (Required)</label>
              <input
                type="text"
                className="form-control"
                placeholder="e.g. Jaipur, Kota, Udaipur"
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                required
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Tehsil (Optional)</label>
              <input
                type="text"
                className="form-control"
                placeholder="Leave blank for entire district"
                value={tehsil}
                onChange={(e) => setTehsil(e.target.value)}
              />
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Village (Optional)</label>
              <input
                type="text"
                className="form-control"
                placeholder="Leave blank for entire tehsil"
                value={village}
                onChange={(e) => setVillage(e.target.value)}
              />
            </div>

            <div>
              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', height: 38 }}
                disabled={isSubmitting || !district.trim()}
              >
                <IconPlus size={14} />
                {isSubmitting ? 'Assigning...' : 'Assign Jurisdiction'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Existing Assignments Table */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Active Jurisdiction Assignments</h2>
            <div className="card-subtitle">
              {jurisdictions.length} active coverage mapping(s) configured
            </div>
          </div>
          <button className="btn btn-outline btn-sm" onClick={fetchData} disabled={isLoading}>
            <IconRefresh size={12} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        <div className="card-body" style={{ padding: 0 }}>
          {error ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--rose-700)' }}>{error}</div>
          ) : (
            <div className="table-responsive">
              <table className="gov-table">
                <thead>
                  <tr>
                    <th style={{ width: 80 }}>ID</th>
                    <th>Verifier User</th>
                    <th>District</th>
                    <th>Tehsil</th>
                    <th>Village</th>
                    <th>Created</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                        Loading jurisdiction mappings...
                      </td>
                    </tr>
                  ) : jurisdictions.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: 36, color: 'var(--slate-500)' }}>
                        No jurisdiction assignments configured yet. All incoming documents will route to the Admin Escalation Queue.
                      </td>
                    </tr>
                  ) : (
                    jurisdictions.map((j) => (
                      <tr key={j.id}>
                        <td>
                          <span className="hash-chip">#{j.id}</span>
                        </td>
                        <td>
                          <strong>{j.verifier_username || `User #${j.user_id}`}</strong>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600, color: 'var(--gov-navy-900)' }}>{j.district}</span>
                        </td>
                        <td>
                          {j.tehsil ? (
                            <span>{j.tehsil}</span>
                          ) : (
                            <span style={{ color: 'var(--slate-400)', fontStyle: 'italic' }}>Entire District</span>
                          )}
                        </td>
                        <td>
                          {j.village ? (
                            <span>{j.village}</span>
                          ) : (
                            <span style={{ color: 'var(--slate-400)', fontStyle: 'italic' }}>All Villages</span>
                          )}
                        </td>
                        <td style={{ fontSize: 12, color: 'var(--slate-600)' }}>
                          {j.created_at ? new Date(j.created_at).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            className="btn btn-outline btn-sm"
                            style={{ color: 'var(--rose-700)', borderColor: 'var(--rose-200)' }}
                            onClick={() => handleDelete(j.id, j.verifier_username)}
                          >
                            <IconTrash size={12} />
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))
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
