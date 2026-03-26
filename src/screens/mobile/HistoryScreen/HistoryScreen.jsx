import React, { useState } from 'react';
import { t } from '../../../i18n';
import { StatusBadge } from '../../../components';
import './HistoryScreen.css';

const HistoryScreen = ({ onSelectSession, onBack }) => {
    const [filter, setFilter] = useState('all');
    const [dateRange, setDateRange] = useState('week');

    // Mock data
    const sessions = [
        {
            id: 'ses-001',
            date: '2024-02-08',
            time: '14:00',
            duration: 45,
            meanFhr: 136,
            riskLevel: 'low',
            events: { accelerations: 3, decelerations: 0, movements: 2 },
            signalQuality: 95
        },
        {
            id: 'ses-002',
            date: '2024-02-08',
            time: '09:00',
            duration: 50,
            meanFhr: 148,
            riskLevel: 'medium',
            events: { accelerations: 2, decelerations: 2, movements: 1 },
            signalQuality: 85
        },
        {
            id: 'ses-003',
            date: '2024-02-07',
            time: '15:00',
            duration: 40,
            meanFhr: 137,
            riskLevel: 'low',
            events: { accelerations: 3, decelerations: 0, movements: 2 },
            signalQuality: 96
        },
        {
            id: 'ses-004',
            date: '2024-02-07',
            time: '09:30',
            duration: 35,
            meanFhr: 142,
            riskLevel: 'low',
            events: { accelerations: 2, decelerations: 0, movements: 3 },
            signalQuality: 94
        },
        {
            id: 'ses-005',
            date: '2024-02-06',
            time: '16:00',
            duration: 60,
            meanFhr: 165,
            riskLevel: 'high',
            events: { accelerations: 1, decelerations: 4, movements: 0 },
            signalQuality: 88
        },
        {
            id: 'ses-006',
            date: '2024-02-05',
            time: '10:00',
            duration: 45,
            meanFhr: 140,
            riskLevel: 'low',
            events: { accelerations: 4, decelerations: 0, movements: 3 },
            signalQuality: 97
        }
    ];

    const stats = {
        totalSessions: 24,
        totalHours: 18.5,
        avgFhr: 142,
        normalSessions: 20,
        watchSessions: 3,
        alarmSessions: 1
    };

    const getFilteredSessions = () => {
        if (filter === 'all') return sessions;
        return sessions.filter(s => s.riskLevel === filter);
    };

    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (date.toDateString() === today.toDateString()) {
            return 'Hari Ini';
        } else if (date.toDateString() === yesterday.toDateString()) {
            return 'Kemarin';
        }
        return date.toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'short' });
    };

    const groupSessionsByDate = () => {
        const grouped = {};
        getFilteredSessions().forEach(session => {
            const dateLabel = formatDate(session.date);
            if (!grouped[dateLabel]) {
                grouped[dateLabel] = [];
            }
            grouped[dateLabel].push(session);
        });
        return grouped;
    };

    const getRiskBadgeStatus = (level) => {
        switch (level) {
            case 'low': return 'success';
            case 'medium': return 'warning';
            case 'high': return 'critical';
            default: return 'info';
        }
    };

    const getRiskLabel = (level) => {
        switch (level) {
            case 'low': return 'Normal';
            case 'medium': return 'Watch';
            case 'high': return 'Alarm';
            default: return level;
        }
    };

    return (
        <div className="history-screen">
            {/* Header */}
            <header className="history-header">
                <button className="history-header__back" onClick={onBack}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M19 12H5M12 19l-7-7 7-7" />
                    </svg>
                </button>
                <h1>{t('history.title')}</h1>
                <button className="history-header__export">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                </button>
            </header>

            {/* Stats Summary */}
            <div className="history-stats">
                <div className="history-stats__card">
                    <span className="history-stats__value">{stats.totalSessions}</span>
                    <span className="history-stats__label">{t('history.sessions')}</span>
                </div>
                <div className="history-stats__card">
                    <span className="history-stats__value">{stats.totalHours}j</span>
                    <span className="history-stats__label">Total Waktu</span>
                </div>
                <div className="history-stats__card">
                    <span className="history-stats__value">{stats.avgFhr}</span>
                    <span className="history-stats__label">Rata-rata FHR</span>
                </div>
            </div>

            {/* Risk Distribution */}
            <div className="history-distribution">
                <div className="history-distribution__bar">
                    <div
                        className="history-distribution__segment history-distribution__segment--normal"
                        style={{ width: `${(stats.normalSessions / stats.totalSessions) * 100}%` }}
                    />
                    <div
                        className="history-distribution__segment history-distribution__segment--watch"
                        style={{ width: `${(stats.watchSessions / stats.totalSessions) * 100}%` }}
                    />
                    <div
                        className="history-distribution__segment history-distribution__segment--alarm"
                        style={{ width: `${(stats.alarmSessions / stats.totalSessions) * 100}%` }}
                    />
                </div>
                <div className="history-distribution__legend">
                    <span className="history-distribution__legend-item history-distribution__legend-item--normal">
                        Normal ({stats.normalSessions})
                    </span>
                    <span className="history-distribution__legend-item history-distribution__legend-item--watch">
                        Watch ({stats.watchSessions})
                    </span>
                    <span className="history-distribution__legend-item history-distribution__legend-item--alarm">
                        Alarm ({stats.alarmSessions})
                    </span>
                </div>
            </div>

            {/* Filters */}
            <div className="history-filters">
                <div className="history-filters__tabs">
                    {['all', 'low', 'medium', 'high'].map(f => (
                        <button
                            key={f}
                            className={`history-filters__tab ${filter === f ? 'active' : ''}`}
                            onClick={() => setFilter(f)}
                        >
                            {f === 'all' ? 'Semua' : f === 'low' ? 'Normal' : f === 'medium' ? 'Watch' : 'Alarm'}
                        </button>
                    ))}
                </div>
                <select
                    className="history-filters__date"
                    value={dateRange}
                    onChange={(e) => setDateRange(e.target.value)}
                >
                    <option value="week">{t('history.filterWeek')}</option>
                    <option value="month">{t('history.filterMonth')}</option>
                    <option value="all">{t('history.filterAll')}</option>
                </select>
            </div>

            {/* Session List */}
            <div className="history-list">
                {Object.entries(groupSessionsByDate()).map(([date, dateSessions]) => (
                    <div key={date} className="history-group">
                        <h3 className="history-group__date">{date}</h3>
                        {dateSessions.map(session => (
                            <button
                                key={session.id}
                                className="history-item"
                                onClick={() => onSelectSession?.(session.id)}
                            >
                                <div className="history-item__time">
                                    <span className="history-item__clock">{session.time}</span>
                                    <span className="history-item__duration">{session.duration} min</span>
                                </div>
                                <div className="history-item__data">
                                    <div className="history-item__fhr">
                                        <span className="history-item__fhr-value">{session.meanFhr}</span>
                                        <span className="history-item__fhr-label">bpm</span>
                                    </div>
                                    <div className="history-item__events">
                                        <span className="history-item__event history-item__event--acc">
                                            ↑{session.events.accelerations}
                                        </span>
                                        <span className="history-item__event history-item__event--dec">
                                            ↓{session.events.decelerations}
                                        </span>
                                        <span className="history-item__event history-item__event--mov">
                                            ◌{session.events.movements}
                                        </span>
                                    </div>
                                </div>
                                <StatusBadge 
                                    status={getRiskBadgeStatus(session.riskLevel)} 
                                    size="small"
                                    label={getRiskLabel(session.riskLevel)}
                                />
                                <svg className="history-item__arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M9 18l6-6-6-6" />
                                </svg>
                            </button>
                        ))}
                    </div>
                ))}
            </div>

            {/* Export Button */}
            <div className="history-export">
                <button className="btn btn-secondary history-export__btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="16" y1="13" x2="8" y2="13" />
                        <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                    {t('history.exportPDF')}
                </button>
                <button className="btn btn-secondary history-export__btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                    </svg>
                    {t('history.shareToClinic')}
                </button>
            </div>
        </div>
    );
};

export default HistoryScreen;
