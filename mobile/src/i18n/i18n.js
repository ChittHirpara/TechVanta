import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as SecureStore from 'expo-secure-store';
import { LANGUAGES, getLanguageByCode } from './languages';
import { translations, getTranslation } from './translations';

const I18nContext = createContext({
  language: 'en',
  currentLangObj: LANGUAGES[0],
  setLanguage: () => {},
  t: (key) => key,
  languages: LANGUAGES,
});

const LANGUAGE_KEY = 'bhoomi_officer_language';

export function I18nProvider({ children }) {
  const [language, setLangState] = useState('en');

  useEffect(() => {
    async function loadLanguage() {
      try {
        const saved = await SecureStore.getItemAsync(LANGUAGE_KEY);
        if (saved && (LANGUAGES.some((l) => l.code === saved) || translations[saved])) {
          setLangState(saved);
        }
      } catch (e) {
        // secure store unavailable
      }
    }
    loadLanguage();
  }, []);

  const setLanguage = useCallback(async (newLang) => {
    setLangState(newLang);
    try {
      await SecureStore.setItemAsync(LANGUAGE_KEY, newLang);
    } catch (e) {}
  }, []);

  const t = useCallback(
    (key) => {
      return getTranslation(language, key);
    },
    [language]
  );

  const currentLangObj = getLanguageByCode(language);

  return (
    <I18nContext.Provider
      value={{
        language,
        currentLangObj,
        setLanguage,
        t,
        languages: LANGUAGES,
      }}
    >
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
}

export default I18nContext;
