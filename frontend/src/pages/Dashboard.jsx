import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Icon from '../components/Icon';
import RenewalList from '../components/RenewalList';
import { RevenueArea } from '../components/charts';
import { SubscriptionForm } from '../components/forms';
import { Button, Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge } from '../components/ui';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/hooks';
import { daysLabel, formatDate, money, timeAgo } from '../lib/format';

function Stat({ icon, label, value, children, to }) {
  const body = (
    <>
      <div className="stat-head">
        <Icon name={icon} size={18} className="muted-icon" />
        <span>{label}</span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-foot">{children}</div>
    </>
  );
  return to ? (
    <Link to={to} className="card stat stat-link">
      {body}
    </Link>
  ) : (
    <div className="card stat">{body}</div>
  );
}

function MoneyValue({ amount }) {
  const [whole, cents] = money(amount).replace('$', '').split('.');
  return (
    <>
      <span className="currency">$</span>
      {whole}
      <span className="cents">.{cents}</span>
    </>
  );
}

const STATUS_ROWS = [
  ['active', 'Active', 'green'],
  ['expiring_soon', 'Expiring soon', 'orange'],
  ['expired', 'Expired', 'red'],
  ['cancelled', 'Cancelled', 'gray'],
];

function StatusOverview({ counts }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  return (
    <div className="status-overview">
      <div className="stacked-bar" role="img" aria-label="Subscriptions by status">
        {STATUS_ROWS.map(([key, , tone]) =>
          counts[key] ? <span key={key} className={`seg seg-${tone}`} style={{ flexGrow: counts[key] }} /> : null,
        )}
      </div>
      <ul className="status-rows">
        {STATUS_ROWS.map(([key, label, tone]) => (
          <li key={key}>
            <Link to={`/subscriptions?status=${key}`}>
              <span className={`legend-dot dot-${tone}`} />
              <span>{label}</span>
              <strong>{counts[key]}</strong>
              <span className="muted pct">{Math.round((counts[key] / total) * 100)}%</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

const ACTIVITY_ICONS = {
  subscription_created: ['plus', 'accent'],
  renewal: ['refresh', 'green'],
  payment_paid: ['dollar', 'green'],
  payment_failed: ['alert', 'red'],
  cancelled: ['ban', 'gray'],
};

function Activity({ events }) {
  if (!events.length) return <EmptyState title="No activity yet" message="New subscriptions, renewals and payments will show here." />;
  return (
    <ul className="activity">
      {events.map((event, i) => {
        const [icon, tone] = ACTIVITY_ICONS[event.type] || ['bell', 'gray'];
        return (
          <li key={`${event.type}-${event.subscription_id}-${i}`}>
            <span className={`activity-icon tone-${tone}`}>
              <Icon name={icon} size={15} />
            </span>
            <Link to={`/subscriptions/${event.subscription_id}`} className="activity-text">
              <strong>{event.title}</strong>
              <span className="muted">
                {event.description} · {timeAgo(event.timestamp)}
              </span>
            </Link>
            {event.amount !== null && <span className="activity-amount">{money(event.amount)}</span>}
          </li>
        );
      })}
    </ul>
  );
}

function StaffDashboard({ data, reload }) {
  const { user, can } = useAuth();
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const { stats } = data;
  const change = stats.revenue_change_pct;

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle={`Welcome back, ${user.name.split(' ')[0]}!`}
        actions={
          can('manageSubscriptions') && (
            <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
              New subscription
            </Button>
          )
        }
      />

      <div className="stat-grid">
        <Stat icon="dollar" label="Monthly revenue" value={<MoneyValue amount={stats.monthly_revenue} />} to={can('viewReports') ? '/reports' : undefined}>
          {change === null ? (
            <span className="muted">Paid this month</span>
          ) : (
            <>
              <span className={change >= 0 ? 'trend-up' : 'trend-down'}>
                <Icon name={change >= 0 ? 'trendUp' : 'trendDown'} size={15} /> {Math.abs(change)}%
              </span>
              <span className="muted">vs. same period last month</span>
            </>
          )}
        </Stat>
        <Stat icon="card" label="Active subscriptions" value={stats.active_subscriptions} to="/subscriptions?status=current">
          <span className="muted">
            {stats.expired_subscriptions} expired · {stats.pending_payments} payments pending
          </span>
        </Stat>
        <Stat icon="refresh" label="Upcoming renewals" value={stats.upcoming_renewals} to="/renewals">
          {stats.overdue_renewals > 0 ? (
            <span className="text-red">{stats.overdue_renewals} overdue</span>
          ) : (
            <span className="muted">Next {data.renewal_window_days} days</span>
          )}
        </Stat>
        <Stat icon="users" label="Total customers" value={stats.total_customers} to={can('viewCustomers') ? '/customers' : undefined}>
          <span className="muted">{stats.active_customers} active accounts</span>
        </Stat>
      </div>

      <div className="grid-2-1">
        <Card title="Monthly revenue" subtitle="Paid payments, last 6 months" icon="chart">
          <RevenueArea data={data.revenue_chart} />
        </Card>
        <Card title="Subscription overview" subtitle="All subscriptions by status" icon="layers">
          <StatusOverview counts={data.status_overview} />
        </Card>
      </div>

      <div className="grid-2-1">
        <Card
          title="Upcoming renewals"
          subtitle="Manage subscriptions renewing soon"
          bodyClass="card-body-flush"
          actions={
            <Button size="sm" onClick={() => navigate('/renewals')}>
              View all
            </Button>
          }
        >
          {data.upcoming_renewals.length ? (
            <RenewalList items={data.upcoming_renewals} onChanged={reload} compact />
          ) : (
            <EmptyState icon="checkCircle" title="No renewals due" message={`Nothing expires in the next ${data.renewal_window_days} days.`} />
          )}
        </Card>
        <Card title="Recent activity" icon="clock">
          <Activity events={data.recent_activity} />
        </Card>
      </div>

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

function CustomerDashboard({ data, user }) {
  const { stats } = data;
  const next = stats.next_renewal;
  return (
    <>
      <PageHeader title="Overview" subtitle={`Welcome back, ${user.name.split(' ')[0]}!`} />
      <div className="stat-grid stat-grid-3">
        <Stat icon="card" label="Active subscriptions" value={stats.active_subscriptions} to="/subscriptions">
          <span className="muted">{stats.expired_subscriptions} expired</span>
        </Stat>
        <Stat icon="calendar" label="Next renewal" value={next ? formatDate(next.expiry_date) : '—'} to={next ? `/subscriptions/${next.id}` : undefined}>
          {next ? (
            <span className={`days days-${next.status}`}>
              {next.service_name} · {daysLabel(next.days_until_expiry)}
            </span>
          ) : (
            <span className="muted">No active subscriptions</span>
          )}
        </Stat>
        <Stat icon="wallet" label="Total paid" value={<MoneyValue amount={stats.total_paid} />} to="/payments">
          {stats.pending_amount > 0 ? (
            <span className="text-orange">{money(stats.pending_amount)} pending</span>
          ) : (
            <span className="muted">All payments settled</span>
          )}
        </Stat>
      </div>

      <div className="grid-2-1">
        <Card title="My subscriptions" bodyClass="card-body-flush">
          {data.subscriptions.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Expiry</th>
                    <th className="num">Amount</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.subscriptions.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <Link to={`/subscriptions/${s.id}`} className="cell-main">
                          <strong>{s.service_name}</strong>
                          <span className="muted">{s.code}</span>
                        </Link>
                      </td>
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
            <EmptyState title="No subscriptions yet" />
          )}
        </Card>
        <Card title="Recent payments" icon="receipt">
          {data.recent_payments.length ? (
            <ul className="mini-list">
              {data.recent_payments.map((p) => (
                <li key={p.id}>
                  <span>
                    <strong>{money(p.amount)}</strong>
                    <small className="muted">
                      {p.subscription.service_name} · {formatDate(p.paid_on || p.due_date)}
                    </small>
                  </span>
                  <StatusBadge status={p.status} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No payments yet" />
          )}
        </Card>
      </div>
    </>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi('/dashboard');
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  return data.role === 'customer' ? <CustomerDashboard data={data} user={user} /> : <StaffDashboard data={data} reload={reload} />;
}
