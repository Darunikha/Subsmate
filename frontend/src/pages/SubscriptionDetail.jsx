import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Icon from '../components/Icon';
import { CancelModal, PaymentForm, PaymentUpdateModal, RenewModal, SubscriptionForm } from '../components/forms';
import { Button, Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge } from '../components/ui';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/hooks';
import { CYCLE_LABELS, daysLabel, formatDate, money, METHOD_LABELS } from '../lib/format';
import { BackLink } from './CustomerDetail';

export default function SubscriptionDetail() {
  const { id } = useParams();
  const { user, can } = useAuth();
  const { data: s, error, loading, reload } = useApi(`/subscriptions/${id}`);
  const [modal, setModal] = useState(null);
  const [editingPayment, setEditingPayment] = useState(null);

  if (loading && !s) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const close = () => setModal(null);
  const saved = () => {
    setModal(null);
    setEditingPayment(null);
    reload();
  };
  const live = s.status !== 'cancelled';
  const isCustomer = user.role === 'customer';

  return (
    <>
      <PageHeader
        back={<BackLink to="/subscriptions" label={isCustomer ? 'My Subscriptions' : 'Subscriptions'} />}
        title={
          <span className="title-with-badge">
            {s.plan.name} <StatusBadge status={s.status} />
          </span>
        }
        subtitle={`${s.code} · ${s.customer.full_name}`}
        actions={
          live && (
            <>
              {can('managePayments') && (
                <Button icon="receipt" onClick={() => setModal('payment')}>
                  Record payment
                </Button>
              )}
              {can('manageSubscriptions') && (
                <>
                  <Button icon="edit" onClick={() => setModal('edit')}>
                    Edit
                  </Button>
                  <Button icon="ban" variant="ghost-danger" onClick={() => setModal('cancel')}>
                    Cancel
                  </Button>
                </>
              )}
              {can('renewSubscriptions') && (
                <Button variant="primary" icon="refresh" onClick={() => setModal('renew')}>
                  Renew
                </Button>
              )}
            </>
          )
        }
      />

      {s.status === 'expired' && (
        <div className="alert alert-red">
          <Icon name="alert" size={18} /> This subscription expired on {formatDate(s.expiry_date)}.
          {can('renewSubscriptions') && ' Renew it to start a new billing period from today.'}
        </div>
      )}
      {s.status === 'expiring_soon' && (
        <div className="alert alert-orange">
          <Icon name="clock" size={18} /> {daysLabel(s.days_until_expiry)} — renewal due {formatDate(s.expiry_date)}.
        </div>
      )}
      {s.status === 'cancelled' && (
        <div className="alert alert-gray">
          <Icon name="ban" size={18} /> Cancelled on {formatDate(s.cancelled_at)}
          {s.cancellation_reason ? ` — ${s.cancellation_reason}` : ''}.
        </div>
      )}

      <div className="summary-grid card">
        <div>
          <span>Customer</span>
          {isCustomer ? <strong>{s.customer.full_name}</strong> : <Link to={`/customers/${s.customer.id}`}>{s.customer.full_name}</Link>}
        </div>
        <div>
          <span>Billing cycle</span>
          <strong>{CYCLE_LABELS[s.plan.billing_cycle]}</strong>
        </div>
        <div>
          <span>Amount</span>
          <strong>{money(s.amount)}</strong>
        </div>
        <div>
          <span>Start date</span>
          <strong>{formatDate(s.start_date)}</strong>
        </div>
        <div>
          <span>Expiry date</span>
          <strong>{formatDate(s.expiry_date)}</strong>
          {live && <span className={`days days-${s.status}`}>{daysLabel(s.days_until_expiry)}</span>}
        </div>
        <div>
          <span>Payment status</span>
          <StatusBadge status={s.payment_status} />
        </div>
      </div>
      {s.notes && (
        <p className="notes">
          <Icon name="edit" size={14} /> {s.notes}
        </p>
      )}

      <div className="grid-2-1">
        <Card title="Payments" subtitle="All payments for this subscription" bodyClass="card-body-flush">
          {s.payments.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Payment</th>
                    <th>Due</th>
                    <th className="hide-sm">Paid on</th>
                    <th className="hide-sm">Method</th>
                    <th className="num">Amount</th>
                    <th>Status</th>
                    {can('managePayments') && <th className="actions-col" aria-label="Actions" />}
                  </tr>
                </thead>
                <tbody>
                  {s.payments.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <div className="cell-main">
                          <strong>{p.code}</strong>
                          {p.reference && <span className="muted">{p.reference}</span>}
                        </div>
                      </td>
                      <td>
                        {formatDate(p.due_date)}
                        {p.is_overdue && <span className="days days-expired"> · overdue</span>}
                      </td>
                      <td className="hide-sm">{p.paid_on ? formatDate(p.paid_on) : '—'}</td>
                      <td className="hide-sm">{METHOD_LABELS[p.method] || '—'}</td>
                      <td className="num">{money(p.amount)}</td>
                      <td>
                        <StatusBadge status={p.status} />
                      </td>
                      {can('managePayments') && (
                        <td className="actions-col">
                          <Button size="sm" onClick={() => setEditingPayment({ ...p, subscription: { customer: s.customer, plan: s.plan } })}>
                            Update
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon="wallet" title="No payments yet" />
          )}
        </Card>

        <Card title="Renewal history" icon="refresh">
          {s.renewals.length ? (
            <ol className="timeline">
              {s.renewals.map((r) => (
                <li key={r.id}>
                  <span className="timeline-dot" />
                  <div>
                    <strong>
                      {formatDate(r.previous_expiry_date)} → {formatDate(r.new_expiry_date)}
                    </strong>
                    <span className="muted">
                      {r.plan.name} · {money(r.amount)}
                      {r.payment_status && ` · ${r.payment_status}`}
                    </span>
                    <span className="muted small">
                      Renewed {formatDate(r.renewed_at)}
                      {r.renewed_by && ` by ${r.renewed_by}`}
                    </span>
                  </div>
                </li>
              ))}
              <li>
                <span className="timeline-dot timeline-dot-start" />
                <div>
                  <strong>Started {formatDate(s.start_date)}</strong>
                  <span className="muted small">Subscription created</span>
                </div>
              </li>
            </ol>
          ) : (
            <EmptyState icon="refresh" title="Not renewed yet" message={`First period started ${formatDate(s.start_date)}.`} />
          )}
        </Card>
      </div>

      {modal === 'renew' && <RenewModal subscription={s} onClose={close} onSaved={saved} />}
      {modal === 'cancel' && <CancelModal subscription={s} onClose={close} onSaved={saved} />}
      {modal === 'edit' && <SubscriptionForm subscription={s} onClose={close} onSaved={saved} />}
      {modal === 'payment' && <PaymentForm subscription={s} onClose={close} onSaved={saved} />}
      {editingPayment && <PaymentUpdateModal payment={editingPayment} onClose={() => setEditingPayment(null)} onSaved={saved} />}
    </>
  );
}
