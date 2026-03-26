import React, { useState } from 'react';
import './styles/design-tokens.css';
import './styles/components.css';

// Components
import { BottomNav, EmergencyButton } from './components';

// Screens
import {
  HomeScreen,
  MonitoringScreen,
  OnboardingScreen,
  HistoryScreen,
  NotificationsScreen,
  SettingsScreen,
  LoginScreen,
  ProfileScreen
} from './screens/mobile';

function App() {
  const [currentScreen, setCurrentScreen] = useState('home');
  const [isLoggedIn, setIsLoggedIn] = useState(true);
  const [isOnboarded, setIsOnboarded] = useState(true); // Set to false for first-time users
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [patientData, setPatientData] = useState({
    fullName: '',
    pregnancyWeek: 32,
    // other patient data
  });

  const handleTabChange = (tab) => {
    if (tab === 'notifications') {
      setCurrentScreen('notifications');
    } else if (tab === 'history') {
      setCurrentScreen('history');
    } else if (tab === 'settings') {
      setCurrentScreen('settings');
    } else if (tab === 'monitoring') {
      setCurrentScreen('monitoring');
    } else if (tab === 'profile') {
      setCurrentScreen('profile');
    } else {
      setCurrentScreen('home');
    }
  };

  const handleStartMonitoring = () => {
    setIsMonitoring(true);
    setCurrentScreen('monitoring');
  };

  const handleStopMonitoring = () => {
    setIsMonitoring(false);
    setCurrentScreen('home');
  };

  const handleOnboardingComplete = (data) => {
    console.log('Onboarding complete:', data);
    setIsOnboarded(true);
    setCurrentScreen('home');
  };

  const handleLogin = (userData) => {
    console.log('Login successful:', userData);
    setIsLoggedIn(true);
    setPatientData(prev => ({ ...prev, ...userData }));
    setCurrentScreen('home');
  };

  const handleRegister = (userData) => {
    console.log('Registration successful:', userData);
    setIsLoggedIn(true);
    setPatientData(prev => ({ ...prev, ...userData }));
    setCurrentScreen('profile'); // Go to profile to complete data
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setCurrentScreen('login');
  };

  const handleSaveProfile = (profileData) => {
    console.log('Profile saved:', profileData);
    setPatientData(prev => ({ ...prev, ...profileData }));
  };

  const handleEmergency = (type) => {
    console.log('Emergency action:', type);
    alert(`Menghubungi ${type === 'clinic' ? 'Klinik' : 'Layanan Darurat'}...`);
  };

  const handleGoBack = () => {
    setCurrentScreen('home');
  };

  // Show login screen for unauthenticated users
  if (!isLoggedIn) {
    return (
      <LoginScreen 
        onLogin={handleLogin} 
        onRegister={handleRegister}
      />
    );
  }

  // Show onboarding for first-time users
  if (!isOnboarded) {
    return <OnboardingScreen onComplete={handleOnboardingComplete} />;
  }

  const renderScreen = () => {
    switch (currentScreen) {
      case 'monitoring':
        return (
          <MonitoringScreen
            onBack={handleGoBack}
            onStop={handleStopMonitoring}
            patientData={patientData}
          />
        );
      case 'history':
        return (
          <HistoryScreen
            onBack={handleGoBack}
            onSelectSession={(id) => console.log('Selected session:', id)}
          />
        );
      case 'notifications':
        return (
          <NotificationsScreen
            onBack={handleGoBack}
          />
        );
      case 'settings':
        return (
          <SettingsScreen
            onBack={handleGoBack}
            onLogout={handleLogout}
          />
        );
      case 'profile':
        return (
          <ProfileScreen
            patientData={patientData}
            onBack={handleGoBack}
            onSave={handleSaveProfile}
          />
        );
      case 'home':
      default:
        return (
          <HomeScreen
            onStartMonitoring={handleStartMonitoring}
            onStopMonitoring={handleStopMonitoring}
            isMonitoring={isMonitoring}
            patientData={patientData}
            onOpenProfile={() => setCurrentScreen('profile')}
            onNavigate={handleTabChange}
          />
        );
    }
  };

  return (
    <div className="app font-display">
      {renderScreen()}

      {/* Emergency Button - always visible except during monitoring */}
      {currentScreen !== 'monitoring' && (
        <EmergencyButton
          onEmergency={handleEmergency}
          clinicPhone="+62211234567"
        />
      )}

      {/* Bottom Navigation */}
      <BottomNav
        activeTab={currentScreen === 'home' ? 'home' : currentScreen}
        onTabChange={handleTabChange}
        notificationCount={2}
      />
    </div>
  );
}

export default App;
