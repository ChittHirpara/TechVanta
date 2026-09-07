import React from 'react';
import { IconCheck, IconAlert, IconShield } from './Icons';

export default function Toast({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;

  const renderIcon = (type) => {
    switch (type) {
      case 'success':
        return <IconCheck size={16} className="text-emerald-600" />;
      case 'error':
        return <IconAlert size={16} className="text-rose-600" />;
      case 'warning':
        return <IconAlert size={16} className="text-amber-600" />;
      default:
        return <IconShield size={16} className="text-navy-600" />;
    }
  };

  return (
    <div id="toast-container">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast-${toast.type || 'info'}`}
          onClick={() => onDismiss(toast.id)}
          style={{ cursor: 'pointer' }}
        >
          <span className="toast-icon-wrapper">{renderIcon(toast.type)}</span>
          <span className="toast-message">{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
