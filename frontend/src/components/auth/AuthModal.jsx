import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../context/AuthContext';

export default function AuthModal({ isOpen, initialTab = 'login', onClose, onSuccess, showToast }) {
  const { t } = useTranslation();
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
      showToast?.(t('auth_modal.toast_welcome', { name: user.full_name || user.username }), 'success');
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
      showToast?.(t('auth_modal.toast_registered', { username: newUser.username }), 'success');
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
            {activeTab === 'login' ? `🔐 ${t('auth_modal.title_login_header')}` : `📝 ${t('auth_modal.title_register_header')}`}
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
            {t('auth_modal.tab_login')}
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
            {t('auth_modal.tab_register')}
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
                  {t('auth_modal.label_username_login')}
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
                  {t('auth_modal.label_password')}
                </label>
                <input
                  id="login-password"
                  type="password"
                  className="form-control"
                  placeholder={t('auth_modal.placeholder_password')}
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  required
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" className="btn btn-outline" onClick={onClose}>
                  {t('auth_modal.btn_cancel')}
                </button>
                <button type="submit" className="btn btn-primary" disabled={isLoading}>
                  {isLoading ? t('auth_modal.btn_verifying') : t('modals.auth.title_login')}
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegisterSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="reg-username">
                  {t('auth_modal.label_username_register')}
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
                  {t('auth_modal.label_fullname')}
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
                  {t('auth_modal.label_email')}
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
                  {t('auth_modal.label_password_register')}
                </label>
                <input
                  id="reg-password"
                  type="password"
                  className="form-control"
                  placeholder={t('modals.auth.passphrase')}
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="reg-role">
                  {t('auth_modal.label_role')}
                </label>
                <select
                  id="reg-role"
                  className="form-control"
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                >
                  <option value="field_officer">{t('modals.auth.field_officer_desc')}</option>
                  <option value="verifier">{t('modals.auth.verifier_desc')}</option>
                  <option value="admin">{t('modals.auth.admin_desc')}</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
                <button type="button" className="btn btn-outline" onClick={onClose}>
                  {t('auth_modal.btn_cancel')}
                </button>
                <button type="submit" className="btn btn-saffron" disabled={isLoading}>
                  {isLoading ? t('auth_modal.btn_registering') : t('modals.auth.title_register')}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
