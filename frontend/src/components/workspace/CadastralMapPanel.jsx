import React, { useState } from 'react';
import { IconMap, IconCheck, IconExternal } from '../common/Icons';

export default function CadastralMapPanel({ doc, fields = [] }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeLayer, setActiveLayer] = useState('cadastral'); // 'cadastral' | 'satellite'

  const fieldMap = {};
  fields.forEach((f) => {
    fieldMap[f.field_name] = f.value;
  });

  const district = doc?.district || fieldMap['district'] || 'Jaipur';
  const tehsil = doc?.tehsil || fieldMap['tehsil'] || 'Sanganer';
  const village = doc?.village || fieldMap['village'] || 'Rampur Kalan';
  const surveyNumber = fieldMap['survey_number'] || '78-B';
  const khasraNumber = fieldMap['khasra_number'] || '451/2';
  const plotArea = fieldMap['plot_area'] || '2 Bigha 14 Biswa';

  // Simulated representative geo-coordinates for Rajasthan revenue divisions
  const geoLookup = {
    Jaipur: { lat: 26.9124, lng: 75.7873, zoom: 15 },
    Jodhpur: { lat: 26.2389, lng: 73.0243, zoom: 15 },
    Ajmer: { lat: 26.4499, lng: 74.6399, zoom: 15 },
    Udaipur: { lat: 24.5854, lng: 73.7125, zoom: 15 },
    Kota: { lat: 25.2138, lng: 75.8648, zoom: 15 },
    Bikaner: { lat: 28.0229, lng: 73.3119, zoom: 15 },
  };

  const coords = geoLookup[district] || { lat: 26.9124, lng: 75.7873, zoom: 14 };

  return (
    <div className="card" style={{ marginTop: 16, overflow: 'hidden' }}>
      {/* Header Accordion Toggle */}
      <div
        style={{
          padding: '12px 18px',
          background: 'var(--gov-navy-50)',
          borderBottom: isExpanded ? '1px solid var(--slate-200)' : 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ color: 'var(--gov-navy-700)' }}>
            <IconMap size={18} />
          </div>
          <div>
            <strong style={{ fontSize: 13, color: 'var(--gov-navy-900)' }}>
              Cadastral GIS & Geolocation Boundary Inspector
            </strong>
            <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--slate-500)' }}>
              {village}, {tehsil} ({district}) • Survey #{surveyNumber}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              fontSize: 11,
              background: 'var(--gov-navy-100)',
              color: 'var(--gov-navy-800)',
              padding: '2px 8px',
              borderRadius: 4,
              fontWeight: 600,
            }}
          >
            {coords.lat.toFixed(4)}° N, {coords.lng.toFixed(4)}° E
          </span>
          <button
            className="btn btn-outline btn-sm"
            style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            {isExpanded ? 'Collapse GIS Panel ▲' : 'Expand GIS Map ▼'}
          </button>
        </div>
      </div>

      {/* Collapsible GIS Body */}
      {isExpanded && (
        <div style={{ padding: 18 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: 'var(--slate-600)' }}>
              <strong>Cadastral Layer:</strong> DILRMP Geo-referenced Khasra Parcel #{khasraNumber} (Declared Area: {plotArea})
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                className={`btn btn-sm ${activeLayer === 'cadastral' ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '3px 8px', fontSize: 11 }}
                onClick={() => setActiveLayer('cadastral')}
              >
                Cadastral Grid
              </button>
              <button
                className={`btn btn-sm ${activeLayer === 'satellite' ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '3px 8px', fontSize: 11 }}
                onClick={() => setActiveLayer('satellite')}
              >
                Satellite Hybrid
              </button>
            </div>
          </div>

          {/* Simulated High-Res Cadastral Map View */}
          <div
            style={{
              height: 260,
              background: activeLayer === 'satellite' ? '#1e293b' : '#f8fafc',
              border: '1px solid var(--slate-300)',
              borderRadius: 6,
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {/* SVG Grid / Cadastral Layer */}
            <svg
              width="100%"
              height="100%"
              viewBox="0 0 800 260"
              preserveAspectRatio="none"
              style={{ position: 'absolute', top: 0, left: 0 }}
            >
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path
                    d="M 40 0 L 0 0 0 40"
                    fill="none"
                    stroke={activeLayer === 'satellite' ? 'rgba(255,255,255,0.08)' : 'rgba(11,31,58,0.06)'}
                    strokeWidth="1"
                  />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />

              {/* Neighboring parcel outlines */}
              <polygon
                points="180,40 340,30 360,140 200,160"
                fill={activeLayer === 'satellite' ? 'rgba(255,255,255,0.05)' : '#e2e8f0'}
                stroke={activeLayer === 'satellite' ? '#64748b' : '#94a3b8'}
                strokeWidth="1.5"
                strokeDasharray="4,4"
              />
              <text x="250" y="95" fill={activeLayer === 'satellite' ? '#94a3b8' : '#64748b'} fontSize="11" fontFamily="monospace">
                Parcel 450
              </text>

              <polygon
                points="520,60 680,50 690,190 530,200"
                fill={activeLayer === 'satellite' ? 'rgba(255,255,255,0.05)' : '#e2e8f0'}
                stroke={activeLayer === 'satellite' ? '#64748b' : '#94a3b8'}
                strokeWidth="1.5"
                strokeDasharray="4,4"
              />
              <text x="590" y="125" fill={activeLayer === 'satellite' ? '#94a3b8' : '#64748b'} fontSize="11" fontFamily="monospace">
                Parcel 452
              </text>

              {/* Targeted Active Parcel Boundary (Highlighted in Emerald/Gold) */}
              <polygon
                points="350,50 510,40 520,180 360,200"
                fill="rgba(5, 150, 105, 0.22)"
                stroke="#059669"
                strokeWidth="2.5"
              />

              {/* Vertex Coordinates */}
              <circle cx="350" cy="50" r="4" fill="#047857" />
              <circle cx="510" cy="40" r="4" fill="#047857" />
              <circle cx="520" cy="180" r="4" fill="#047857" />
              <circle cx="360" cy="200" r="4" fill="#047857" />

              {/* Center Marker / Label */}
              <rect x="380" y="100" width="110" height="34" rx="4" fill="#0b1f3a" />
              <text x="435" y="115" fill="#ffffff" fontSize="10" fontWeight="bold" textAnchor="middle">
                Khasra #{khasraNumber}
              </text>
              <text x="435" y="127" fill="#86efac" fontSize="9" textAnchor="middle" fontFamily="monospace">
                {coords.lat.toFixed(4)}N, {coords.lng.toFixed(4)}E
              </text>
            </svg>

            {/* Map Overlay Badge */}
            <div
              style={{
                position: 'absolute',
                bottom: 8,
                left: 8,
                background: 'rgba(15, 23, 42, 0.85)',
                color: '#ffffff',
                padding: '4px 8px',
                borderRadius: 4,
                fontSize: 10,
                fontFamily: 'monospace',
                backdropFilter: 'blur(4px)',
              }}
            >
              Survey Scale: 1:1000 • Datum: WGS-84 • DILRMP Geo-tag Verified
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
