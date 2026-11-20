import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import Icon from '../components/Icon';
import { CustomerForm, SubscriptionForm } from '../components/forms';
import { Avatar, Button, Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge } from '../components/ui';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/hooks';
import { formatDate, money, METHOD_LABELS } from '../lib/format';

export function BackLink({ to, label }) {
  return (
    <Link to={to} className="back-link">
      <Icon name="arrowLeft" size={15} /> {label}
    </Link>
  );
}

export default function CustomerDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi(`/customers/${id}`);
  const [editing, setEditing] = useState(false);
  const [subscribing, setSubscribing] = useState(false);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  const c = data;

  return (
    <>
      <PageHeader
        back={<BackLink to="/customers" label="Customers" />}
        title={c.full_name}
        subtitle={`${c.code} · Customer since ${formatDate(c.registration_date)}`}
        actions={
          can('manageCustomers') && (
            <>
              <Button icon="edit" onClick={() => setEditing(true)}>
                Edit
              </Button>
              {c.status === 'active' && (
                <Button variant="primary" icon="plus" onClick={() => setSubscribing(true)}>
                  New subscription
                </Button>
              )}
            </>
          )
        }
      />

      <div className="grid-1-2">
        <Card title="Profile" icon="user">
          <div className="profile-card">
            <Avatar name={c.full_name} size="lg" />
            <StatusBadge status={c.status} />
          </div>
          <dl className="detail-list">
            <div>
              <dt>
                <Icon name="mail" size={15} /> Email
              </dt>
              <dd>{c.email}</dd>
            </div>
            <div>
              <dt>
                <Icon name="phone" size={15} /> Phone
              </dt>
              <dd>{c.phone || '—'}</dd>
            </div>
            <div>
              <dt>
                <Icon name="lock" size={15} /> Portal login
              </dt>
              <dd>{c.has_login ? 'Enabled' : 'Not set up'}</dd>
            </div>
            <div>
              <dt>
                <Icon name="wallet" size={15} /> Total paid
              </dt>
              <dd>{money(c.total_paid)}</dd>
            </div>
            <div>
              <dt>
                <Icon name="clock" size={15} /> Pending
              </dt>
              <dd className={c.pending_amount ? 'text-orange' : ''}>{money(c.pending_amount)}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Subscription history" subtitle={`${c.active_subscription_count} active of ${c.subscription_count}`} bodyClass="card-body-flush">
          {c.subscriptions.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Plan</th>
                    <th className="hide-sm">Start</th>
                    <th>Expiry</th>
                    <th className="num">Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {c.subscriptions.map((s) => (
                    <tr key={s.id} className="row-link" onClick={() => navigate(`/subscriptions/${s.id}`)}>
                      <td>
                        <div className="cell-main">
                          <strong>{s.plan.name}</strong>
                          <span className="muted">
                            {s.code} · {s.renewal_count} renewal{s.renewal_count === 1 ? '' : 's'}
                          </span>
                        </div>
                      </td>
                      <td className="hide-sm">{formatDate(s.start_date)}</td>
                      <td>{formatDate(s.expiry_date)}</td>
                      <td className="num">{money(s.amount)}</td>
                      <td>
                        <StatusBadge status={s.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon="card" title="No subscriptions" message="This customer has not subscribed to a plan yet." />
          )}
        </Card>
      </div>

      <Card title="Payment history" bodyClass="card-body-flush">
        {c.payments.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Payment</th>
                  <th>Plan</th>
                  <th className="hide-sm">Due</th>
                  <th className="hide-sm">Paid on</th>
                  <th className="hide-sm">Method</th>
                  <th className="num">Amount</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {c.payments.map((p) => (
                  <tr key={p.id}>
                    <td>{p.code}</td>
                    <td>{p.subscription.plan.name}</td>
                    <td className="hide-sm">{formatDate(p.due_date)}</td>
                    <td className="hide-sm">{p.paid_on ? formatDate(p.paid_on) : '—'}</td>
                    <td className="hide-sm">{METHOD_LABELS[p.method] || '—'}</td>
                    <td className="num">{money(p.amount)}</td>
                    <td>
                      <StatusBadge status={p.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="wallet" title="No payments recorded" />
        )}
      </Card>

      {editing && (
        <CustomerForm
          customer={c}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            reload();
          }}
        />
      )}
      {subscribing && (
        <SubscriptionForm
          customerId={c.id}
          onClose={() => setSubscribing(false)}
          onSaved={() => {
            setSubscribing(false);
            reload();
          }}
        />
      )}
    </>
  );
}
