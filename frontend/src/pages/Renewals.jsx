import { useState } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../components/Icon';
import RenewalList from '../components/RenewalList';
import { Card, EmptyState, ErrorState, PageHeader, Pager, Spinner, StatusBadge, Tabs } from '../components/ui';
import { useApi } from '../lib/hooks';
import { formatDate, money } from '../lib/format';

const WINDOWS = [7, 14, 30, 60, 90];

function Upcoming() {
  const [days, setDays] = useState(30);
  const { data, error, loading, reload } = useApi('/renewals/upcoming', { days });

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Spinner />;

  const soon = data.upcoming.filter((s) => s.status === 'expiring_soon');
  const later = data.upcoming.filter((s) => s.status !== 'expiring_soon');

  return (
    <>
      <div className="indicator-row">
        <div className="indicator indicator-red">
          <Icon name="alert" size={18} />
          <div>
            <strong>{data.counts.overdue}</strong>
            <span>Expired · renewal overdue</span>
          </div>
        </div>
        <div className="indicator indicator-orange">
          <Icon name="clock" size={18} />
          <div>
            <strong>{data.counts.expiring_soon}</strong>
            <span>Expiring within 7 days</span>
          </div>
        </div>
        <div className="indicator indicator-green">
          <Icon name="checkCircle" size={18} />
          <div>
            <strong>{data.counts.upcoming - data.counts.expiring_soon}</strong>
            <span>Renewing later in window</span>
          </div>
        </div>
        <label className="window-select">
          <span>Show next</span>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {WINDOWS.map((w) => (
              <option key={w} value={w}>
                {w} days
              </option>
            ))}
          </select>
        </label>
      </div>

      {data.overdue.length + data.upcoming.length === 0 && (
        <Card>
          <EmptyState icon="checkCircle" title="Nothing to renew" message={`No subscriptions expire in the next ${days} days.`} />
        </Card>
      )}
      {data.overdue.length > 0 && (
        <Card title="Overdue" subtitle="Expired subscriptions that have not been renewed or cancelled" bodyClass="card-body-flush">
          <RenewalList items={data.overdue} onChanged={reload} />
        </Card>
      )}
      {soon.length > 0 && (
        <Card title="Expiring soon" subtitle="Due within 7 days" bodyClass="card-body-flush">
          <RenewalList items={soon} onChanged={reload} />
        </Card>
      )}
      {later.length > 0 && (
        <Card title="Upcoming" subtitle={`Due within ${days} days`} bodyClass="card-body-flush">
          <RenewalList items={later} onChanged={reload} />
        </Card>
      )}
    </>
  );
}

function History() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi('/renewals/history', { page });
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Spinner />;
  return (
    <Card bodyClass="card-body-flush">
      {data.items.length === 0 ? (
        <EmptyState icon="refresh" title="No renewals yet" />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Renewed</th>
                <th>Subscription</th>
                <th className="hide-sm">Previous expiry</th>
                <th>New expiry</th>
                <th className="num">Amount</th>
                <th className="hide-sm">Payment</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div className="cell-main">
                      <span>{formatDate(r.renewed_at)}</span>
                      {r.renewed_by && <span className="muted">by {r.renewed_by}</span>}
                    </div>
                  </td>
                  <td>
                    <Link to={`/subscriptions/${r.subscription.id}`} className="cell-main">
                      <strong>{r.subscription.customer.full_name}</strong>
                      <span className="muted">
                        {r.subscription.code} · {r.plan.name}
                      </span>
                    </Link>
                  </td>
                  <td className="hide-sm">{formatDate(r.previous_expiry_date)}</td>
                  <td>{formatDate(r.new_expiry_date)}</td>
                  <td className="num">{money(r.amount)}</td>
                  <td className="hide-sm">{r.payment_status ? <StatusBadge status={r.payment_status} /> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pager page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
    </Card>
  );
}

export default function Renewals() {
  const [tab, setTab] = useState('upcoming');
  return (
    <>
      <PageHeader title="Renewals" subtitle="Stay ahead of expiring subscriptions and keep a full renewal record." />
      <div className="toolbar toolbar-plain">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: 'upcoming', label: 'Upcoming & overdue' },
            { value: 'history', label: 'Renewal history' },
          ]}
        />
      </div>
      <div className="stack">{tab === 'upcoming' ? <Upcoming /> : <History />}</div>
    </>
  );
}
