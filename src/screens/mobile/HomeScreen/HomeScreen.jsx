import React from 'react';
import { t } from '../../../i18n';

const HomeScreen = ({ onNavigate, onStartMonitoring, onStopMonitoring, isMonitoring, patientData, deviceStatus, onOpenProfile }) => {
    const patient = patientData || {
        name: 'Ibu Sarah',
        fullName: 'Siti Aminah',
        gestationalWeeks: 28,
        gestationalDays: 3,
        pregnancyWeek: 28
    };

    const patientName = patient.fullName || patient.name || 'Pengguna';

    const device = deviceStatus || {
        connected: true,
        signalQuality: 92,
        signalStatus: 'success',
        battery: 85,
        lastSync: new Date().toISOString(),
        fhr: 142
    };

    const getFetalStatus = () => {
        const fhr = device.fhr;
        if (fhr >= 110 && fhr <= 160) {
            return { status: 'normal', label: 'Normal Status', color: 'green' };
        } else if ((fhr >= 100 && fhr < 110) || (fhr > 160 && fhr <= 180)) {
            return { status: 'watch', label: 'Perlu Dipantau', color: 'yellow' };
        }
        return { status: 'alert', label: 'Perlu Perhatian', color: 'red' };
    };

    const fetalStatus = getFetalStatus();

    const getStatusColorClasses = () => {
        switch (fetalStatus.color) {
            case 'green':
                return {
                    bg: 'bg-green-100 dark:bg-green-900/30',
                    text: 'text-green-600 dark:text-green-400',
                    border: 'border-green-200 dark:border-green-800',
                    dot: 'bg-green-500'
                };
            case 'yellow':
                return {
                    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
                    text: 'text-yellow-600 dark:text-yellow-400',
                    border: 'border-yellow-200 dark:border-yellow-800',
                    dot: 'bg-yellow-500'
                };
            case 'red':
                return {
                    bg: 'bg-red-100 dark:bg-red-900/30',
                    text: 'text-red-600 dark:text-red-400',
                    border: 'border-red-200 dark:border-red-800',
                    dot: 'bg-red-500'
                };
            default:
                return {
                    bg: 'bg-green-100',
                    text: 'text-green-600',
                    border: 'border-green-200',
                    dot: 'bg-green-500'
                };
        }
    };

    const statusClasses = getStatusColorClasses();

    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 11) return 'Selamat pagi';
        if (hour < 15) return 'Selamat siang';
        if (hour < 18) return 'Selamat sore';
        return 'Selamat malam';
    };

    // Mock recent history
    const recentSessions = [
        { id: 1, label: 'Pagi Hari', time: 'Kemarin, 08:30', fhr: 138 },
        { id: 2, label: 'Sore Hari', time: 'Kemarin, 16:00', fhr: 141 },
        { id: 3, label: 'Pagi Hari', time: '2 hari lalu, 09:00', fhr: 136 },
    ];

    return (
        <div className="bg-background-light dark:bg-background-dark font-display text-slate-900 dark:text-slate-100 min-h-screen flex flex-col">
            {/* Top Bar */}
            <header className="flex items-center justify-between p-4 sticky top-0 bg-background-light/80 dark:bg-background-dark/80 backdrop-blur-md z-10">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onOpenProfile}
                        className="size-10 rounded-full bg-primary/20 flex items-center justify-center overflow-hidden border-2 border-primary/30"
                    >
                        <span className="text-primary font-bold text-lg">{patientName.charAt(0)}</span>
                    </button>
                    <div>
                        <h1 className="text-sm font-medium text-slate-500 dark:text-slate-400">{getGreeting()},</h1>
                        <p className="text-lg font-bold leading-tight">{patientName}</p>
                    </div>
                </div>
                <button
                    className="size-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-600 dark:text-slate-300"
                    onClick={() => onNavigate?.('notifications')}
                >
                    <span className="material-symbols-outlined">notifications</span>
                </button>
            </header>

            <main className="flex-1 px-4 pb-24 overflow-y-auto">
                {/* Patient Info Card */}
                <div className="mt-4 p-5 rounded-xl bg-white dark:bg-slate-900 shadow-sm border border-slate-100 dark:border-slate-800 flex items-center justify-between">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-primary">Usia Kandungan</p>
                        <p className="text-xl font-bold mt-1 text-slate-800 dark:text-slate-100">
                            {patient.pregnancyWeek || patient.gestationalWeeks} Minggu {patient.gestationalDays || 0} Hari
                        </p>
                    </div>
                    <div className="size-12 rounded-full bg-primary/10 flex items-center justify-center">
                        <span className="material-symbols-outlined text-primary text-3xl">child_care</span>
                    </div>
                </div>

                {/* FHR Main Display */}
                <div className="mt-6 flex flex-col items-center">
                    <div className="relative flex items-center justify-center">
                        {/* Circular pulse effect */}
                        <div className="absolute w-48 h-48 rounded-full bg-primary/10 animate-pulse"></div>
                        <div className="absolute w-60 h-60 rounded-full border border-primary/20 animate-pulse-ring"></div>
                        <div className="relative z-10 w-44 h-44 rounded-full bg-white dark:bg-slate-900 shadow-xl border-4 border-primary/20 flex flex-col items-center justify-center">
                            <span className="material-symbols-outlined text-primary text-3xl mb-1">favorite</span>
                            <p className="text-4xl font-black text-slate-900 dark:text-white tracking-tighter">{device.fhr}</p>
                            <p className="text-sm font-medium text-slate-500">bpm</p>
                        </div>
                    </div>
                    <div className={`mt-6 inline-flex items-center px-4 py-1.5 rounded-full ${statusClasses.bg} ${statusClasses.text} border ${statusClasses.border}`}>
                        <span className={`size-2 rounded-full ${statusClasses.dot} mr-2`}></span>
                        <span className="text-sm font-bold uppercase tracking-wide">{fetalStatus.label}</span>
                    </div>
                </div>

                {/* Monitoring Action */}
                <div className="mt-8">
                    {isMonitoring ? (
                        <button
                            className="w-full py-4 bg-slate-700 text-white rounded-xl font-bold text-lg shadow-lg active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                            onClick={() => onStopMonitoring?.()}
                        >
                            <span className="material-symbols-outlined">stop_circle</span>
                            {t('home.stopMonitoring')}
                        </button>
                    ) : (
                        <button
                            className="w-full py-4 bg-primary text-white rounded-xl font-bold text-lg shadow-lg shadow-primary/30 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                            onClick={() => onStartMonitoring?.()}
                        >
                            <span className="material-symbols-outlined">play_circle</span>
                            {t('home.startMonitoring')}
                        </button>
                    )}
                </div>

                {/* Device Status */}
                <div className="mt-8 grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="material-symbols-outlined text-primary">sensors</span>
                            <p className="text-xs font-semibold text-slate-500">Status Alat</p>
                        </div>
                        <p className="text-base font-bold text-slate-800 dark:text-slate-100">
                            {device.connected ? 'Connected' : 'Disconnected'}
                        </p>
                    </div>
                    <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="material-symbols-outlined text-primary">battery_5_bar</span>
                            <p className="text-xs font-semibold text-slate-500">Baterai</p>
                        </div>
                        <div className="flex items-center gap-2">
                            <p className="text-base font-bold text-slate-800 dark:text-slate-100">{device.battery}%</p>
                            <div className="flex-1 h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                                <div
                                    className={`h-full rounded-full ${device.battery > 20 ? 'bg-primary' : 'bg-red-500'}`}
                                    style={{ width: `${device.battery}%` }}
                                ></div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Signal Quality & Sync */}
                <div className="mt-4 grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="material-symbols-outlined text-primary">signal_cellular_alt</span>
                            <p className="text-xs font-semibold text-slate-500">{t('home.signalQuality')}</p>
                        </div>
                        <p className="text-base font-bold text-slate-800 dark:text-slate-100">{device.signalQuality}%</p>
                    </div>
                    <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="material-symbols-outlined text-primary">sync</span>
                            <p className="text-xs font-semibold text-slate-500">{t('home.lastSync')}</p>
                        </div>
                        <p className="text-base font-bold text-slate-800 dark:text-slate-100">Baru saja</p>
                    </div>
                </div>

                {/* Daily Tip */}
                <div className="mt-6 p-4 rounded-xl bg-primary/5 border border-primary/10">
                    <div className="flex items-start gap-3">
                        <span className="material-symbols-outlined text-primary mt-0.5">lightbulb</span>
                        <p className="text-sm text-slate-600 dark:text-slate-300">
                            Disarankan untuk melakukan monitoring 2x sehari selama 20-30 menit untuk hasil optimal.
                        </p>
                    </div>
                </div>

                {/* Recent Logs */}
                <div className="mt-8">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-bold text-slate-800 dark:text-slate-100">Riwayat Terakhir</h3>
                        <button
                            className="text-primary text-sm font-medium"
                            onClick={() => onNavigate?.('history')}
                        >
                            Lihat Semua
                        </button>
                    </div>
                    <div className="space-y-3">
                        {recentSessions.map((session) => (
                            <div
                                key={session.id}
                                className="flex items-center justify-between p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-50 dark:border-slate-800"
                            >
                                <div className="flex items-center gap-3">
                                    <div className="size-8 rounded bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                                        <span className="material-symbols-outlined text-slate-500 text-xl">history</span>
                                    </div>
                                    <div>
                                        <p className="text-sm font-bold">{session.label}</p>
                                        <p className="text-xs text-slate-500">{session.time}</p>
                                    </div>
                                </div>
                                <p className="text-sm font-bold text-slate-800 dark:text-slate-100">{session.fhr} bpm</p>
                            </div>
                        ))}
                    </div>
                </div>
            </main>
        </div>
    );
};

export default HomeScreen;
