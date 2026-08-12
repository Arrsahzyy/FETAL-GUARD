/**
 * I18nContext — Reactive i18n Provider
 * ======================================
 * Membungkus modul i18n statis ke dalam React Context
 * agar perubahan bahasa langsung memicu re-render seluruh tree.
 *
 * CARA PAKAI:
 *   import { useI18n } from '../../../i18n/I18nContext';
 *   const { locale, changeLocale } = useI18n();
 *   changeLocale('en'); // seluruh app langsung update
 */

import React, { useEffect, useState } from 'react';
import { setLocale as setI18nLocale, getLocale } from './index.js';
import I18nContext from './i18nContext.js';

export const I18nProvider = ({ children }) => {
    const [locale, setLocaleState] = useState(getLocale);

    useEffect(() => {
        document.documentElement.lang = locale === 'en' ? 'en' : 'id';
    }, [locale]);

    const changeLocale = (newLocale) => {
        setI18nLocale(newLocale);
        setLocaleState(newLocale);
    };

    return (
        <I18nContext.Provider value={{ locale, changeLocale }}>
            {children}
        </I18nContext.Provider>
    );
};

/**
 * useI18n — hook untuk mengakses locale aktif + fungsi ganti bahasa.
 * Aman digunakan di luar Provider (fallback ke module-level locale).
 */
