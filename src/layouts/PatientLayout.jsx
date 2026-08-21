import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import BottomNav from '../components/BottomNav/BottomNav';
import EmergencyButton from '../components/EmergencyButton/EmergencyButton';
import PatientNotificationBridge from '../components/PatientNotificationBridge/PatientNotificationBridge';
import { PatientDeviceProvider } from '../context/PatientDeviceContext.jsx';
import { PatientMonitoringProvider } from '../context/PatientMonitoringContext.jsx';
import { usePatientDevice } from '../context/usePatientDevice';
import { useAuth } from '../context/useAuth';
import './PatientLayout.css';

/**
 * PatientLayout — Wrapper layout untuk semua halaman domain Pasien.
 *
 * Menyediakan:
 * - BottomNav (navigasi bawah, aktif berdasarkan URL path)
 * - EmergencyButton (tersembunyi saat monitoring)
 * - <Outlet /> untuk child routes
 */
const PatientLayoutContent = () => {
    const location = useLocation();
    const { notificationCount } = usePatientDevice();
    const { user } = useAuth();
    const trustedContactPhone = user?.patientProfile?.emergency_contact_phone || null;

    return (
        <div className="app font-display patient-shell">
            <main className="patient-shell__content">
                <Outlet />
            </main>

            <PatientNotificationBridge />

            <EmergencyButton
                compact={location.pathname !== '/patient/home'}
                trustedContactPhone={trustedContactPhone}
                patientUserId={user?.id}
            />

            {/* Bottom Navigation — driven by URL */}
            <BottomNav
                notificationCount={notificationCount}
            />
        </div>
    );
};

const PatientLayout = () => (
    <PatientDeviceProvider>
        <PatientMonitoringProvider>
            <PatientLayoutContent />
        </PatientMonitoringProvider>
    </PatientDeviceProvider>
);

export default PatientLayout;
