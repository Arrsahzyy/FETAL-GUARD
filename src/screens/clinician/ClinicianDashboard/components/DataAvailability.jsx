import React from 'react';

export default function DataAvailability({ label, value, status = 'missing' }) {
  return (
    <div className="data-availability__row">
      <span>{label}</span>
      <strong className={`data-availability__value data-availability__value--${status}`}>{value}</strong>
    </div>
  );
}
