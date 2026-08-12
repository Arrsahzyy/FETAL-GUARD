/**
 * Shared formatting utilities
 */

const LOCALE_MAP = {
  id: 'id-ID',
  en: 'en-US',
};

const UNAVAILABLE_LABEL = {
  id: 'Belum tersedia',
  en: 'Not available',
};

const JUST_NOW_LABEL = {
  id: 'baru saja',
  en: 'just now',
};

const TIME_UNITS = {
  id: {
    minute: 'menit lalu',
    hour: 'jam lalu',
    day: 'hari lalu',
    hourShort: 'j',
    minuteShort: 'm',
  },
  en: {
    minute: 'minutes ago',
    hour: 'hours ago',
    day: 'days ago',
    hourShort: 'h',
    minuteShort: 'm',
  },
};

function resolveLocale(locale = 'id') {
  return LOCALE_MAP[locale] || LOCALE_MAP.id;
}

export function getUnavailableLabel(locale = 'id') {
  return UNAVAILABLE_LABEL[locale] || UNAVAILABLE_LABEL.id;
}

export function formatRelativeTime(value, locale = 'id') {
  const unavailable = getUnavailableLabel(locale);
  if (!value) return unavailable;

  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return unavailable;

  const diffMs = Date.now() - parsed;
  if (diffMs < 60_000) return JUST_NOW_LABEL[locale] || JUST_NOW_LABEL.id;

  const units = TIME_UNITS[locale] || TIME_UNITS.id;
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} ${units.minute}`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ${units.hour}`;

  const days = Math.floor(hours / 24);
  return `${days} ${units.day}`;
}

export function formatDateTime(value, locale = 'id') {
  const unavailable = getUnavailableLabel(locale);
  if (!value) return unavailable;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return unavailable;

  return parsed.toLocaleString(resolveLocale(locale), {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDateLong(value = new Date(), locale = 'id') {
  return new Date(value).toLocaleDateString(resolveLocale(locale), {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

export function formatDuration(startTime, endTime, status, locale = 'id') {
  if (!startTime) return getUnavailableLabel(locale);

  const start = new Date(startTime).getTime();
  const end = status === 'active' ? Date.now() : new Date(endTime || startTime).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return getUnavailableLabel(locale);

  const units = TIME_UNITS[locale] || TIME_UNITS.id;
  const totalMinutes = Math.max(1, Math.floor((end - start) / 60_000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0) return `${hours}${units.hourShort} ${minutes}${units.minuteShort}`;
  return `${minutes}${units.minuteShort}`;
}
