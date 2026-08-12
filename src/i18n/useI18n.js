import { useContext } from 'react';
import { setLocale as setI18nLocale, getLocale } from './index.js';
import I18nContext from './i18nContext.js';

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return { locale: getLocale(), changeLocale: setI18nLocale };
  }
  return ctx;
}
