import idTranslations from './id.json';
import enTranslations from './en.json';

const translations = {
  id: idTranslations,
  en: enTranslations
};

let currentLocale = 'id'; // Default to Indonesian

export const setLocale = (locale) => {
  if (translations[locale]) {
    currentLocale = locale;
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
