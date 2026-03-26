# 🤖 AI AGENT PROMPT: Buat Sistem FETAL-GUARD

> **Instruksi:** Copy seluruh isi file ini dan paste ke AI coding agent (seperti Claude, GPT-4, Cursor, dll) untuk membuat sistem serupa.

---

## PERINTAH UNTUK AI AGENT

Buatkan sistem **wearable health monitoring application** dengan spesifikasi lengkap berikut. Sistem ini adalah aplikasi React untuk memantau kesehatan janin menggunakan sensor piezoelektrik.

---

## 1. PROJECT SETUP

```
Tech Stack:
- Frontend: React 19+ dengan Vite
- Styling: CSS dengan Design Tokens (CSS Variables)
- State: React useState (local state)
- i18n: Custom JSON-based (Indonesian + English)
- API Spec: OpenAPI 3.0.3

Struktur Folder:
src/
├── App.jsx                    # Root component & routing
├── main.jsx                   # Entry point
├── components/                # Reusable UI components
│   ├── index.js              # Export barrel
│   ├── FHRDisplay/           # Heart rate display
│   ├── StatusBadge/          # Status indicators
│   ├── AlertCard/            # Alert notifications
│   ├── WaveformChart/        # Real-time graph
│   ├── BottomNav/            # Navigation bar
│   └── EmergencyButton/      # Emergency action
├── screens/
│   ├── mobile/               # Patient app screens
│   │   ├── LoginScreen/
│   │   ├── OnboardingScreen/
│   │   ├── HomeScreen/
│   │   ├── MonitoringScreen/
│   │   ├── HistoryScreen/
│   │   ├── ProfileScreen/
│   │   ├── NotificationsScreen/
│   │   └── SettingsScreen/
│   └── clinician/            # Clinician dashboard
│       └── ClinicianDashboard/
├── i18n/                     # Translations
│   ├── index.js
│   ├── id.json
│   └── en.json
└── styles/
    ├── design-tokens.css     # CSS variables
    └── components.css        # Global styles
api/
├── openapi.yaml              # API specification
└── schemas/
    ├── patient-schema.json
    └── session-schema.json
data/
├── mock-patients.json
└── mock-sessions.json
```

---

## 2. DATA MODELS

### Patient Schema (Profil Pasien)
```json
{
  "id": "uuid",
  "patient_id": "PAT-2024-001",
  "name": "string (max 200)",
  "email": "email",
  "phone": "+628xxxxx",
  "birth_date": "YYYY-MM-DD",
  "age": "14-60",
  
  "lmp_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "gestational_age_weeks": "0-45",
  "gestational_age_days": "0-6",
  "gravida": "number",
  "para": "number",
  
  "weight_kg": "30-200",
  "height_cm": "100-250",
  "bmi": "10-60",
  "blood_type": "A+|A-|B+|B-|AB+|AB-|O+|O-|unknown",
  
  "medical_history": {
    "diabetes": "boolean",
    "gestational_diabetes": "boolean",
    "hypertension": "boolean",
    "chronic_hypertension": "boolean",
    "heart_disease": "boolean",
    "preeclampsia": "boolean",
    "preeclampsia_history": "boolean",
    "thyroid_disorder": "boolean",
    "autoimmune_disease": "boolean",
    "previous_cesarean": "boolean",
    "other": "string"
  },
  
  "medications_current": [
    { "name": "string", "dosage": "string", "frequency": "string" }
  ],
  
  "allergies": ["string"],
  
  "emergency_contact": {
    "name": "string (required)",
    "relation": "spouse|parent|sibling|friend|other",
    "phone": "string (required)"
  },
  
  "clinic_id": "uuid",
  "clinic_name": "string",
  "clinician_id": "uuid",
  "clinician_name": "string",
  
  "consent_timestamp": "ISO-8601",
  "consent_version": "1.2.0",
  
  "privacy_flags": {
    "location_share_allowed": "boolean",
    "upload_allowed_wifi_only": "boolean"
  },
  
  "stats": {
    "total_sessions": "number",
    "total_monitoring_hours": "number",
    "last_session_date": "ISO-8601",
    "current_risk_level": "low|medium|high",
    "active_alerts": "number"
  }
}
```

### Session Schema (Sesi Monitoring)
```json
{
  "session_id": "uuid",
  "patient_id": "uuid",
  
  "device_serial": "FG-2024-XXXXXX",
  "device_model": "FETAL-GUARD-V2",
  "device_firmware_version": "X.X.X",
  
  "start_time": "ISO-8601",
  "end_time": "ISO-8601 | null",
  "duration_seconds": "number",
  "time_zone": "Asia/Jakarta",
  "sampling_rate_hz": "250",
  "channel_count": "4",
  "status": "active|stopped|completed|error",
  
  "fhr_summary": {
    "baseline_bpm": "60-220",
    "min_bpm": "number",
    "max_bpm": "number",
    "mean_bpm": "number",
    "variability": "number",
    "variability_classification": "absent|minimal|moderate|marked"
  },
  
  "events": [
    {
      "event_id": "string",
      "type": "acceleration|early_deceleration|late_deceleration|variable_deceleration|prolonged_deceleration|fetal_movement|contraction",
      "timestamp": "ISO-8601",
      "duration_ms": "number",
      "severity": "mild|moderate|severe",
      "fhr_peak": "number",
      "fhr_nadir": "number",
      "confidence": "0-1"
    }
  ],
  
  "risk_assessment": {
    "score": "0-100",
    "level": "low|medium|high",
    "confidence": "0-1",
    "model_version": "string",
    "model_type": "ml_on_device|ml_cloud",
    "explainability": "string (penjelasan bahasa)",
    "contributing_factors": [
      { "factor": "string", "impact": "0-1", "description": "string" }
    ]
  },
  
  "signal_quality": {
    "overall_percentage": "0-100",
    "classification": "excellent|good|fair|poor"
  }
}
```

---

## 3. SCREEN SPECIFICATIONS

### 3.1 LoginScreen
```javascript
// PURPOSE: User authentication (login/register)
// STATE:
isLogin: boolean                    // Toggle mode
formData: {
  email: string,                    // Required, email format
  password: string,                 // Required, min 6 chars
  name: string,                     // Register only
  phone: string,                    // Register only
  confirmPassword: string           // Register only, must match
}
errors: {}                          // Validation errors
isLoading: boolean

// CALLBACKS:
onLogin(userData)    → Set logged in, navigate to home
onRegister(userData) → Set logged in, navigate to profile
```

### 3.2 OnboardingScreen
```javascript
// PURPOSE: First-time user setup (7 steps)
// STEPS:
1. Welcome     - App introduction
2. Profile     - Name, LMP date, birth date, weight, height
3. Medical     - Medical history checkboxes
4. Emergency   - Emergency contact info
5. Setup       - Device setup guide
6. Permissions - Bluetooth, Notifications, Location
7. Consent     - Digital consent with timestamp

// STATE:
currentStep: 0-6
formData: {
  name, patientId, lmpDate, birthDate, weight, height,
  medicalHistory: { diabetes, hypertension, heartDisease, preeclampsia, other },
  emergencyContact: { name, relation, phone },
  clinic, consent, consentTimestamp
}
permissions: { bluetooth, notifications, location }

// COMPUTED:
calculateBMI() → weight / (height in m)²
calculateGestationalAge() → { weeks, days } from LMP
```

### 3.3 HomeScreen
```javascript
// PURPOSE: Main dashboard
// PROPS:
onStartMonitoring, onStopMonitoring, isMonitoring, patientData, onOpenProfile

// DISPLAY DATA:
patientName, gestationalWeeks, gestationalDays
device: { connected, signalQuality (0-100), battery, lastSync, fhr }

// COMPUTED - Fetal Status based on FHR:
110-160 bpm → { status: "normal", icon: "💚", color: "success" }
100-110 or 160-180 → { status: "watch", icon: "💛", color: "warning" }
<100 or >180 → { status: "alert", icon: "❤️", color: "critical" }

// FEATURES:
- Welcome banner with branding
- FHR display with sparkline trend
- Signal quality & battery indicators
- Start monitoring button
- Daily tips
```

### 3.4 MonitoringScreen
```javascript
// PURPOSE: Active monitoring session
// REAL-TIME STATE (update every 1s):
sessionDuration: number (seconds)
currentFHR: 110-170 bpm (simulated)
motherHeartRate: 60-110 bpm
bloodPressure: { systolic: 90-140, diastolic: 60-90 }
signalQuality: "excellent|good|fair|poor"
riskScore: 0-100
counters: { accelerations, decelerations, movements }

// STATUS FUNCTIONS:
getFHRStatus()      → success (110-160), warning (100-110 or 160-170), critical
getMotherHRStatus() → success (60-100), warning (100-110), critical
getBPStatus()       → success (≤120/80), warning (≤139/89), critical (≥140/90)
getRiskLevel()      → low (<25), medium (25-60), high (>60)

// UI COMPONENTS:
- Duration timer
- Pregnancy week banner
- FHRDisplay component
- Mother vitals grid (Heart Rate, Blood Pressure, FHR card)
- WaveformChart (real-time graph)
- Event counters
- Risk score bar with explainability
- Stop button
```

### 3.5 HistoryScreen
```javascript
// PURPOSE: Session history list
// STATE:
filter: "all|low|medium|high"
dateRange: "week|month|all"

// SESSION DATA:
{ id, date, time, duration, meanFhr, riskLevel, events: { accelerations, decelerations, movements }, signalQuality }

// STATS:
{ totalSessions, totalHours, avgFhr, normalSessions, watchSessions, alarmSessions }

// FEATURES:
- Stats summary cards
- Risk distribution bar
- Filter tabs
- Grouped by date list
- Export button
```

### 3.6 ProfileScreen
```javascript
// PURPOSE: Patient profile management
// TABS: Biodata, Kehamilan (Pregnancy), Rekam Medis (Medical Records)

// BIODATA:
fullName, nik (16 digit), birthDate, bloodType, address, phone, emergencyContact, emergencyPhone

// PREGNANCY:
pregnancyWeek, expectedDueDate, lastMenstrualDate, gravida, para, abortus, height, weightBeforePregnancy, currentWeight

// MEDICAL:
hasHypertension, hasDiabetes, hasHeartDisease, hasAsthma, hasAllergies, allergiesDetail, otherConditions, currentMedications, previousComplications, previousDeliveryType

// CALLBACKS:
onBack(), onSave(formData)
```

### 3.7 NotificationsScreen
```javascript
// PURPOSE: Alert and notification list
// NOTIFICATION STRUCTURE:
{ id, type: "critical|warning|info", title, message, timestamp, recommendation, acknowledged, sessionId }

// FILTERS: Semua, Belum Dibaca, Kritis, Peringatan

// FEATURES:
- Filter tabs
- AlertCard list
- Acknowledge action
- Link to related session
```

### 3.8 SettingsScreen
```javascript
// PURPOSE: App settings
// SETTINGS:
language: "id|en"
pushNotifications, criticalAlerts, soundAlerts, hapticFeedback: boolean
lowBatteryThreshold: 10|15|20|30
uploadWifiOnly, shareLocation, autoEscalation: boolean
darkMode: boolean
onDeviceInference, cloudInference: boolean

// DEVICE INFO (read-only):
{ serial, model, firmware, battery, lastSync }

// USER INFO:
{ name, patientId, clinic, clinician }

// CALLBACKS:
onBack(), onLogout()
```

### 3.9 ClinicianDashboard
```javascript
// PURPOSE: Clinician/doctor dashboard
// PATIENT DATA:
{ id, name, gestationalAge, lastSession, currentRisk, lastFhr, activeAlerts, signalQuality }

// ALERT DATA:
{ id, patientId, patientName, type, message, timestamp, sessionId, acknowledged }

// STATS:
{ total, monitoring, highRisk, alerts }

// FEATURES:
- Sidebar navigation
- Patient list with search & filter
- Alert queue with acknowledge
- Patient detail modal
- Risk color coding
```

---

## 4. REUSABLE COMPONENTS

### FHRDisplay
```javascript
Props: { value, unit="bpm", label, showAnimation, size="small|medium|large" }
// Auto color based on FHR: normal (110-160), warning, critical
// Animated value change
// Pulse animation SVG
```

### StatusBadge
```javascript
Props: { status="success|warning|critical|info", label, value, showIcon, size }
// Icon per status type
// Color coding
```

### AlertCard
```javascript
Props: { type, title, message, timestamp, recommendation, acknowledged, onAcknowledge, onAction, actionLabel }
// Icon based on type
// Acknowledge button
// Action button
```

### WaveformChart
```javascript
Props: { data, height, showGrid, showMarkers, markers, isLive, signalQuality }
// Canvas-based rendering
// Real-time waveform generation
// Marker indicators (acceleration/deceleration)
// Grid overlay
// Responsive resize
```

### BottomNav
```javascript
Props: { activeTab, onTabChange, hasNotification }
// 5 tabs: home, monitoring, history, notifications, settings
// Badge indicator for notifications
// Active state styling
```

### EmergencyButton
```javascript
Props: { onEmergency, clinicPhone, emergencyPhone="112", disabled }
// 2-step confirmation modal
// Call clinic or emergency options
```

---

## 5. DESIGN TOKENS

```css
:root {
  /* Colors */
  --color-primary-pink: #FF6B9A;
  --color-primary-blue: #4AA3FF;
  --color-success: #28C76F;
  --color-warning: #FFB020;
  --color-critical: #FF3B30;
  --color-bg-primary: #F6F8FB;
  --color-text-primary: #1A1D26;
  --color-text-secondary: #6B7280;
  
  /* Gradients */
  --gradient-primary: linear-gradient(135deg, #FF6B9A 0%, #4AA3FF 100%);
  
  /* Typography */
  --font-family: 'Inter', sans-serif;
  --font-size-xs: 0.75rem;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-size-2xl: 1.5rem;
  --font-size-fhr: clamp(3rem, 8vw, 5rem);
  
  /* Spacing */
  --spacing-1: 0.25rem;
  --spacing-2: 0.5rem;
  --spacing-4: 1rem;
  --spacing-6: 1.5rem;
  --spacing-8: 2rem;
  
  /* Border Radius */
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
  --radius-full: 9999px;
  
  /* Shadows */
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-glow-pink: 0 0 20px rgba(255, 107, 154, 0.4);
}
```

---

## 6. BUSINESS LOGIC RULES

### FHR Classification
| Range (bpm) | Status | Color | Action |
|-------------|--------|-------|--------|
| 110-160 | Normal ✅ | success/green | Continue |
| 100-110 atau 160-180 | Watch ⚠️ | warning/yellow | Monitor closely |
| <100 atau >180 | Alert 🚨 | critical/red | Contact clinic |

### Risk Score Classification
| Score | Level | Action |
|-------|-------|--------|
| 0-24 | Low | Normal monitoring |
| 25-59 | Medium | Watch, consider consultation |
| 60-100 | High | Immediate medical attention |

### FHR Variability
| Variability (bpm) | Classification |
|-------------------|----------------|
| <5 | Absent (concerning) |
| 5-9 | Minimal (watch) |
| 10-25 | Moderate (normal) |
| >25 | Marked (evaluate) |

---

## 7. API ENDPOINTS (OpenAPI)

```yaml
# Authentication
POST /auth/login          # Login
POST /auth/refresh        # Refresh token
POST /auth/logout         # Logout

# Patients
GET    /patients          # List all (clinician)
GET    /patients/{id}     # Get detail
PATCH  /patients/{id}     # Update profile
GET    /patients/me       # Current user

# Devices
POST   /devices/pair      # Pair device
GET    /devices/{id}      # Get info
DELETE /devices/{id}      # Unpair
PUT    /devices/{id}/status # Update status

# Sessions
GET    /sessions          # List sessions
POST   /sessions          # Start session
GET    /sessions/{id}     # Get detail
PATCH  /sessions/{id}     # Update/stop
POST   /sessions/{id}/data # Upload data chunk
GET    /sessions/{id}/export # Export PDF

# Notifications
GET    /notifications     # List all
PATCH  /notifications/{id} # Mark read
```

---

## 8. INTERNATIONALIZATION

Implement bilingual support (Indonesian + English) with JSON files:

```javascript
// i18n/index.js
export const t = (key, params = {}) => {
  // Get translation by dot notation: t('home.greeting')
  // Support params: t('key', { name: 'value' })
}
export const setLocale = (locale) => { /* 'id' | 'en' */ }
export const getLocale = () => currentLocale
```

Key sections to translate:
- App name & tagline
- Onboarding steps
- Home screen labels
- Monitoring metrics
- Alert messages
- Settings labels
- Error messages

---

## 9. MOCK DATA

Generate realistic mock data for:
1. **5-10 patients** with varied:
   - Gestational ages (28-37 weeks)
   - Risk levels (mostly low, some medium/high)
   - Medical histories
   
2. **10-20 sessions** with:
   - Various durations (30-60 min)
   - Different FHR patterns
   - Events (accelerations, decelerations)
   - Risk assessments

---

## 10. ADDITIONAL REQUIREMENTS

1. **Responsive Design**: Mobile-first, support tablets
2. **Dark Mode**: Implement with CSS variables
3. **Accessibility**: ARIA labels, semantic HTML
4. **Performance**: 
   - Animated value transitions
   - Efficient canvas rendering for waveform
   - Lazy loading where appropriate
5. **Error Handling**: Form validation, error states
6. **Loading States**: Skeleton/spinner during async ops

---

## QUICK START COMMAND

```bash
npm create vite@latest fetal-guard -- --template react
cd fetal-guard
npm install
# Then implement the structure above
```

---

**END OF PROMPT - Copy everything above this line to your AI agent**
