import React from 'react';
import { useI18n } from '../../../../i18n/useI18n';
import { getRiskMeta } from '../../../../utils/clinicianModels';

export default function RiskBadge({ risk }) {
  const { locale } = useI18n();
  const meta = getRiskMeta(risk, locale);
  return <span className={`risk-badge risk-badge--${meta.className}`}>{meta.label}</span>;
}
