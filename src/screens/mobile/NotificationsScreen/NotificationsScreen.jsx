import React, { useState } from 'react';
import { t } from '../../../i18n';
import { AlertCard } from '../../../components';
import './NotificationsScreen.css';

const NotificationsScreen = ({ onBack }) => {
    const [filter, setFilter] = useState('all');

    const notifications = [
        {
            id: 'n1',
            type: 'critical',
            title: 'Deselerasi Lambat Terdeteksi',
            message: 'Terdeteksi 3 episode deselerasi lambat dalam 30 menit terakhir dengan durasi >90 detik.',
            timestamp: '10 menit lalu',
            recommendation: 'Segera hubungi bidan/dokter atau pergi ke fasilitas kesehatan terdekat.',
            acknowledged: false,
            sessionId: 'ses-005'
        },
        {
            id: 'n2',
            type: 'warning',
            title: 'Variabilitas FHR Menurun',
            message: 'Variabilitas detak jantung janin berada di rentang minimal (5.2 bpm) selama 15 menit.',
            timestamp: '25 menit lalu',
            recommendation: 'Coba ubah posisi ke miring kiri dan pantau selama 10 menit.',
            acknowledged: true,
            sessionId: 'ses-002'
        },
        {
            id: 'n3',
            type: 'info',
            title: 'Sesi Monitoring Selesai',
            message: 'Sesi monitoring selama 45 menit telah selesai dengan hasil baik.',
            timestamp: '2 jam lalu',
            acknowledged: true,
            sessionId: 'ses-001'
        },
        {
            id: 'n4',
            type: 'info',
            title: 'Data Berhasil Dikirim ke Klinik',
            message: 'Data sesi monitoring Anda telah berhasil dibagikan ke RS Bunda Jakarta.',
            timestamp: '3 jam lalu',
            acknowledged: true
        },
        {
            id: 'n5',
            type: 'warning',
            title: 'Baterai Perangkat Rendah',
            message: 'Baterai perangkat FETAL-GUARD tersisa 15%. Segera isi ulang untuk menjaga pemantauan.',
            timestamp: '5 jam lalu',
            recommendation: 'Hubungkan perangkat ke charger.',
            acknowledged: true
        },
        {
            id: 'n6',
            type: 'info',
            title: 'Pengingat Monitoring Harian',
            message: 'Waktunya melakukan monitoring harian. Disarankan 2x sehari selama 30 menit.',
            timestamp: 'Kemarin, 09:00',
            acknowledged: true
        },
        {
            id: 'n7',
            type: 'info',
            title: 'Kunjungan Dokter Mendatang',
            message: 'Jadwal kontrol dengan Dr. Rina Susanti pada tanggal 15 Februari 2024.',
            timestamp: '2 hari lalu',
            acknowledged: true
        }
    ];

    const [acknowledgedIds, setAcknowledgedIds] = useState(
        notifications.filter(n => n.acknowledged).map(n => n.id)
    );

    const handleAcknowledge = (id) => {
        setAcknowledgedIds(prev => [...prev, id]);
    };

    const getFilteredNotifications = () => {
        if (filter === 'all') return notifications;
        if (filter === 'unread') return notifications.filter(n => !acknowledgedIds.includes(n.id));
        return notifications.filter(n => n.type === filter);
    };

    const unreadCount = notifications.filter(n => !acknowledgedIds.includes(n.id)).length;

    return (
        <div className="notifications-screen">
            {/* Header */}
            <header className="notifications-header">
                <button className="notifications-header__back" onClick={onBack}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M19 12H5M12 19l-7-7 7-7" />
                    </svg>
                </button>
                <h1>{t('notifications.title')}</h1>
                {unreadCount > 0 && (
                    <span className="notifications-header__badge">{unreadCount}</span>
                )}
                <button className="notifications-header__clear">
                    Tandai Dibaca
                </button>
            </header>

            {/* Filters */}
            <div className="notifications-filters">
                {[
                    { key: 'all', label: 'Semua' },
                    { key: 'unread', label: `Belum Dibaca (${unreadCount})` },
                    { key: 'critical', label: 'Kritis' },
                    { key: 'warning', label: 'Peringatan' }
                ].map(f => (
                    <button
                        key={f.key}
                        className={`notifications-filter ${filter === f.key ? 'active' : ''}`}
                        onClick={() => setFilter(f.key)}
                    >
                        {f.label}
                    </button>
                ))}
            </div>

            {/* Notification List */}
            <div className="notifications-list">
                {getFilteredNotifications().length === 0 ? (
                    <div className="notifications-empty">
                        <div className="notifications-empty__icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                            </svg>
                        </div>
                        <p>Tidak ada notifikasi</p>
                    </div>
                ) : (
                    getFilteredNotifications().map(notification => (
                        <AlertCard
                            key={notification.id}
                            type={notification.type}
                            title={notification.title}
                            message={notification.message}
                            timestamp={notification.timestamp}
                            recommendation={notification.recommendation}
                            acknowledged={acknowledgedIds.includes(notification.id)}
                            onAcknowledge={() => handleAcknowledge(notification.id)}
                            onAction={notification.sessionId ? () => console.log('View session', notification.sessionId) : undefined}
                            actionLabel={notification.sessionId ? 'Lihat Sesi' : undefined}
                        />
                    ))
                )}
            </div>

            {/* Bottom Info */}
            <div className="notifications-info">
                <p>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 16v-4M12 8h.01" />
                    </svg>
                    Notifikasi kritis akan selalu menampilkan peringatan dengan suara
                </p>
            </div>
        </div>
    );
};

export default NotificationsScreen;
