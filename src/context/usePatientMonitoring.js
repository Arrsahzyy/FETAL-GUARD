import { useContext } from 'react';
import PatientMonitoringContext from './patientMonitoringContext';

export function usePatientMonitoring() {
  const context = useContext(PatientMonitoringContext);
  if (!context) {
    throw new Error('usePatientMonitoring must be used within PatientMonitoringProvider');
  }
  return context;
}
