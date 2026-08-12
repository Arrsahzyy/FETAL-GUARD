import React, { useEffect, useState } from 'react';
import ThemeContext from './themeContext';

export function ThemeProvider({ children }) {
    // Default false (light)
    const [isDarkMode, setIsDarkMode] = useState(() => {
        const saved = localStorage.getItem('fetal_guard_theme');
        return saved === 'dark';
    });

    useEffect(() => {
        const root = document.documentElement;
        if (isDarkMode) {
            root.classList.add('dark');
            root.setAttribute('data-theme', 'dark');
            localStorage.setItem('fetal_guard_theme', 'dark');
        } else {
            root.classList.remove('dark');
            root.removeAttribute('data-theme');
            localStorage.setItem('fetal_guard_theme', 'light');
        }
    }, [isDarkMode]);

    const toggleTheme = () => {
        setIsDarkMode(prev => !prev);
    };

    return (
        <ThemeContext.Provider value={{ isDarkMode, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}
