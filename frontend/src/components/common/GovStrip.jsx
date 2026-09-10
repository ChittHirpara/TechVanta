import React from 'react';
import { useTranslation } from 'react-i18next';

export default function GovStrip() {
  const { t } = useTranslation();

  return (
    <div className="gov-strip">
      <div className="gov-strip-left">
        <span className="gov-strip-badge">{t('gov_strip.title')}</span>
        <span className="gov-strip-sep">•</span>
        <span>{t('gov_strip.dilrmp')}</span>
      </div>
      <div className="gov-strip-right">
        <span className="status-pill-subtle">
          <span className="status-dot-pulse" />
          {t('gov_strip.node_active')}
        </span>
        <span className="gov-strip-sep">•</span>
        <span>{t('gov_strip.gigw')}</span>
        <span className="gov-strip-sep">•</span>
        <span className="font-mono">v1.0.0</span>
      </div>
    </div>
  );
}
