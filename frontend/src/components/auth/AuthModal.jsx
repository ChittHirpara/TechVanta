import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';

export default function AuthModal({ isOpen, initialTab = 'login', onClose, onSuccess, showToast }) {
  const { login, register } = useAuth();
  const [activeTab, setActiveTab] = useState(initialTab);

  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Register form state
  const [regUsername, setRegUsername] = useState('');
  const [regFullName, setRegFullName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regRole, setRegRole] = useState('field_officer');

  // Loading & error state
  const [errorMsg, setErrorMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setIsLoading(true);

    try {
      const user = await login(loginUsername.trim(), loginPassword);
      showToast?.(`Welcome back, Officer ${user.full_name || user.username}!`, 'success');
      onSuccess?.();
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Authentication failed. Please check credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setIsLoading(true);

    try {
      const payload = {
        username: regUsername.trim(),
        full_name: regFullName.trim() || null,
        email: regEmail.trim(),
        password: regPassword,
        role: regRole,
      };

      const newUser = await register(payload);
      showToast?.(`Officer account '${newUser.username}' registered successfully! Please sign in.`, 'success');
      setActiveTab('login');
      setLoginUsername(newUser.username);
      setLoginPassword('');
    } catch (err) {
      setErrorMsg(err.message || 'Registration failed. Please check information.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="card-title">
            {activeTab === 'login' ? '🔐 Official Departmental Sign In' : '📝 New Officer Registration'}
          </h3>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Auth Tab Switcher */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', background: '#fafbfc' }}>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            style={{
              flex: 1,
              borderRadius: 0,
              borderTop: 'none',
              borderLeft: 'none',
              borderBottom: activeTab === 'login' ? '2px solid var(--gov-navy-800)' : 'none',
              fontWeight: activeTab === 'login' ? 700 : 500,
              color: activeTab === 'login' ? 'var(--gov-navy-900)' : 'var(--slate-600)',
            }}
            onClick={() => {
              setActiveTab('login');
              setErrorMsg('');
            }}
          >
            Existing Officer Sign In
          </button>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            style={{
              flex: 1,
              borderRadius: 0,
              borderTop: 'none',
              borderRight: 'none',
              borderBottom: activeTab === 'register' ? '2px solid var(--gov-navy-800)' : 'none',
              fontWeight: activeTab === 'register' ? 700 : 500,
              color: activeTab === 'register' ? 'var(--gov-navy-900)' : 'var(--slate-600)',
            }}
            onClick={() => {
              setActiveTab('register');
              setErrorMsg('');
            }}
          >
            New Officer Registration
          </button>
        </div>

        <div className="modal-body">
          {errorMsg && (
            <div className="gov-alert gov-alert-danger">
              <div>{errorMsg}</div>
            </div>
          )}

          {activeTab === 'login' ? (
            <form onSubmit={handleLoginSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="login-username">
                  Official Username / Employee ID
                </label>
                <input
                  id="login-username"
                  type="text"
                  className="form-control"
                  placeholder="e.g. patwari_jaipur"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="login-password">
                  Security Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  className="form-control"
                  placeholder="Enter authorized password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" className="btn btn-outline" onClick={onClose}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isLoading}>
                  {isLoading ? 'Verifying...' : 'Sign In to Portal'}
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegisterSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="reg-username">
                  Official Username *
                </label>
                <input
                  id="reg-username"
                  type="text"
                  className="form-control"
                  placeholder="e.g. inspector_patel"
                  value={regUsername}
                  onChange={(e) => setRegUsername(e.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-fullname">
                  Full Legal Name
                </label>
                <input
                  id="reg-fullname"
                  type="text"
                  className="form-control"
                  placeholder="e.g. Rajesh Kumar Sharma"
                  value={regFullName}
                  onChange={(e) => setRegFullName(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-email">
                  Official Email Address *
                </label>
                <input
                  id="reg-email"
                  type="email"
                  className="form-control"
                  placeholder="e.g. rajesh.sharma@rajasthan.gov.in"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-password">
                  Password (Minimum 8 Characters) *
                </label>
                <input
                  id="reg-password"
                  type="password"
                  className="form-control"
                  placeholder="Create a strong passphrase"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-role">
                  Departmental Role & Jurisdiction *
                </label>
                <select
                  id="reg-role"
                  className="form-control"
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                >
                  <option value="field_officer">Field Officer (Patwari / Talati) — Scoped Ingestion & Review</option>
                  <option value="verifier">Verifying Officer (Tehsildar / Naib Tehsildar) — Verification Sign-Off</option>
                  <option value="admin">District Administrator — Full System Governance</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" className="btn btn-outline" onClick={onClose}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-saffron" disabled={isLoading}>
                  {isLoading ? 'Registering...' : 'Complete Officer Registration'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
