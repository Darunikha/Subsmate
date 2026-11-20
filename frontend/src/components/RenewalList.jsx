import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { daysLabel, formatDate, money } from '../lib/format';
import { RenewModal } from './forms';
import { Avatar, IconButton, StatusBadge } from './ui';

/** Renewal rows with a coloured urgency rail: red expired, orange soon, green later. */
export default function RenewalList({ items, onChanged, compact }) {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [renewing, setRenewing] = useState(null);

  return (
    <>
      <ul className={`renewal-list ${compact ? 'renewal-list-compact' : ''}`}>
        {items.map((sub) => (
          <li key={sub.id} className={`renewal-row renewal-${sub.status}`}>
            <span className="renewal-rail" />
            <Avatar name={sub.customer.full_name} />
            <div className="renewal-main">
              <strong>{sub.customer.full_name}</strong>
              <span className="muted">
                {sub.service_name} · {sub.status === 'expired' ? 'Expired' : 'Renews'} {formatDate(sub.expiry_date)}
              </span>
            </div>
            <div className="renewal-amount">
              <strong>{money(sub.amount)}</strong>
              <span className={`days days-${sub.status}`}>{daysLabel(sub.days_until_expiry)}</span>
            </div>
            {!compact && (
              <div className="renewal-status">
                <StatusBadge status={sub.status} />
              </div>
            )}
            <div className="row-actions">
              {can('renewSubscriptions') && (
                <IconButton icon="refresh" label="Renew" tone="accent" onClick={() => setRenewing(sub)} />
              )}
              <IconButton icon="eye" label="View details" onClick={() => navigate(`/subscriptions/${sub.id}`)} />
            </div>
          </li>
        ))}
      </ul>
      {renewing && (
        <RenewModal
          subscription={renewing}
          onClose={() => setRenewing(null)}
          onSaved={() => {
            setRenewing(null);
            onChanged?.();
          }}
        />
      )}
    </>
  );
}
