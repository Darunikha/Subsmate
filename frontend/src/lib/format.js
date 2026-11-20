const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const compactCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  notation: 'compact',
  maximumFractionDigits: 1,
});

export const money = (value) => currency.format(Number(value || 0));
export const moneyCompact = (value) => compactCurrency.format(Number(value || 0));

function parseDate(value) {
  if (!value) return null;
  // Date-only strings are local calendar dates, not UTC midnight.
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  return new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`);
}

export function formatDate(value) {
  const date = parseDate(value);
  return date ? date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
}

export function formatMonth(key) {
  const [y, m] = key.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'short' });
}

export function formatMonthYear(key) {
  const [y, m] = key.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

export function timeAgo(value) {
  const date = parseDate(value);
  if (!date) return '';
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const units = [
    ['year', 31536000],
    ['month', 2592000],
    ['day', 86400],
    ['hour', 3600],
    ['minute', 60],
  ];
  for (const [unit, size] of units) {
    const amount = Math.floor(Math.abs(seconds) / size);
    if (amount >= 1) {
      return seconds > 0 ? `${amount} ${unit}${amount > 1 ? 's' : ''} ago` : `in ${amount} ${unit}${amount > 1 ? 's' : ''}`;
    }
  }
  return formatDate(value);
}

export function daysLabel(days) {
  if (days === 0) return 'Expires today';
  if (days === 1) return 'Expires tomorrow';
  if (days > 0) return `${days} days left`;
  if (days === -1) return 'Expired yesterday';
  return `Expired ${-days} days ago`;
}

export const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Mirrors the backend expiry rule: add calendar months, clamping the day. */
export function calculateExpiry(isoDate, cycle) {
  const months = { monthly: 1, quarterly: 3, yearly: 12 }[cycle];
  if (!isoDate || !months) return null;
  const [y, m, d] = isoDate.split('-').map(Number);
  const index = m - 1 + months;
  const year = y + Math.floor(index / 12);
  const month = index % 12;
  const lastDay = new Date(year, month + 1, 0).getDate();
  const day = Math.min(d, lastDay);
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

export const CYCLE_LABELS = { monthly: 'Monthly', quarterly: 'Quarterly', yearly: 'Yearly' };
export const CYCLE_SHORT = { monthly: 'mo', quarterly: 'qtr', yearly: 'yr' };

export const STATUS_LABELS = {
  active: 'Active',
  expiring_soon: 'Expiring soon',
  expired: 'Expired',
  cancelled: 'Cancelled',
  inactive: 'Inactive',
  paid: 'Paid',
  pending: 'Pending',
  failed: 'Failed',
};

export const METHOD_LABELS = {
  cash: 'Cash',
  bank_transfer: 'Bank transfer',
  card: 'Card',
  upi: 'UPI',
  cheque: 'Cheque',
  other: 'Other',
};

export const initials = (name = '') =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
