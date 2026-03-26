import React, { useState } from 'react';
import { t, setLocale, getLocale } from '../../../i18n';
import connectionManager, { CONNECTION_MODES, CONNECTION_STATUS } from '../../../services/ConnectionManager';
import './SettingsScreen.css';

const SettingsScreen = ({ onBack, onLogout }) => {
    const [settings, setSettings] = useState({
        language: getLocale(),
        pushNotifications: true,
        criticalAlerts: true,
        soundAlerts: true,
        hapticFeedback: true,
        lowBatteryThreshold: 20,
        uploadWifiOnly: true,
        shareLocation: false,
        autoEscalation: true,
        darkMode: false,
        onDeviceInference: true,
        cloudInference: false
    });

    // State untuk mode koneksi IoT (Bluetooth/MQTT/WiFi)
    const [connectionMode, setConnectionMode] = useState(CONNECTION_MODES.MQTT);
    const [connectionStatus, setConnectionStatus] = useState(CONNECTION_STATUS.DISCONNECTED);
    const [mqttBrokerUrl, setMqttBrokerUrl] = useState('wss://broker.hivemq.com:8884/mqtt');
    const [mqttTopic, setMqttTopic] = useState('fetalguard/sensor/data');

    const handleConnectionModeChange = async (mode) => {
        setConnectionMode(mode);
        await connectionManager.setMode(mode);
        if (mode === CONNECTION_MODES.MQTT) {
            connectionManager.updateConfig('mqtt', { brokerUrl: mqttBrokerUrl, topic: mqttTopic });
        }
    };

    const handleTestConnection = async () => {
        try {
            setConnectionStatus(CONNECTION_STATUS.CONNECTING);
            if (connectionMode === CONNECTION_MODES.MQTT) {
                connectionManager.updateConfig('mqtt', { brokerUrl: mqttBrokerUrl, topic: mqttTopic });
            }
            await connectionManager.connect();
            setConnectionStatus(CONNECTION_STATUS.CONNECTED);
            // Auto disconnect after 3 seconds (just testing)
            setTimeout(async () => {
                await connectionManager.disconnect();
                setConnectionStatus(CONNECTION_STATUS.DISCONNECTED);
            }, 3000);
        } catch (err) {
            setConnectionStatus(CONNECTION_STATUS.ERROR);
            console.error('Connection test failed:', err);
        }
    };

    const [deviceInfo] = useState({
        serial: 'FG-2024-001234',
        model: 'FETAL-GUARD-V2',
        firmware: '2.1.3',
        battery: 85,
        lastSync: '5 menit lalu'
    });

    const [userInfo] = useState({
        name: 'Sarah Wijaya',
        patientId: 'PAT-2024-001',
        clinic: 'RS Bunda Jakarta',
        clinician: 'Dr. Rina Susanti, SpOG'
    });

    const handleToggle = (key) => {
        setSettings(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const handleLanguageChange = (lang) => {
        setSettings(prev => ({ ...prev, language: lang }));
        setLocale(lang);
    };

    return (
        <div className="settings-screen">
            {/* Header */}
            <header className="settings-header">
                <button className="settings-header__back" onClick={onBack}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M19 12H5M12 19l-7-7 7-7" />
                    </svg>
                </button>
                <h1>{t('settings.title')}</h1>
            </header>

            <div className="settings-content">
                {/* Profile Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">{t('settings.profile')}</h2>
                    <div className="settings-profile">
                        <div className="settings-profile__avatar">
                            {userInfo.name.charAt(0)}
                        </div>
                        <div className="settings-profile__info">
                            <h3>{userInfo.name}</h3>
                            <p>{userInfo.patientId}</p>
                        </div>
                        <button className="settings-profile__edit">Edit</button>
                    </div>
                    <div className="settings-item settings-item--info">
                        <span className="settings-item__label">Klinik</span>
                        <span className="settings-item__value">{userInfo.clinic}</span>
                    </div>
                    <div className="settings-item settings-item--info">
                        <span className="settings-item__label">Dokter</span>
                        <span className="settings-item__value">{userInfo.clinician}</span>
                    </div>
                </section>

                {/* Device Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">{t('settings.device.title')}</h2>
                    <div className="settings-device">
                        <div className="settings-device__icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
                                <line x1="12" y1="18" x2="12" y2="18" />
                            </svg>
                        </div>
                        <div className="settings-device__info">
                            <h4>{deviceInfo.model}</h4>
                            <p>SN: {deviceInfo.serial}</p>
                        </div>
                        <div className="settings-device__status">
                            <div className="settings-device__battery">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <rect x="1" y="6" width="18" height="12" rx="2" ry="2" />
                                    <line x1="23" y1="13" x2="23" y2="11" />
                                </svg>
                                <span>{deviceInfo.battery}%</span>
                            </div>
                        </div>
                    </div>
                    <div className="settings-item settings-item--info">
                        <span className="settings-item__label">{t('settings.device.firmware')}</span>
                        <span className="settings-item__value">v{deviceInfo.firmware}</span>
                    </div>
                    <div className="settings-item settings-item--info">
                        <span className="settings-item__label">{t('settings.device.lastSync')}</span>
                        <span className="settings-item__value">{deviceInfo.lastSync}</span>
                    </div>
                    <button className="settings-btn settings-btn--outline">
                        {t('settings.device.unpair')}
                    </button>
                </section>

                {/* IoT Connection Mode Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20" style={{display:'inline', verticalAlign:'text-bottom', marginRight:'6px'}}>
                            <path d="M5 12.55a11 11 0 0 1 14.08 0" />
                            <path d="M1.42 9a16 16 0 0 1 21.16 0" />
                            <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                            <line x1="12" y1="20" x2="12.01" y2="20" />
                        </svg>
                        Koneksi Perangkat IoT
                    </h2>
                    <p className="settings-section__desc">Pilih cara perangkat sensor terhubung ke aplikasi</p>

                    {/* Mode Bluetooth */}
                    <div
                        className={`settings-connection-card ${connectionMode === CONNECTION_MODES.BLUETOOTH ? 'active' : ''}`}
                        onClick={() => handleConnectionModeChange(CONNECTION_MODES.BLUETOOTH)}
                    >
                        <div className="settings-connection-card__radio">
                            <div className={`radio-dot ${connectionMode === CONNECTION_MODES.BLUETOOTH ? 'active' : ''}`} />
                        </div>
                        <div className="settings-connection-card__icon settings-connection-card__icon--ble">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <polyline points="6.5 6.5 17.5 17.5 12 23 12 1 17.5 6.5 6.5 17.5" />
                            </svg>
                        </div>
                        <div className="settings-connection-card__content">
                            <h4>Bluetooth LE</h4>
                            <p>Langsung ke HP — seperti Mi Band</p>
                        </div>
                    </div>

                    {/* Mode MQTT */}
                    <div
                        className={`settings-connection-card ${connectionMode === CONNECTION_MODES.MQTT ? 'active' : ''}`}
                        onClick={() => handleConnectionModeChange(CONNECTION_MODES.MQTT)}
                    >
                        <div className="settings-connection-card__radio">
                            <div className={`radio-dot ${connectionMode === CONNECTION_MODES.MQTT ? 'active' : ''}`} />
                        </div>
                        <div className="settings-connection-card__icon settings-connection-card__icon--mqtt">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="2" y1="12" x2="22" y2="12" />
                                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                            </svg>
                        </div>
                        <div className="settings-connection-card__content">
                            <h4>MQTT (via Internet)</h4>
                            <p>Device kirim data via WiFi ke server</p>
                        </div>
                    </div>

                    {/* Mode WiFi/HTTP */}
                    <div
                        className={`settings-connection-card ${connectionMode === CONNECTION_MODES.WIFI ? 'active' : ''}`}
                        onClick={() => handleConnectionModeChange(CONNECTION_MODES.WIFI)}
                    >
                        <div className="settings-connection-card__radio">
                            <div className={`radio-dot ${connectionMode === CONNECTION_MODES.WIFI ? 'active' : ''}`} />
                        </div>
                        <div className="settings-connection-card__icon settings-connection-card__icon--wifi">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M5 12.55a11 11 0 0 1 14.08 0" />
                                <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
                                <line x1="12" y1="20" x2="12.01" y2="20" />
                            </svg>
                        </div>
                        <div className="settings-connection-card__content">
                            <h4>WiFi / REST API</h4>
                            <p>Koneksi langsung via jaringan lokal</p>
                        </div>
                    </div>

                    {/* MQTT Config (hanya tampil saat mode MQTT) */}
                    {connectionMode === CONNECTION_MODES.MQTT && (
                        <div className="settings-mqtt-config">
                            <div className="settings-mqtt-config__field">
                                <label>MQTT Broker URL</label>
                                <input
                                    type="text"
                                    value={mqttBrokerUrl}
                                    onChange={(e) => setMqttBrokerUrl(e.target.value)}
                                    placeholder="wss://broker.hivemq.com:8884/mqtt"
                                />
                            </div>
                            <div className="settings-mqtt-config__field">
                                <label>Topic</label>
                                <input
                                    type="text"
                                    value={mqttTopic}
                                    onChange={(e) => setMqttTopic(e.target.value)}
                                    placeholder="fetalguard/sensor/data"
                                />
                            </div>
                        </div>
                    )}

                    {/* Test Connection Button */}
                    <button
                        className={`settings-btn settings-btn--test ${
                            connectionStatus === CONNECTION_STATUS.CONNECTED ? 'settings-btn--success' :
                            connectionStatus === CONNECTION_STATUS.ERROR ? 'settings-btn--error' :
                            connectionStatus === CONNECTION_STATUS.CONNECTING ? 'settings-btn--loading' : ''
                        }`}
                        onClick={handleTestConnection}
                        disabled={connectionStatus === CONNECTION_STATUS.CONNECTING}
                    >
                        {connectionStatus === CONNECTION_STATUS.CONNECTING ? (
                            <><span className="spinner" /> Menghubungkan...</>
                        ) : connectionStatus === CONNECTION_STATUS.CONNECTED ? (
                            <><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" width="16" height="16"><polyline points="20 6 9 17 4 12" /></svg> Terhubung!</>
                        ) : connectionStatus === CONNECTION_STATUS.ERROR ? (
                            'Gagal — Coba Lagi'
                        ) : (
                            'Tes Koneksi'
                        )}
                    </button>
                </section>

                {/* Notifications Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">{t('settings.notifications.title')}</h2>
                    <div className="settings-item">
                        <span className="settings-item__label">{t('settings.notifications.push')}</span>
                        <div
                            className={`toggle ${settings.pushNotifications ? 'active' : ''}`}
                            onClick={() => handleToggle('pushNotifications')}
                        />
                    </div>
                    <div className="settings-item">
                        <span className="settings-item__label">{t('settings.notifications.critical')}</span>
                        <div
                            className={`toggle ${settings.criticalAlerts ? 'active' : ''}`}
                            onClick={() => handleToggle('criticalAlerts')}
                        />
                    </div>
                    <div className="settings-item">
                        <span className="settings-item__label">{t('settings.notifications.sound')}</span>
                        <div
                            className={`toggle ${settings.soundAlerts ? 'active' : ''}`}
                            onClick={() => handleToggle('soundAlerts')}
                        />
                    </div>
                    <div className="settings-item">
                        <span className="settings-item__label">Umpan Balik Getar</span>
                        <div
                            className={`toggle ${settings.hapticFeedback ? 'active' : ''}`}
                            onClick={() => handleToggle('hapticFeedback')}
                        />
                    </div>
                    <div className="settings-item">
                        <span className="settings-item__label">{t('settings.notifications.batteryThreshold')}</span>
                        <select
                            className="settings-select"
                            value={settings.lowBatteryThreshold}
                            onChange={(e) => setSettings(prev => ({ ...prev, lowBatteryThreshold: parseInt(e.target.value) }))}
                        >
                            <option value="10">10%</option>
                            <option value="15">15%</option>
                            <option value="20">20%</option>
                            <option value="30">30%</option>
                        </select>
                    </div>
                </section>

                {/* Privacy Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">{t('settings.privacy.title')}</h2>
                    <div className="settings-item">
                        <div className="settings-item__content">
                            <span className="settings-item__label">{t('settings.privacy.wifiOnly')}</span>
                            <span className="settings-item__desc">Hanya unggah data saat tersambung WiFi</span>
                        </div>
                        <div
                            className={`toggle ${settings.uploadWifiOnly ? 'active' : ''}`}
                            onClick={() => handleToggle('uploadWifiOnly')}
                        />
                    </div>
                    <div className="settings-item">
                        <div className="settings-item__content">
                            <span className="settings-item__label">{t('settings.privacy.locationShare')}</span>
                            <span className="settings-item__desc">Izinkan berbagi lokasi saat darurat</span>
                        </div>
                        <div
                            className={`toggle ${settings.shareLocation ? 'active' : ''}`}
                            onClick={() => handleToggle('shareLocation')}
                        />
                    </div>
                    <div className="settings-item">
                        <div className="settings-item__content">
                            <span className="settings-item__label">{t('settings.privacy.autoEscalation')}</span>
                            <span className="settings-item__desc">Eskalasi otomatis ke kontak darurat</span>
                        </div>
                        <div
                            className={`toggle ${settings.autoEscalation ? 'active' : ''}`}
                            onClick={() => handleToggle('autoEscalation')}
                        />
                    </div>
                    <button className="settings-btn settings-btn--link">
                        {t('settings.privacy.dataRetention')}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                    <button className="settings-btn settings-btn--link settings-btn--danger">
                        {t('settings.privacy.deleteData')}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                </section>

                {/* Language Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">{t('settings.language')}</h2>
                    <div className="settings-language">
                        <button
                            className={`settings-language__btn ${settings.language === 'id' ? 'active' : ''}`}
                            onClick={() => handleLanguageChange('id')}
                        >
                            🇮🇩 Bahasa Indonesia
                        </button>
                        <button
                            className={`settings-language__btn ${settings.language === 'en' ? 'active' : ''}`}
                            onClick={() => handleLanguageChange('en')}
                        >
                            🇺🇸 English
                        </button>
                    </div>
                </section>

                {/* Advanced Section */}
                <section className="settings-section">
                    <h2 className="settings-section__title">Lanjutan</h2>
                    <div className="settings-item">
                        <div className="settings-item__content">
                            <span className="settings-item__label">Mode Gelap</span>
                        </div>
                        <div
                            className={`toggle ${settings.darkMode ? 'active' : ''}`}
                            onClick={() => handleToggle('darkMode')}
                        />
                    </div>
                    <div className="settings-item">
                        <div className="settings-item__content">
                            <span className="settings-item__label">Inferensi On-Device</span>
                            <span className="settings-item__desc">Proses AI di perangkat (lebih privat)</span>
                        </div>
                        <div
                            className={`toggle ${settings.onDeviceInference ? 'active' : ''}`}
                            onClick={() => handleToggle('onDeviceInference')}
                        />
                    </div>
                </section>

                {/* About & Support */}
                <section className="settings-section">
                    <h2 className="settings-section__title">{t('settings.about')}</h2>
                    <button className="settings-btn settings-btn--link">
                        Panduan Pengguna
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                    <button className="settings-btn settings-btn--link">
                        FAQ
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                    <button className="settings-btn settings-btn--link">
                        Hubungi Dukungan
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                    <button className="settings-btn settings-btn--link">
                        Kebijakan Privasi
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                    <button className="settings-btn settings-btn--link">
                        Syarat & Ketentuan
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <path d="M9 18l6-6-6-6" />
                        </svg>
                    </button>
                </section>

                {/* Version */}
                <div className="settings-version">
                    <p>FETAL-GUARD v1.0.0</p>
                    <p>© 2024 FETAL-GUARD Team</p>
                </div>

                {/* Logout */}
                <button className="settings-logout" onClick={onLogout}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                        <polyline points="16 17 21 12 16 7" />
                        <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
                    {t('settings.logout')}
                </button>
            </div>
        </div>
    );
};

export default SettingsScreen;
