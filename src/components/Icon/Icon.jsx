import React from 'react';

export default function Icon({ name, className = '', ...props }) {
  const common = {
    viewBox: '0 0 24 24',
    width: '1em',
    height: '1em',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '2',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    className,
    focusable: 'false',
    'aria-hidden': 'true',
    ...props,
  };

  switch (name) {
    case 'activity':
      return <svg {...common}><path d="M22 12h-4l-3 8-6-16-3 8H2" /></svg>;
    case 'alert':
      return <svg {...common}><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>;
    case 'bell':
      return <svg {...common}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>;
    case 'calendar':
      return <svg {...common}><path d="M8 2v4" /><path d="M16 2v4" /><rect width="18" height="18" x="3" y="4" rx="2" /><path d="M3 10h18" /></svg>;
    case 'chart':
      return <svg {...common}><path d="M3 3v18h18" /><path d="m7 14 3-3 3 2 5-6" /></svg>;
    case 'check':
      return <svg {...common}><path d="m20 6-11 11-5-5" /></svg>;
    case 'chevron':
      return <svg {...common}><path d="m9 18 6-6-6-6" /></svg>;
    case 'close':
      return <svg {...common}><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>;
    case 'download':
      return <svg {...common}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" /></svg>;
    case 'eye':
      return <svg {...common}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></svg>;
    case 'file':
      return <svg {...common}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6" /><path d="M16 13H8" /><path d="M16 17H8" /></svg>;
    case 'grid':
      return <svg {...common}><rect width="7" height="7" x="3" y="3" rx="1" /><rect width="7" height="7" x="14" y="3" rx="1" /><rect width="7" height="7" x="14" y="14" rx="1" /><rect width="7" height="7" x="3" y="14" rx="1" /></svg>;
    case 'info':
      return <svg {...common}><circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" /></svg>;
    case 'log-out':
      return <svg {...common}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></svg>;
    case 'moon':
      return <svg {...common}><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z" /></svg>;
    case 'phone':
      return <svg {...common}><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2.1Z" /></svg>;
    case 'refresh':
      return <svg {...common}><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" /><path d="M3 21v-5h5" /><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" /><path d="M21 3v5h-5" /></svg>;
    case 'search':
      return <svg {...common}><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>;
    case 'settings':
      return <svg {...common}><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.4l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.6 7l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1h.3a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg>;
    case 'home':
      return <svg {...common}><path d="m3 10 9-7 9 7" /><path d="M5 9v12h14V9" /><path d="M9 21v-7h6v7" /></svg>;
    case 'history':
    case 'timer':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>;
    case 'monitor_heart':
    case 'monitoring':
    case 'cardiology':
    case 'favorite':
      return <svg {...common}><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" /><path d="M5.5 12h3l1.5-3 2.5 6 1.5-3h4.5" /></svg>;
    case 'notifications':
      return <svg {...common}><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>;
    case 'notifications_off':
      return <svg {...common}><path d="m3 3 18 18" /><path d="M18 8a6 6 0 0 0-9.3-5" /><path d="M6.3 6.3C6.1 6.8 6 7.4 6 8c0 7-3 9-3 9h14" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>;
    case 'menu_book':
      return <svg {...common}><path d="M3 5a4 4 0 0 1 4-1h4v16H7a4 4 0 0 0-4 1Z" /><path d="M21 5a4 4 0 0 0-4-1h-4v16h4a4 4 0 0 1 4 1Z" /></svg>;
    case 'arrow_back':
      return <svg {...common}><path d="m15 18-6-6 6-6" /><path d="M9 12h11" /></svg>;
    case 'arrow_forward':
      return <svg {...common}><path d="m9 18 6-6-6-6" /><path d="M4 12h11" /></svg>;
    case 'chevron_right':
      return <svg {...common}><path d="m9 18 6-6-6-6" /></svg>;
    case 'expand_more':
      return <svg {...common}><path d="m6 9 6 6 6-6" /></svg>;
    case 'sensors':
      return <svg {...common}><circle cx="12" cy="12" r="2" /><path d="M8.5 8.5a5 5 0 0 0 0 7" /><path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M5.5 5.5a9 9 0 0 0 0 13" /><path d="M18.5 5.5a9 9 0 0 1 0 13" /></svg>;
    case 'sensors_off':
      return <svg {...common}><path d="m3 3 18 18" /><circle cx="12" cy="12" r="2" /><path d="M8.5 8.5a5 5 0 0 0-1 5.5" /><path d="M15.5 8.5a5 5 0 0 1 1 5.5" /><path d="M5.5 5.5a9 9 0 0 0-1.2 11" /><path d="M18.5 5.5a9 9 0 0 1 1.2 11" /></svg>;
    case 'inventory_2':
      return <svg {...common}><path d="M4 7h16v14H4Z" /><path d="M3 3h18v4H3Z" /><path d="M9 11h6" /></svg>;
    case 'bluetooth':
    case 'bluetooth_connected':
    case 'bluetooth_searching':
      return <svg {...common}><path d="m7 7 10 10-5 4V3l5 4L7 17" />{name === 'bluetooth_connected' && <><path d="M2 12h3" /><path d="M19 12h3" /></>}{name === 'bluetooth_searching' && <><path d="M19 8a6 6 0 0 1 0 8" /><path d="M21 5a10 10 0 0 1 0 14" /></>}</svg>;
    case 'pregnant_woman':
      return <svg {...common}><circle cx="12" cy="4" r="2" /><path d="M9 22v-7H7l2-7h3" /><path d="M12 8c4 0 5 3 5 6h-5v8" /></svg>;
    case 'person':
      return <svg {...common}><circle cx="12" cy="7" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>;
    case 'signal_cellular_alt':
      return <svg {...common}><path d="M4 20v-4" /><path d="M10 20v-8" /><path d="M16 20V8" /><path d="M22 20V4" /></svg>;
    case 'show_chart':
    case 'stacked_line_chart':
    case 'analytics':
      return <svg {...common}><path d="M3 3v18h18" /><path d="m6 15 4-4 3 3 5-7" /></svg>;
    case 'warning':
    case 'error':
    case 'priority_high':
      return <svg {...common}><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></svg>;
    case 'cloud':
    case 'cloud_sync':
      return <svg {...common}><path d="M17.5 19H6a4 4 0 0 1-.6-8A6 6 0 0 1 17 8.5 5 5 0 0 1 17.5 19Z" />{name === 'cloud_sync' && <><path d="m9 13 2-2 2 2" /><path d="M11 11v5" /></>}</svg>;
    case 'clinical_notes':
    case 'medical_information':
      return <svg {...common}><path d="M7 3h10v4H7Z" /><path d="M5 5H4v16h16V5h-1" /><path d="M9 12h6" /><path d="M12 9v6" /></svg>;
    case 'spo2':
      return <svg {...common}><path d="M12 2s6 7 6 12a6 6 0 0 1-12 0c0-5 6-12 6-12Z" /><path d="M9 15h6" /></svg>;
    case 'trending_up':
      return <svg {...common}><path d="m3 17 6-6 4 4 8-8" /><path d="M15 7h6v6" /></svg>;
    case 'trending_down':
      return <svg {...common}><path d="m3 7 6 6 4-4 8 8" /><path d="M15 17h6v-6" /></svg>;
    case 'child_care':
    case 'child_friendly':
      return <svg {...common}><circle cx="12" cy="12" r="7" /><path d="M9 11h.01" /><path d="M15 11h.01" /><path d="M9 15c1.5 1 4.5 1 6 0" /><path d="M12 5V2" /></svg>;
    case 'compress':
      return <svg {...common}><path d="M8 3H3v5" /><path d="m3 3 6 6" /><path d="M16 21h5v-5" /><path d="m21 21-6-6" /><path d="M21 8V3h-5" /><path d="m21 3-6 6" /><path d="M3 16v5h5" /><path d="m3 21 6-6" /></svg>;
    case 'check_circle':
    case 'verified':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></svg>;
    case 'health_and_safety':
      return <svg {...common}><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="M9 11h6" /><path d="M12 8v6" /></svg>;
    case 'emergency':
      return <svg {...common}><path d="M8 2h8l1 6 4 4-4 4-1 6H8l-1-6-4-4 4-4Z" /><path d="M12 7v6" /><path d="M12 17h.01" /></svg>;
    case 'open_in_new':
      return <svg {...common}><path d="M15 3h6v6" /><path d="m10 14 11-11" /><path d="M18 13v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h7" /></svg>;
    case 'logout':
      return <svg {...common}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></svg>;
    case 'autorenew':
    case 'sync':
      return <svg {...common}><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" /><path d="M3 21v-5h5" /><path d="M3 12A9 9 0 0 1 18.5 5.7L21 8" /><path d="M21 3v5h-5" /></svg>;
    case 'save':
      return <svg {...common}><path d="M4 3h14l2 2v16H4Z" /><path d="M8 3v6h8V3" /><path d="M8 21v-7h8v7" /></svg>;
    case 'play_circle':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="m10 8 6 4-6 4Z" /></svg>;
    case 'battery_5_bar':
      return <svg {...common}><rect x="3" y="7" width="17" height="10" rx="2" /><path d="M22 10v4" /><path d="M6 10h9v4H6Z" /></svg>;
    case 'calendar_month':
    case 'event_available':
      return <svg {...common}><path d="M8 2v4" /><path d="M16 2v4" /><rect width="18" height="18" x="3" y="4" rx="2" /><path d="M3 10h18" /><path d="m9 15 2 2 4-4" /></svg>;
    case 'nutrition':
      return <svg {...common}><path d="M12 21c-4-3-7-7-7-11a4 4 0 0 1 7-2 4 4 0 0 1 7 2c0 4-3 8-7 11Z" /><path d="M12 8c0-3 2-5 5-5" /></svg>;
    case 'directions_walk':
      return <svg {...common}><circle cx="13" cy="4" r="2" /><path d="m10 22 2-7-3-3 2-5 4 3 3 1" /><path d="m12 15 4 3 1 4" /><path d="M9 12 5 15" /></svg>;
    case 'medication':
      return <svg {...common}><path d="m7 17 10-10a4 4 0 0 0-6-6L1 11a4 4 0 0 0 6 6Z" /><path d="m8 8 8 8" /></svg>;
    case 'call':
      return <svg {...common}><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2.1Z" /></svg>;
    case 'sun':
      return <svg {...common}><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.9 4.9 1.4 1.4" /><path d="m17.7 17.7 1.4 1.4" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m4.9 19.1 1.4-1.4" /><path d="m17.7 6.3 1.4-1.4" /></svg>;
    case 'user':
      return <svg {...common}><path d="M20 21a8 8 0 0 0-16 0" /><circle cx="12" cy="7" r="4" /></svg>;
    case 'users':
      return <svg {...common}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.9" /><path d="M16 3.1a4 4 0 0 1 0 7.8" /></svg>;
    default:
      return null;
  }
}
