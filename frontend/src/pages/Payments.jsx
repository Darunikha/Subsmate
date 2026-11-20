import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Icon from '../components/Icon';
import { PaymentForm, PaymentUpdateModal } from '../components/forms';
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
  useToast,
} from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useApi, useDebounced } from '../lib/hooks';
import { formatDate, money, METHOD_LABELS } from '../lib/format';

const TABS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'paid', label: 'Paid' },
  { value: 'failed', label: 'Failed' },
];

export default function Payments() {
  const { user, can } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = params.get('status') || '';
  const [term, setTerm] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [page, setPage] = useState(1);
  const [recording, setRecording] = useState(false);
  const [editing, setEditing] = useState(null);
  const q = useDebounced(term);
  const manage = can('managePayments');
  const isCustomer = user.role === 'customer';

  const query = {
    status: tab === 'overdue' ? '' : tab,
    overdue: tab === 'overdue' ? 'true' : '',
    q,
    from,
    to,
    page,
  };
  const { data, error, loading, reload } = useApi('/payments', query);
  const summary = data?.summary || {};

  const markPaid = async (payment) => {
    try {
      await api.put(`/payments/${payment.id}`, { status: 'paid' });
      toast.success(`${payment.code} marked as paid.`);
      reload();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const setTab = (value) => {
    setParams(value ? { status: value } : {}, { replace: true });
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title={isCustomer ? 'Payment History' : 'Payments'}
        subtitle={isCustomer ? 'Payments recorded against your subscriptions.' : 'Record payments manually and follow up on pending ones.'}
        actions={
          manage && (
            <Button variant="primary" icon="plus" onClick={() => setRecording(true)}>
              Record payment
            </Button>
          )
        }
      />

      <div className="stat-grid stat-grid-3">
        {[
          ['paid', 'Paid', 'checkCircle', 'green'],
          ['pending', 'Pending', 'clock', 'orange'],
          ['failed', 'Failed', 'alert', 'red'],
        ].map(([key, label, icon, tone]) => (
          <button key={key} type="button" className={`card stat stat-button ${tab === key ? 'stat-selected' : ''}`} onClick={() => setTab(key)}>
            <div className="stat-head">
              <Icon name={icon} size={18} className={`text-${tone}`} />
              <span>{label}</span>
            </div>
            <div className="stat-value stat-value-sm">{money(summary[key]?.amount || 0)}</div>
            <div className="stat-foot muted">
              {summary[key]?.count || 0} payment{summary[key]?.count === 1 ? '' : 's'}
            </div>
          </button>
        ))}
      </div>

      <Card bodyClass="card-body-flush">
        <div className="toolbar">
          <Tabs value={tab} onChange={setTab} tabs={TABS} />
          <div className="toolbar-right">
            <label className="date-filter">
              <span>From</span>
              <input type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} />
            </label>
            <label className="date-filter">
              <span>To</span>
              <input type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} />
            </label>
            {!isCustomer && (
              <SearchInput value={term} onChange={(v) => { setTerm(v); setPage(1); }} placeholder="Customer or reference" />
            )}
          </div>
        </div>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : loading && !data ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <EmptyState icon="wallet" title="No payments found" message="Try another filter." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Payment</th>
                  {!isCustomer && <th>Customer</th>}
                  <th className="hide-sm">Service</th>
                  <th>Due</th>
                  <th className="hide-sm">Paid on</th>
                  <th className="hide-sm">Method</th>
                  <th className="num">Amount</th>
                  <th>Status</th>
                  {manage && <th className="actions-col" aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <div className="cell-main">
                        <strong>{p.code}</strong>
                        {p.reference && <span className="muted">{p.reference}</span>}
                      </div>
                    </td>
                    {!isCustomer && (
                      <td>
                        <Link to={`/subscriptions/${p.subscription.id}`} className="cell-main">
                          <strong>{p.subscription.customer.full_name}</strong>
                          <span className="muted">{p.subscription.code}</span>
                        </Link>
                      </td>
                    )}
                    <td className="hide-sm">{p.subscription.service_name}</td>
                    <td>
                      <div className="cell-main">
                        <span>{formatDate(p.due_date)}</span>
                        {p.is_overdue && <span className="days days-expired">Overdue</span>}
                      </div>
                    </td>
                    <td className="hide-sm">{p.paid_on ? formatDate(p.paid_on) : '—'}</td>
                    <td className="hide-sm">{METHOD_LABELS[p.method] || '—'}</td>
                    <td className="num">{money(p.amount)}</td>
                    <td>
                      <StatusBadge status={p.status} />
                    </td>
                    {manage && (
                      <td className="actions-col">
                        <div className="row-actions">
                          {p.status !== 'paid' && (
                            <Button size="sm" variant="soft" onClick={() => markPaid(p)}>
                              Mark paid
                            </Button>
                          )}
                          <Button size="sm" onClick={() => setEditing(p)}>
                            Update
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pager page={data.page} pages={data.pages} total={data.total} onChange={setPage} />}
      </Card>

      {recording && (
        <PaymentForm
          onClose={() => setRecording(false)}
          onSaved={() => {
            setRecording(false);
            reload();
          }}
        />
      )}
      {editing && (
        <PaymentUpdateModal
          payment={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </>
  );
}
