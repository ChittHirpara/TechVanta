import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { documentsApi } from '../../api/client';

export default function FieldModal({ isOpen, docId, field, onClose, onUpdated, showToast }) {
  const { t } = useTranslation();
  const [newVal, setNewVal] = useState('');
  const [note, setNote] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (field) {
      setNewVal(field.value || '');
      setNote('');
      setError('');
    }
  }, [field]);

  if (!isOpen || !field) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSaving(true);

    try {
      await documentsApi.patchField(docId, field.field_name, {
        value: newVal.trim(),
        note: note.trim() || null,
      });

      showToast?.(t('modals.field.toast_updated', { fieldName: field.field_name }), 'success');
      onUpdated?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to update field value.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="card-title">{t('modals.field.title')}</h3>
          <button className="btn btn-outline btn-sm" onClick={onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="gov-alert gov-alert-danger">
                <div>{error}</div>
              </div>
            )}

            <div className="form-group">
              <label className="form-label">{t('modals.field.entity_field')}</label>
              <input
                type="text"
                className="form-control"
                value={field.field_name}
                disabled
                style={{ background: 'var(--slate-100)', fontFamily: 'var(--font-mono)' }}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{t('modals.field.original_value')}</label>
              <input
                type="text"
                className="form-control"
                value={field.value || t('modals.field.empty_val')}
                disabled
                style={{ background: 'var(--slate-100)' }}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{t('modals.field.corrected_value')}</label>
              <input
                type="text"
                className="form-control"
                value={newVal}
                onChange={(e) => setNewVal(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <label className="form-label">{t('modals.field.reason')}</label>
              <input
                type="text"
                className="form-control"
                placeholder={t('modals.field.reason_placeholder')}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>
              {t('modals.cancel')}
            </button>
            <button type="submit" className="btn btn-primary" disabled={isSaving}>
              {isSaving ? t('modals.saving') : t('modals.field.confirm')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
