/**
 * TechVanta / BhoomiScan AI - Theme Tokens
 * Direct 1-to-1 match with sovereign land registry design system in frontend/src/index.css
 */

export const colors = {
  // Brand Palette (Government Navy)
  govNavy950: '#061325',
  govNavy900: '#0b1f3a',
  govNavy850: '#0e2746',
  govNavy800: '#133458',
  govNavy700: '#1b497b',
  govNavy600: '#2563eb',
  govNavy300: '#6b93c4',
  govNavy100: '#e2eaf4',
  govNavy50: '#f0f4f9',

  // Sovereign Accent (Saffron Amber)
  saffron900: '#78350f',
  saffron700: '#b45309',
  saffron600: '#d97706',
  saffron500: '#f59e0b',
  saffron100: '#fef3c7',
  saffron50: '#fffbeb',

  // Neutral Slate
  slate950: '#020617',
  slate900: '#0f172a',
  slate800: '#1e293b',
  slate700: '#334155',
  slate600: '#475569',
  slate500: '#64748b',
  slate400: '#94a3b8',
  slate300: '#cbd5e1',
  slate200: '#e2e8f0',
  slate100: '#f1f5f9',
  slate50: '#f8fafc',

  // Verification Emerald
  emerald800: '#065f46',
  emerald700: '#047857',
  emerald600: '#059669',
  emerald500: '#10b981',
  emerald100: '#d1fae5',
  emerald50: '#ecfdf5',

  // Danger Crimson / Rose
  rose800: '#991b1b',
  rose700: '#b91c1c',
  rose600: '#dc2626',
  rose300: '#fca5a5',
  rose100: '#fee2e2',
  rose50: '#fef2f2',

  // Surfaces & Base
  bgPage: '#f4f6fa',
  bgCard: '#ffffff',
  borderCard: '#e2e8f0',
  borderSubtle: '#edf2f7',
  white: '#ffffff',
  black: '#000000',
};

export const typography = {
  fontFamily: {
    regular: 'System',
    mono: 'monospace',
  },
  sizes: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 18,
    xl: 22,
    xxl: 26,
  },
  weights: {
    regular: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
};

export const radius = {
  xs: 4,
  sm: 6,
  md: 10,
  lg: 14,
  full: 9999,
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const shadows = {
  sm: {
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 2,
    elevation: 2,
  },
  md: {
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
    elevation: 4,
  },
  lg: {
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 12,
    elevation: 8,
  },
};

export default {
  colors,
  typography,
  radius,
  spacing,
  shadows,
};
