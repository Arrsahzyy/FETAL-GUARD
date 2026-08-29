const finiteOrNull = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

export function getPatientLiveReadings(telemetry, isLiveTelemetry) {
  if (!isLiveTelemetry || !telemetry || typeof telemetry !== 'object') {
    return {
      fhr: null,
      maternalHeartRate: null,
      spo2: null,
      signalQuality: null,
      contractionLevel: null,
    };
  }

  return {
    fhr: finiteOrNull(telemetry.fhr),
    maternalHeartRate: finiteOrNull(telemetry.maternalHeartRate),
    spo2: finiteOrNull(telemetry.spo2),
    signalQuality: finiteOrNull(telemetry.signalQuality),
    contractionLevel: finiteOrNull(telemetry.contractionLevel),
  };
}
