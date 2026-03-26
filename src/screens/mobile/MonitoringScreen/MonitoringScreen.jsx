import React, { useState, useEffect } from 'react';
import { FHRDisplay, StatusBadge, WaveformChart } from '../../../components';
import { t } from '../../../i18n';
import './MonitoringScreen.css';

const MonitoringScreen = ({ onBack, onStop, onNavigate, onStopSession, patientData }) => {
    const [sessionDuration, setSessionDuration] = useState(0);
    const [currentFHR, setCurrentFHR] = useState(138);
    const [motherHeartRate, setMotherHeartRate] = useState(82);
    const [bloodPressure, setBloodPressure] = useState({ systolic: 118, diastolic: 75 });
    const [signalQuality, setSignalQuality] = useState('good');
    const [riskScore, setRiskScore] = useState(12);
    const [counters, setCounters] = useState({
        accelerations: 3,
        decelerations: 0,
        movements: 8
    });
    
    // Pregnancy data - can be passed from patient profile
    const [pregnancyWeek, setPregnancyWeek] = useState(patientData?.pregnancyWeek || 32);

    // Simulate real-time updates
    useEffect(() => {
        const interval = setInterval(() => {
            // Update duration
            setSessionDuration(prev => prev + 1);

            // Simulate FHR changes (Fetal Heart Rate: 110-160 bpm normal)
            setCurrentFHR(prev => {
                const change = (Math.random() - 0.5) * 4;
                return Math.round(Math.max(110, Math.min(170, prev + change)));
            });
            
            // Simulate Mother's Heart Rate changes (60-100 bpm normal)
            setMotherHeartRate(prev => {
                const change = (Math.random() - 0.5) * 2;
                return Math.round(Math.max(60, Math.min(110, prev + change)));
            });
            
            // Simulate Blood Pressure changes (Normal: 90-120/60-80)
            setBloodPressure(prev => {
                const sysChange = (Math.random() - 0.5) * 2;
                const diaChange = (Math.random() - 0.5) * 1;
                return {
                    systolic: Math.round(Math.max(90, Math.min(140, prev.systolic + sysChange))),
                    diastolic: Math.round(Math.max(60, Math.min(90, prev.diastolic + diaChange)))
                };
            });

            // Randomly update counters
            if (Math.random() < 0.1) {
                setCounters(prev => ({
                    ...prev,
                    movements: prev.movements + 1
                }));
            }
            if (Math.random() < 0.05) {
                setCounters(prev => ({
                    ...prev,
                    accelerations: prev.accelerations + 1
                }));
            }
        }, 1000);

        return () => clearInterval(interval);
    }, []);

    const formatDuration = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };

    const getSignalQualityLabel = () => {
        switch (signalQuality) {
            case 'excellent': return t('monitoring.excellent');
            case 'good': return t('monitoring.good');
            case 'fair': return t('monitoring.fair');
            case 'poor': return t('monitoring.poor');
            default: return signalQuality;
        }
    };

    const getSignalStatus = () => {
        switch (signalQuality) {
            case 'excellent':
            case 'good': return 'success';
            case 'fair': return 'warning';
            case 'poor': return 'critical';
            default: return 'info';
        }
    };

    const getRiskLevel = () => {
        if (riskScore < 25) return { label: t('monitoring.lowRisk'), status: 'success' };
        if (riskScore < 60) return { label: t('monitoring.mediumRisk'), status: 'warning' };
        return { label: t('monitoring.highRisk'), status: 'critical' };
    };
    
    const getMotherHRStatus = () => {
        if (motherHeartRate >= 60 && motherHeartRate <= 100) return 'success';
        if (motherHeartRate > 100 && motherHeartRate <= 110) return 'warning';
        return 'critical';
    };
    
    const getBPStatus = () => {
        const { systolic, diastolic } = bloodPressure;
        if (systolic <= 120 && diastolic <= 80) return 'success';
        if (systolic <= 139 && diastolic <= 89) return 'warning';
        return 'critical';
    };
    
    const getFHRStatus = () => {
        if (currentFHR >= 110 && currentFHR <= 160) return 'success';
        if ((currentFHR >= 100 && currentFHR < 110) || (currentFHR > 160 && currentFHR <= 170)) return 'warning';
        return 'critical';
    };

    const handleStop = () => {
        // Support both prop naming conventions
        if (onStop) {
            onStop();
        } else if (onStopSession) {
            onStopSession();
        }
        if (onNavigate) {
            onNavigate('home');
        } else if (onBack) {
            onBack();
        }
    };

    return (
        <div className="monitoring-screen">
            {/* Header */}
            <header className="monitoring-header">
                <div className="monitoring-header__left">
                    <button className="monitoring-back-btn" onClick={handleStop}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <line x1="19" y1="12" x2="5" y2="12" />
                            <polyline points="12 19 5 12 12 5" />
                        </svg>
                    </button>
                    <h1>{t('monitoring.title')}</h1>
                </div>
                <div className="monitoring-header__duration">
                    <span className="monitoring-header__duration-label">{t('monitoring.duration')}</span>
                    <span className="monitoring-header__duration-value">{formatDuration(sessionDuration)}</span>
                </div>
            </header>

            {/* Pregnancy Info Banner */}
            <div className="monitoring-pregnancy-info">
                <div className="monitoring-pregnancy-week">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                    </svg>
                    <span>Usia Kehamilan: <strong>{pregnancyWeek} Minggu</strong></span>
                </div>
            </div>

            {/* Live Status Bar */}
            <div className="monitoring-status-bar">
                <div className="monitoring-status-item">
                    <StatusBadge
                        status={getSignalStatus()}
                        label={t('monitoring.signalQuality')}
                        value={getSignalQualityLabel()}
                        size="small"
                    />
                </div>
                <div className="monitoring-status-item">
                    <div className="monitoring-imu-status">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                            <circle cx="12" cy="12" r="10" />
                            <path d="M12 8v4l3 3" />
                        </svg>
                        <span>{t('monitoring.imuStatus')}: Normal</span>
                    </div>
                </div>
            </div>

            {/* Signal Poor Warning */}
            {signalQuality === 'poor' && (
                <div className="monitoring-warning">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    <p>{t('monitoring.signalPoorNotice')}</p>
                    <button className="monitoring-warning__btn">{t('monitoring.calibrate')}</button>
                </div>
            )}

            {/* FHR Display */}
            <div className="monitoring-fhr-container">
                <FHRDisplay
                    value={currentFHR}
                    label={t('home.fhr')}
                    size="large"
                    showAnimation={true}
                />
                <div className="monitoring-fhr-avg">
                    Rata-rata: <strong>136 bpm</strong>
                </div>
            </div>
            
            {/* Mother's Vital Signs */}
            <div className="monitoring-vitals">
                <h3 className="monitoring-vitals__title">Tanda Vital Ibu</h3>
                <div className="monitoring-vitals__grid">
                    {/* Mother's Heart Rate */}
                    <div className={`monitoring-vital-card monitoring-vital-card--${getMotherHRStatus()}`}>
                        <div className="monitoring-vital-card__icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                            </svg>
                        </div>
                        <div className="monitoring-vital-card__content">
                            <span className="monitoring-vital-card__label">Detak Jantung Ibu</span>
                            <span className="monitoring-vital-card__value">{motherHeartRate} <small>bpm</small></span>
                        </div>
                        <StatusBadge 
                            status={getMotherHRStatus()} 
                            size="small"
                            label={getMotherHRStatus() === 'success' ? 'Normal' : getMotherHRStatus() === 'warning' ? 'Tinggi' : 'Kritis'}
                        />
                    </div>
                    
                    {/* Blood Pressure */}
                    <div className={`monitoring-vital-card monitoring-vital-card--${getBPStatus()}`}>
                        <div className="monitoring-vital-card__icon">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                            </svg>
                        </div>
                        <div className="monitoring-vital-card__content">
                            <span className="monitoring-vital-card__label">Tekanan Darah</span>
                            <span className="monitoring-vital-card__value">{bloodPressure.systolic}/{bloodPressure.diastolic} <small>mmHg</small></span>
                        </div>
                        <StatusBadge 
                            status={getBPStatus()} 
                            size="small"
                            label={getBPStatus() === 'success' ? 'Normal' : getBPStatus() === 'warning' ? 'Prehipertensi' : 'Hipertensi'}
                        />
                    </div>
                    
                    {/* Fetal Heart Rate Status Card */}
                    <div className={`monitoring-vital-card monitoring-vital-card--${getFHRStatus()}`}>
                        <div className="monitoring-vital-card__icon monitoring-vital-card__icon--fetal">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10" />
                                <path d="M12 6C12 6 8 10 8 14C8 16.21 9.79 18 12 18C14.21 18 16 16.21 16 14C16 10 12 6 12 6Z" />
                            </svg>
                        </div>
                        <div className="monitoring-vital-card__content">
                            <span className="monitoring-vital-card__label">Detak Jantung Janin</span>
                            <span className="monitoring-vital-card__value">{currentFHR} <small>bpm</small></span>
                        </div>
                        <StatusBadge 
                            status={getFHRStatus()} 
                            size="small"
                            label={getFHRStatus() === 'success' ? 'Normal' : getFHRStatus() === 'warning' ? 'Perhatian' : 'Kritis'}
                        />
                    </div>
                </div>
            </div>

            {/* Waveform */}
            <div className="monitoring-waveform">
                <WaveformChart
                    isLive={true}
                    height={180}
                    showGrid={true}
                    showMarkers={true}
                    signalQuality={signalQuality}
                    markers={[
                        { position: 120, type: 'acceleration', label: 'A' },
                        { position: 280, type: 'acceleration', label: 'A' },
                        { position: 380, type: 'acceleration', label: 'A' }
                    ]}
                />
            </div>

            {/* Counters */}
            <div className="monitoring-counters">
                <div className="monitoring-counter">
                    <span className="monitoring-counter__value monitoring-counter__value--success">
                        {counters.accelerations}
                    </span>
                    <span className="monitoring-counter__label">{t('monitoring.accelerations')}</span>
                </div>
                <div className="monitoring-counter">
                    <span className="monitoring-counter__value monitoring-counter__value--critical">
                        {counters.decelerations}
                    </span>
                    <span className="monitoring-counter__label">{t('monitoring.decelerations')}</span>
                </div>
                <div className="monitoring-counter">
                    <span className="monitoring-counter__value monitoring-counter__value--info">
                        {counters.movements}
                    </span>
                    <span className="monitoring-counter__label">{t('monitoring.movements')}</span>
                </div>
            </div>

            {/* Risk Score */}
            <div className={`monitoring-risk monitoring-risk--${getRiskLevel().status}`}>
                <div className="monitoring-risk__header">
                    <h3>{t('monitoring.riskScore')}</h3>
                    <StatusBadge
                        status={getRiskLevel().status}
                        label={getRiskLevel().label}
                    />
                </div>
                <div className="monitoring-risk__score">
                    <span className="monitoring-risk__value">{riskScore}%</span>
                    <div className="monitoring-risk__bar">
                        <div
                            className="monitoring-risk__bar-fill"
                            style={{ width: `${riskScore}%` }}
                        />
                    </div>
                    <span className="monitoring-risk__confidence">
                        {t('monitoring.confidence')}: 94%
                    </span>
                </div>

                {/* Explainability Panel */}
                <div className="monitoring-explain">
                    <h4>{t('monitoring.explainability')}</h4>
                    <p>{t('monitoring.explainabilityText')}</p>
                </div>
            </div>

            {/* Stop Button */}
            <button className="monitoring-stop-btn" onClick={handleStop}>
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
                {t('home.stopMonitoring')}
            </button>
        </div>
    );
};

export default MonitoringScreen;
