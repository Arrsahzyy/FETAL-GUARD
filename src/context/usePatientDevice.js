import { useContext } from 'react';
import PatientDeviceContext from './patientDeviceContext';

export function usePatientDevice() {
  const context = useContext(PatientDeviceContext);
  if (!context) {
    throw new Error('usePatientDevice must be used within PatientDeviceProvider');
  }
  return context;
}
