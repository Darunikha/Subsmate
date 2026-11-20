import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { SubscriptionForm } from '../components/forms';
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Pager,
  SearchInput,
  Spinner,
  StatusBadge,
  Tabs,
} from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useApi, useDebounced } from '../lib/hooks';
import { daysLabel, formatDate, money } from '../lib/format';

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'current', label: 'Current' },
  { value: 'expiring_soon', label: 'Expiring soon' },
  { value: 'expired', label: 'Expired' },
  { value: 'cancelled', label: 'Cancelled' },
];

export default function Subscriptions() {
  const { user, can } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || '';
  const planId = params.get('plan_id') || '';
  const [term, setTerm] = useState('');
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [plans, setPlans] = useState([]);
  const q = useDebounced(term);
  const isCustomer = user.role === 'customer';
  const { data, error, loading, reload } = useApi('/subscriptions', { status, plan_id: planId, q, page });

  useEffect(() => {
    if (!isCustomer) api.get('/plans').then((d) => setPlans(d.items)).catch(() => {});
  }, [isCustomer]);

  const setFilter = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title={isCustomer ? 'My Subscriptions' : 'Subscriptions'}
        subtitle={isCustomer ? 'Your plans, expiry dates and renewal status.' : 'Create, track and manage customer subscriptions.'}
        actions={
          can('manageSubscriptions') && (
            <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
              New subscription
            </Button>
          )
        }
      />
      <Card bodyClass="card-body-flush">
        <div className="toolbar">
          <Tabs value={status} onChange={(v) => setFilter('status', v)} tabs={STATUS_TABS} />
          <div className="toolbar-right">
            {!isCustomer && (
              <select className="select-sm" value={planId} onChange={(e) => setFilter('plan_id', e.target.value)} aria-label="Filter by plan">
                <option value="">All plans</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            )}
            <SearchInput
              value={term}
              onChange={(v) => {
                setTerm(v);
                setPage(1);
              }}
              placeholder={isCustomer ? 'Search plans' : 'Search customer, plan or ID'}
            />
          </div>
        </div>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : loading && !data ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <EmptyState icon="card" title="No subscriptions found" message="Try another filter or search term." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Subscription</th>
                  {!isCustomer && <th>Customer</th>}
                  <th className="hide-sm">Start</th>
                  <th>Expiry</th>
                  <th className="num">Amount</th>
                  <th className="hide-sm">Payment</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((s) => (
                  <tr key={s.id} className="row-link" onClick={() => navigate(`/subscriptions/${s.id}`)}>
                    <td>
                      <div className="cell-main">
                        <strong>{s.plan.name}</strong>
                        <span className="muted">{s.code}</span>
                      </div>
                    </td>
                    {!isCustomer && (
                      <td>
                        <div className="cell-main">
                          <strong>{s.customer.full_name}</strong>
                          <span className="muted">{s.customer.email}</span>
                        </div>
                      </td>
                    )}
                    <td className="hide-sm">{formatDate(s.start_date)}</td>
                    <td>
                      <div className="cell-main">
                        <span>{formatDate(s.expiry_date)}</span>
                        {s.status !== 'cancelled' && (
                          <span className={`days days-${s.status}`}>{daysLabel(s.days_until_expiry)}</span>
                        )}
                      </div>
                    </td>
                    <td className="num">{money(s.amount)}</td>
                    <td className="hide-sm">
                      <StatusBadge status={s.payment_status} />
                    </td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pager page={data.page} pages={data.pages} total={data.total} onChange={setPage} />}
      </Card>
      {creating && (
        <SubscriptionForm
          onClose={() => setCreating(false)}
          onSaved={(sub) => {
            setCreating(false);
            navigate(`/subscriptions/${sub.id}`);
          }}
        />
      )}
    </>
  );
}
