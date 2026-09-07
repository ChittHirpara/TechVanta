import React from 'react';

export default function GovStrip() {
  return (
    <div className="gov-strip">
      <div className="gov-strip-left">
        <span className="gov-strip-badge">GOVERNMENT OF INDIA</span>
        <span className="gov-strip-sep">•</span>
        <span>DIGITAL INDIA LAND RECORDS MODERNIZATION PROGRAMME (DILRMP)</span>
      </div>
      <div className="gov-strip-right">
        <span className="status-pill-subtle">
          <span className="status-dot-pulse" />
          Sovereign Node Active
        </span>
        <span className="gov-strip-sep">•</span>
        <span>GIGW Compliant</span>
        <span className="gov-strip-sep">•</span>
        <span className="font-mono">v1.0.0</span>
      </div>
    </div>
  );
}
