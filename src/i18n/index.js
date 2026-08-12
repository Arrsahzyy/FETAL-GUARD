import idTranslations from './id.json';
import enTranslations from './en.json';

const translations = {
  id: idTranslations,
  en: enTranslations
};

const LOCALE_STORAGE_KEY = 'fetalguard.locale';

const getStoredLocale = () => {
  if (typeof window === 'undefined') return 'id';

  const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return translations[storedLocale] ? storedLocale : 'id';
};

let currentLocale = getStoredLocale(); // Default to Indonesian

export const setLocale = (locale) => {
  if (translations[locale]) {
    currentLocale = locale;
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    }
  }
};

export const getLocale = () => currentLocale;

export const t = (key, params = {}) => {
  const keys = key.split('.');
  let value = translations[currentLocale];
  
  for (const k of keys) {
    if (value && typeof value === 'object' && k in value) {
      value = value[k];
    } else {
      console.warn(`Translation key not found: ${key}`);
      return key;
    }
  }
  
  if (typeof value === 'string') {
    // Replace parameters like {name} with actual values
    return value.replace(/\{(\w+)\}/g, (match, param) => {
      return params[param] !== undefined ? params[param] : match;
    });
  }
  
  return value;
};

export default { t, setLocale, getLocale };
