import React from 'react';

const BottomNav = ({ activeTab = 'home', onTabChange, notificationCount = 0 }) => {
    const tabs = [
        { id: 'home', label: 'Home', icon: 'home' },
        { id: 'monitoring', label: 'Monitoring', icon: 'monitor_heart' },
        { id: 'history', label: 'History', icon: 'history' },
        { id: 'notifications', label: 'Alerts', icon: 'notifications', badge: notificationCount },
        { id: 'settings', label: 'Settings', icon: 'settings' },
    ];

    return (
        <nav className="fixed bottom-0 left-0 right-0 bg-white/95 dark:bg-background-dark/95 backdrop-blur-lg border-t border-slate-200 dark:border-slate-800 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-2 z-50">
            <div className="flex justify-around items-center px-4 max-w-lg mx-auto">
                {tabs.map((tab) => {
                    const isActive = activeTab === tab.id;
                    const badgeCount = Number.isFinite(tab.badge) ? tab.badge : 0;
                    const badgeLabel = badgeCount > 99 ? '99+' : `${badgeCount}`;
                    return (
                        <button
                            key={tab.id}
                            type="button"
                            className={`flex flex-col items-center gap-1 relative transition-colors ${
                                isActive
                                    ? 'text-primary'
                                    : 'text-slate-400 dark:text-slate-500'
                            }`}
                            onClick={() => onTabChange?.(tab.id)}
                            aria-current={isActive ? 'page' : undefined}
                        >
                            <span className={`material-symbols-outlined ${isActive ? 'fill-1' : ''}`} style={isActive ? { fontVariationSettings: "'FILL' 1" } : {}}>
                                {tab.icon}
                            </span>
                            {badgeCount > 0 && (
                                <span className="absolute -top-1 -right-1 size-4 bg-critical text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                                    {badgeLabel}
                                </span>
                            )}
                            <span className={`text-[10px] ${isActive ? 'font-bold' : 'font-medium'}`}>
                                {tab.label}
                            </span>
                        </button>
                    );
                })}
            </div>
        </nav>
    );
};

export default BottomNav;
