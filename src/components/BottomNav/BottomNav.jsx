import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { t } from '../../i18n';
import { useI18n } from '../../i18n/useI18n';
import Icon from '../Icon/Icon';
import './BottomNav.css';

/**
 * BottomNav — Navigasi bawah untuk domain Pasien (Mobile).
 *
 * Sebelumnya: Menggunakan `onTabChange` callback + `activeTab` prop.
 * Sekarang: Menggunakan React Router `useNavigate` + `useLocation`.
 *
 * Props:
 * - notificationCount: jumlah notifikasi unread (badge)
 * - activeTab (opsional fallback, deprecated — prioritas ke URL)
 * - onNavigate (opsional fallback untuk non-router usage)
 */
const BottomNav = ({ notificationCount = 0 }) => {
    const navigate = useNavigate();
    const location = useLocation();
    useI18n();

    const tabs = [
        { id: 'home', labelKey: 'patient.nav.home', icon: 'home' },
        { id: 'monitoring', labelKey: 'patient.nav.monitoring', icon: 'monitor_heart' },
        { id: 'history', labelKey: 'patient.nav.history', icon: 'history' },
        { id: 'notifications', labelKey: 'patient.nav.notifications', icon: 'notifications', badge: notificationCount },
        { id: 'education', labelKey: 'patient.nav.education', icon: 'menu_book' },
        { id: 'settings', labelKey: 'patient.nav.settings', icon: 'settings' },
    ];

    // Derive active tab from URL pathname (primary), fallback ke prop
    const pathSegment = location.pathname.split('/').filter(Boolean)[1] || 'home';
    const currentActiveTab = pathSegment === 'profile' ? 'settings' : pathSegment;

    const handleTabClick = (tabId) => {
        const targetPath = `/patient/${tabId}`;

        // Prevent re-navigating to the same path
        if (location.pathname === targetPath) return;

        navigate(targetPath);
    };

    return (
        <nav className="bottom-nav" aria-label={t('patient.nav.label')}>
            {tabs.map((tab) => {
                const isActive = currentActiveTab === tab.id;
                const badgeCount = Number.isFinite(tab.badge) ? tab.badge : 0;
                const badgeLabel = badgeCount > 99 ? '99+' : `${badgeCount}`;
                const label = t(tab.labelKey);

                return (
                    <button
                        key={tab.id}
                        type="button"
                        className={`bottom-nav__item ${isActive ? 'bottom-nav__item--active' : ''}`}
                        onClick={() => handleTabClick(tab.id)}
                        aria-label={label}
                        aria-current={isActive ? 'page' : undefined}
                    >
                        <span className="bottom-nav__icon" aria-hidden="true">
                            <Icon className="material-symbols-outlined" name={tab.icon} />
                            {badgeCount > 0 && (
                                <span className="bottom-nav__badge">
                                    {badgeLabel}
                                </span>
                            )}
                        </span>
                        <span className="bottom-nav__label">
                            {label}
                        </span>
                    </button>
                );
            })}
        </nav>
    );
};

export default BottomNav;
