import React from 'react';
import { Outlet } from 'react-router-dom';

/**
 * ClinicianLayout — Wrapper layout untuk semua halaman domain Nakes (Web Dashboard).
 *
 * Tidak menggunakan BottomNav karena dashboard nakes adalah web app,
 * bukan mobile-first UI.
 */
const ClinicianLayout = () => {
    return (
        <div className="app font-display clinician-layout">
            <Outlet />
        </div>
    );
};

export default ClinicianLayout;
