import React, { useState, useMemo } from 'react';
import { t } from '../../../i18n';
import './ClinicianDashboard.css';

// Mock data imports would go here
const mockPatients = [
    {
        id: 'p001',
        name: 'Sarah Wijaya',
        gestationalAge: 32,
        lastSession: '10 menit lalu',
        currentRisk: 'low',
        lastFhr: 136,
        activeAlerts: 0,
        signalQuality: 95
    },
    {
        id: 'p002',
        name: 'Dewi Lestari',
        gestationalAge: 34,
        lastSession: '25 menit lalu',
        currentRisk: 'high',
        lastFhr: 165,
        activeAlerts: 2,
        signalQuality: 88
    },
    {
        id: 'p003',
        name: 'Putri Handayani',
        gestationalAge: 28,
        lastSession: '1 jam lalu',
        currentRisk: 'low',
        lastFhr: 144,
        activeAlerts: 0,
        signalQuality: 97
    },
    {
        id: 'p004',
        name: 'Ratna Sari',
        gestationalAge: 31,
        lastSession: '2 jam lalu',
        currentRisk: 'medium',
        lastFhr: 148,
        activeAlerts: 1,
        signalQuality: 85
    },
    {
        id: 'p005',
        name: 'Maya Anggraini',
        gestationalAge: 33,
        lastSession: '3 jam lalu',
        currentRisk: 'low',
        lastFhr: 137,
        activeAlerts: 0,
        signalQuality: 96
    },
    {
        id: 'p006',
        name: 'Lia Permata',
        gestationalAge: 37,
        lastSession: 'Aktif sekarang',
        currentRisk: 'high',
        lastFhr: 172,
        activeAlerts: 3,
        signalQuality: 92
    }
];

const mockAlerts = [
    {
        id: 'a1',
        patientId: 'p006',
        patientName: 'Lia Permata',
        type: 'critical',
        message: 'Deselerasi berkepanjangan > 2 menit terdeteksi',
        timestamp: '2 menit lalu',
        sessionId: 'ses-005',
        acknowledged: false
    },
    {
        id: 'a2',
        patientId: 'p002',
        patientName: 'Dewi Lestari',
        type: 'critical',
        message: 'Deselerasi lambat berulang (3x dalam 30 menit)',
        timestamp: '15 menit lalu',
        sessionId: 'ses-002',
        acknowledged: false
    },
    {
        id: 'a3',
        patientId: 'p002',
        patientName: 'Dewi Lestari',
        type: 'warning',
        message: 'Variabilitas FHR minimal (5.2 bpm)',
        timestamp: '20 menit lalu',
        sessionId: 'ses-002',
        acknowledged: true
    },
    {
        id: 'a4',
        patientId: 'p004',
        patientName: 'Ratna Sari',
        type: 'warning',
        message: 'Deselerasi variabel terdeteksi',
        timestamp: '2 jam lalu',
        sessionId: 'ses-004',
        acknowledged: true
    }
];

const ClinicianDashboard = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [riskFilter, setRiskFilter] = useState('all');
    const [selectedPatient, setSelectedPatient] = useState(null);
    const [activeTab, setActiveTab] = useState('patients');
    const [acknowledgedAlerts, setAcknowledgedAlerts] = useState(['a3', 'a4']);

    // Filter patients
    const filteredPatients = useMemo(() => {
        return mockPatients.filter(patient => {
            const matchesSearch = patient.name.toLowerCase().includes(searchQuery.toLowerCase());
            const matchesRisk = riskFilter === 'all' ||
                (riskFilter === 'alerts' && patient.activeAlerts > 0) ||
                patient.currentRisk === riskFilter;
            return matchesSearch && matchesRisk;
        });
    }, [searchQuery, riskFilter]);

    // Stats
    const stats = useMemo(() => ({
        total: mockPatients.length,
        monitoring: mockPatients.filter(p => p.lastSession.includes('Aktif') || p.lastSession.includes('menit')).length,
        highRisk: mockPatients.filter(p => p.currentRisk === 'high').length,
        alerts: mockAlerts.filter(a => !acknowledgedAlerts.includes(a.id)).length
    }), [acknowledgedAlerts]);

    const handleAcknowledgeAlert = (alertId) => {
        setAcknowledgedAlerts(prev => [...prev, alertId]);
    };

    const getRiskColor = (risk) => {
        switch (risk) {
            case 'low': return 'var(--color-success)';
            case 'medium': return 'var(--color-warning)';
            case 'high': return 'var(--color-critical)';
            default: return 'var(--color-text-tertiary)';
        }
    };

    const getRiskLabel = (risk) => {
        switch (risk) {
            case 'low': return 'Normal';
            case 'medium': return 'Watch';
            case 'high': return 'Alarm';
            default: return risk;
        }
    };

    return (
        <div className="clinician-dashboard">
            {/* Sidebar */}
            <aside className="dashboard-sidebar">
                <div className="dashboard-sidebar__logo">
                    <div className="logo-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                        </svg>
                    </div>
                    <span>FETAL-GUARD</span>
                </div>

                <nav className="dashboard-nav">
                    <button
                        className={`dashboard-nav__item ${activeTab === 'patients' ? 'active' : ''}`}
                        onClick={() => setActiveTab('patients')}
                    >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                            <circle cx="9" cy="7" r="4" />
                            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                        </svg>
                        {t('clinician.patientList')}
                    </button>
                    <button
                        className={`dashboard-nav__item ${activeTab === 'alerts' ? 'active' : ''}`}
                        onClick={() => setActiveTab('alerts')}
                    >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                        </svg>
                        {t('clinician.alertQueue')}
                        {stats.alerts > 0 && (
                            <span className="dashboard-nav__badge">{stats.alerts}</span>
                        )}
                    </button>
                    <button className="dashboard-nav__item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <line x1="16" y1="13" x2="8" y2="13" />
                            <line x1="16" y1="17" x2="8" y2="17" />
                        </svg>
                        Laporan
                    </button>
                    <button className="dashboard-nav__item">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="3" />
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                        </svg>
                        Pengaturan
                    </button>
                </nav>

                <div className="dashboard-sidebar__user">
                    <div className="user-avatar">RS</div>
                    <div className="user-info">
                        <span className="user-name">Dr. Rina Susanti</span>
                        <span className="user-role">SpOG</span>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="dashboard-main">
                {/* Header */}
                <header className="dashboard-header">
                    <div className="dashboard-header__title">
                        <h1>{activeTab === 'patients' ? t('clinician.patientList') : t('clinician.alertQueue')}</h1>
                        <p>{new Date().toLocaleDateString('id-ID', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
                    </div>
                    <div className="dashboard-header__actions">
                        <button className="header-btn">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10" />
                                <path d="M12 16v-4M12 8h.01" />
                            </svg>
                            Bantuan
                        </button>
                    </div>
                </header>

                {/* Stats Cards */}
                <div className="dashboard-stats">
                    <div className="stat-card">
                        <div className="stat-card__icon stat-card__icon--total">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                                <circle cx="9" cy="7" r="4" />
                            </svg>
                        </div>
                        <div className="stat-card__content">
                            <span className="stat-card__value">{stats.total}</span>
                            <span className="stat-card__label">{t('clinician.totalPatients')}</span>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card__icon stat-card__icon--monitoring">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                            </svg>
                        </div>
                        <div className="stat-card__content">
                            <span className="stat-card__value">{stats.monitoring}</span>
                            <span className="stat-card__label">{t('clinician.activeMonitoring')}</span>
                        </div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card__icon stat-card__icon--risk">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                <line x1="12" y1="9" x2="12" y2="13" />
                                <line x1="12" y1="17" x2="12.01" y2="17" />
                            </svg>
                        </div>
                        <div className="stat-card__content">
                            <span className="stat-card__value">{stats.highRisk}</span>
                            <span className="stat-card__label">{t('clinician.highRisk')}</span>
                        </div>
                    </div>
                    <div className="stat-card stat-card--alert">
                        <div className="stat-card__icon stat-card__icon--alerts">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                            </svg>
                        </div>
                        <div className="stat-card__content">
                            <span className="stat-card__value">{stats.alerts}</span>
                            <span className="stat-card__label">{t('clinician.pendingAlerts')}</span>
                        </div>
                    </div>
                </div>

                {activeTab === 'patients' && (
                    <>
                        {/* Filters */}
                        <div className="dashboard-filters">
                            <div className="search-box">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <circle cx="11" cy="11" r="8" />
                                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                                </svg>
                                <input
                                    type="text"
                                    placeholder={t('clinician.search')}
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>
                            <div className="filter-tabs">
                                {[
                                    { key: 'all', label: 'Semua' },
                                    { key: 'alerts', label: 'Ada Alert' },
                                    { key: 'high', label: 'Alarm' },
                                    { key: 'medium', label: 'Watch' },
                                    { key: 'low', label: 'Normal' }
                                ].map(f => (
                                    <button
                                        key={f.key}
                                        className={`filter-tab ${riskFilter === f.key ? 'active' : ''}`}
                                        onClick={() => setRiskFilter(f.key)}
                                    >
                                        {f.label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Patient Table */}
                        <div className="patient-table-container">
                            <table className="patient-table">
                                <thead>
                                    <tr>
                                        <th>Pasien</th>
                                        <th>Usia Gestasi</th>
                                        <th>Sesi Terakhir</th>
                                        <th>FHR Terakhir</th>
                                        <th>Kualitas Sinyal</th>
                                        <th>Status Risiko</th>
                                        <th>Aksi</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filteredPatients.map(patient => (
                                        <tr
                                            key={patient.id}
                                            className={patient.activeAlerts > 0 ? 'has-alerts' : ''}
                                            onClick={() => setSelectedPatient(patient)}
                                        >
                                            <td>
                                                <div className="patient-cell">
                                                    <div className="patient-avatar">{patient.name.charAt(0)}</div>
                                                    <div className="patient-info">
                                                        <span className="patient-name">{patient.name}</span>
                                                        {patient.activeAlerts > 0 && (
                                                            <span className="patient-alerts">{patient.activeAlerts} alert aktif</span>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>
                                            <td>{patient.gestationalAge} minggu</td>
                                            <td>
                                                <span className={patient.lastSession.includes('Aktif') ? 'text-live' : ''}>
                                                    {patient.lastSession}
                                                </span>
                                            </td>
                                            <td>
                                                <span className="fhr-value" style={{ color: getRiskColor(patient.currentRisk) }}>
                                                    {patient.lastFhr} bpm
                                                </span>
                                            </td>
                                            <td>
                                                <div className="signal-quality">
                                                    <div className="signal-bar" style={{ '--quality': `${patient.signalQuality}%` }} />
                                                    <span>{patient.signalQuality}%</span>
                                                </div>
                                            </td>
                                            <td>
                                                <span
                                                    className="risk-badge"
                                                    style={{
                                                        background: `${getRiskColor(patient.currentRisk)}20`,
                                                        color: getRiskColor(patient.currentRisk)
                                                    }}
                                                >
                                                    {getRiskLabel(patient.currentRisk)}
                                                </span>
                                            </td>
                                            <td>
                                                <button className="action-btn" onClick={(e) => { e.stopPropagation(); }}>
                                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                                        <circle cx="12" cy="12" r="3" />
                                                    </svg>
                                                    Lihat
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}

                {activeTab === 'alerts' && (
                    <div className="alert-queue">
                        <div className="alert-queue__header">
                            <h2>Alert Menunggu Tindakan</h2>
                            <span className="alert-count">{stats.alerts} alert</span>
                        </div>
                        <div className="alert-list">
                            {mockAlerts
                                .filter(a => !acknowledgedAlerts.includes(a.id))
                                .map(alert => (
                                    <div key={alert.id} className={`alert-item alert-item--${alert.type}`}>
                                        <div className="alert-item__icon">
                                            {alert.type === 'critical' ? (
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                                                    <line x1="12" y1="9" x2="12" y2="13" />
                                                    <line x1="12" y1="17" x2="12.01" y2="17" />
                                                </svg>
                                            ) : (
                                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                    <circle cx="12" cy="12" r="10" />
                                                    <path d="M12 8v4M12 16h.01" />
                                                </svg>
                                            )}
                                        </div>
                                        <div className="alert-item__content">
                                            <div className="alert-item__header">
                                                <span className="alert-patient">{alert.patientName}</span>
                                                <span className="alert-time">{alert.timestamp}</span>
                                            </div>
                                            <p className="alert-message">{alert.message}</p>
                                        </div>
                                        <div className="alert-item__actions">
                                            <button
                                                className="alert-btn alert-btn--view"
                                                onClick={() => console.log('View session', alert.sessionId)}
                                            >
                                                Lihat Sesi
                                            </button>
                                            <button
                                                className="alert-btn alert-btn--ack"
                                                onClick={() => handleAcknowledgeAlert(alert.id)}
                                            >
                                                Acknowledge
                                            </button>
                                            <button
                                                className="alert-btn alert-btn--call"
                                                onClick={() => console.log('Call patient')}
                                            >
                                                Hubungi Pasien
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            {stats.alerts === 0 && (
                                <div className="alert-empty">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                        <polyline points="22 4 12 14.01 9 11.01" />
                                    </svg>
                                    <p>Tidak ada alert yang menunggu tindakan</p>
                                </div>
                            )}
                        </div>

                        <div className="alert-queue__header" style={{ marginTop: 'var(--spacing-8)' }}>
                            <h2>Alert Sudah Ditangani</h2>
                        </div>
                        <div className="alert-list alert-list--acknowledged">
                            {mockAlerts
                                .filter(a => acknowledgedAlerts.includes(a.id))
                                .map(alert => (
                                    <div key={alert.id} className="alert-item alert-item--acknowledged">
                                        <div className="alert-item__icon">
                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                                <polyline points="22 4 12 14.01 9 11.01" />
                                            </svg>
                                        </div>
                                        <div className="alert-item__content">
                                            <div className="alert-item__header">
                                                <span className="alert-patient">{alert.patientName}</span>
                                                <span className="alert-time">{alert.timestamp}</span>
                                            </div>
                                            <p className="alert-message">{alert.message}</p>
                                        </div>
                                    </div>
                                ))}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
};

export default ClinicianDashboard;
