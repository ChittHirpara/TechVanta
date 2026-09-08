import { JSDOM } from 'jsdom';

// 1. Setup DOM globals FIRST before importing React or components
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost:5173',
  pretendToBeVisual: true,
});
global.window = dom.window;
global.document = dom.window.document;
global.sessionStorage = dom.window.sessionStorage;
global.CustomEvent = dom.window.CustomEvent;
global.HTMLElement = dom.window.HTMLElement;
global.HTMLInputElement = dom.window.HTMLInputElement;
global.HTMLButtonElement = dom.window.HTMLButtonElement;
global.EventSource = class {
  constructor() {}
  close() {}
};

// 2. Mock fetch
const mockStats = {
  total_documents: 10,
  verified: 4,
  pending_review: 3,
  flagged_field_count: 2,
  avg_confidence: 0.94,
  district_breakdown: [{ district: 'Jaipur', total_documents: 10, verified: 4, needs_review: 3, processing: 3 }],
};

const mockDocsList = {
  total: 1,
  page: 1,
  page_size: 15,
  items: [
    {
      id: 1,
      filename: '01_clean_jaipur_khasra.pdf',
      status: 'needs_review',
      district: 'Jaipur',
      tehsil: 'Sanganer',
      village: 'Shyopur',
      created_at: new Date().toISOString(),
    },
  ],
};

const mockDocDetail = {
  id: 1,
  filename: '01_clean_jaipur_khasra.pdf',
  status: 'needs_review',
  district: 'Jaipur',
  tehsil: 'Sanganer',
  village: 'Shyopur',
  extracted_fields: [
    { field_name: 'owner_name', value: 'Rameshwar Prasad Sharma', confidence_score: 0.98, is_flagged: false },
    { field_name: 'khasra_number', value: '412/1', confidence_score: 0.99, is_flagged: false },
  ],
};

global.fetch = async (url, options = {}) => {
  if (url.includes('/auth/me')) {
    const rawUser = sessionStorage.getItem('bhoomi_user');
    return { ok: true, status: 200, json: async () => (rawUser ? JSON.parse(rawUser) : { username: 'user', role: 'field_officer' }) };
  }
  if (url.includes('/dashboard/stats')) {
    return { ok: true, status: 200, json: async () => mockStats };
  }
  if (url.includes('/documents?')) {
    return { ok: true, status: 200, json: async () => mockDocsList };
  }
  if (url.includes('/documents/1/integrity')) {
    return { ok: true, status: 200, json: async () => ({ sha256_hash: 'ef2b5d...', status: 'SECURED_VERIFIED' }) };
  }
  if (url.includes('/documents/1/duplicates')) {
    return { ok: true, status: 200, json: async () => ({ has_suspected_duplicates: false, matches: [] }) };
  }
  if (url.includes('/documents/1')) {
    return { ok: true, status: 200, json: async () => mockDocDetail };
  }
  return { ok: true, status: 200, json: async () => ({}) };
};

// 3. Dynamic imports for React and components
const React = (await import('react')).default;
const { createRoot } = await import('react-dom/client');
const { act } = await import('react');
const { AuthProvider } = await import('../src/context/AuthContext.jsx');
const { default: Dashboard } = await import('../src/components/dashboard/Dashboard.jsx');
const { default: Registry } = await import('../src/components/registry/Registry.jsx');
const { default: Workspace } = await import('../src/components/workspace/Workspace.jsx');

async function testRole(roleName) {
  const container = document.getElementById('root');
  const root = createRoot(container);

  // Set auth credentials
  sessionStorage.setItem('bhoomi_token', `token_${roleName}`);
  sessionStorage.setItem('bhoomi_user', JSON.stringify({ username: `test_${roleName}`, role: roleName }));

  console.log(`\n======================================================`);
  console.log(`LIVE ROLE GATING TEST: ${roleName.toUpperCase()}`);
  console.log(`======================================================`);

  // 1. Render Dashboard
  await act(async () => {
    root.render(
      React.createElement(
        AuthProvider,
        null,
        React.createElement(Dashboard, { onNavigateToUpload: () => {}, onNavigateToRegistry: () => {} })
      )
    );
  });
  await new Promise((r) => setTimeout(r, 60));

  const dashboardHtml = container.innerHTML;
  const hasFieldOfficerBanner = dashboardHtml.includes('Field Officer Mode:');
  console.log(`[Dashboard] 'Field Officer Mode' banner present: ${hasFieldOfficerBanner}`);

  // 2. Render Registry
  await act(async () => {
    root.render(
      React.createElement(
        AuthProvider,
        null,
        React.createElement(Registry, { onSelectDoc: () => {}, onNavigateToUpload: () => {}, onDocCountUpdate: () => {} })
      )
    );
  });
  await new Promise((r) => setTimeout(r, 60));

  const districtInput = container.querySelector('input[placeholder="Filter district..."]');
  console.log(`[Registry] 'Filter district...' input present in DOM: ${districtInput !== null}`);

  // 3. Render Workspace for Record #1
  await act(async () => {
    root.render(
      React.createElement(
        AuthProvider,
        null,
        React.createElement(Workspace, { docId: 1, onBackToRegistry: () => {}, onReprocess: () => {}, showToast: () => {} })
      )
    );
  });
  await new Promise((r) => setTimeout(r, 60));

  const buttons = Array.from(container.querySelectorAll('button'));
  const btnMap = {};
  buttons.forEach((btn) => {
    const text = btn.textContent.trim().replace(/\s+/g, ' ');
    btnMap[text] = {
      disabled: btn.disabled,
      title: btn.getAttribute('title') || '',
    };
  });

  console.log(`[Workspace] Button States:`);
  for (const [name, state] of Object.entries(btnMap)) {
    if (['Sign & Verify Record', 'Verified & Sealed', 'Reprocess', 'Correct', 'Push to State LRMS', 'Push to State GIS Portal'].some((k) => name.includes(k))) {
      console.log(`  - "${name}": disabled=${state.disabled}${state.title ? ` (title: "${state.title}")` : ''}`);
    }
  }

  await act(async () => {
    root.unmount();
  });
}

async function run() {
  await testRole('field_officer');
  await testRole('verifier');
  await testRole('admin');
  process.exit(0);
}

run().catch((err) => {
  console.error('Test error:', err);
  process.exit(1);
});
