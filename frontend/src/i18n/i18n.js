import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import HttpBackend from 'i18next-http-backend';
import { getLanguageByCode, RTL_LANGUAGES } from './languages';

const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
const queryLang = urlParams ? (urlParams.get('lng') || urlParams.get('lang')) : null;
const savedLang = queryLang || localStorage.getItem('bhoomiscan_language') || 'en';
if (queryLang) {
  localStorage.setItem('bhoomiscan_language', queryLang);
}

const loadedFonts = new Set();

export const applyLanguageAttributes = (langCode) => {
  const langObj = getLanguageByCode(langCode);
  const isRtl = RTL_LANGUAGES.includes(langCode);

  // Set document-level language code
  document.documentElement.lang = langCode;

  // RTL applies to text nodes/containers via class while layout stays LTR
  if (isRtl) {
    document.body.classList.add('lang-rtl');
  } else {
    document.body.classList.remove('lang-rtl');
  }

  // Dynamic Font Injection (Noto Sans Ol Chiki / Meetei Mayek)
  if (langObj.font && !loadedFonts.has(langCode)) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = langObj.font;
    link.id = `font-${langCode}`;
    document.head.appendChild(link);
    loadedFonts.add(langCode);
  }
};

i18n
  .use(HttpBackend)
  .use(initReactI18next)
  .init({
    lng: savedLang,
    fallbackLng: 'en',
    supportedLngs: [
      'en', 'as', 'bn', 'brx', 'doi', 'gu', 'hi', 'kn', 'ks', 'kok',
      'mai', 'ml', 'mni', 'mr', 'ne', 'or', 'pa', 'sa', 'sat', 'sd',
      'ta', 'te', 'ur'
    ],
    backend: {
      loadPath: '/locales/{{lng}}.json',
    },
    interpolation: {
      escapeValue: false, // React handles XSS
    },
    react: {
      useSuspense: false, // Avoid blank screens during initial async fetch
    },
  });

i18n.on('languageChanged', (lng) => {
  localStorage.setItem('bhoomiscan_language', lng);
  applyLanguageAttributes(lng);
});

// Apply on initial load
applyLanguageAttributes(savedLang);

export default i18n;
