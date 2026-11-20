import { useState } from 'react';
import { Link } from 'react-router-dom';
import { HorizontalBars, RevenueBars, TrendLines } from '../components/charts';
import { Button, Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge, useToast } from '../components/ui';
import { api } from '../lib/api';
import { useApi } from '../lib/hooks';
import { CYCLE_LABELS, formatDate, money, todayISO } from '../lib/format';

function isoMonthsAgo(months) {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - months + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
}

const PRESETS = [
  { label: '3 months', from: () => isoMonthsAgo(3) },
  { label: '6 months', from: () => isoMonthsAgo(6) },
  { label: '12 months', from: () => isoMonthsAgo(12) },
  { label: 'Year to date', from: () => `${new Date().getFullYear()}-01-01` },
];

function ExportButton({ report, range, label = 'CSV' }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await api.download(`/reports/export/${report}`, range, `${report}.csv`);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button size="sm" icon="download" loading={busy} onClick={run}>
      {label}
    </Button>
  );
}

function Kpi({ label, value, note, tone }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <strong className={`kpi-value ${tone ? `text-${tone}` : ''}`}>{value}</strong>
      {note && <span className="muted small">{note}</span>}
    </div>
  );
}

export default function Reports() {
  const [range, setRange] = useState({ from: isoMonthsAgo(12), to: todayISO() });
  const [preset, setPreset] = useState('12 months');
  const { data, error, loading, reload } = useApi('/reports/summary', range);

  const applyPreset = (p) => {
    setPreset(p.label);
    setRange({ from: p.from(), to: todayISO() });
  };
  const setDate = (key) => (e) => {
    setPreset('');
    setRange((r) => ({ ...r, [key]: e.target.value }));
  };

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Revenue, renewals and plan performance from recorded data."
        actions={<ExportButton report="subscriptions" range={range} label="Export subscriptions" />}
      />

      <div className="filter-bar card">
        <div className="segmented segmented-plain">
          {PRESETS.map((p) => (
            <button key={p.label} type="button" className={`segment ${preset === p.label ? 'segment-active' : ''}`} onClick={() => applyPreset(p)}>
              {p.label}
            </button>
          ))}
        </div>
        <div className="toolbar-right">
          <label className="date-filter">
            <span>From</span>
            <input type="date" value={range.from} max={range.to} onChange={setDate('from')} />
          </label>
          <label className="date-filter">
            <span>To</span>
            <input type="date" value={range.to} min={range.from} onChange={setDate('to')} />
          </label>
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <Spinner />
      ) : (
        <div className={`stack ${loading ? 'is-refreshing' : ''}`}>
          <div className="kpi-grid">
            <Kpi label="Revenue in range" value={money(data.totals.revenue)} note="Paid payments only" />
            <Kpi label="Active subscriptions" value={data.totals.active_subscriptions} note={`${data.totals.expiring_soon} expiring soon`} />
            <Kpi label="Expired subscriptions" value={data.totals.expired_subscriptions} tone={data.totals.expired_subscriptions ? 'red' : undefined} note={`${data.totals.cancelled_subscriptions} cancelled`} />
            <Kpi label="Pending payments" value={money(data.totals.pending_amount)} tone={data.totals.pending_count ? 'orange' : undefined} note={`${data.totals.pending_count} pending · ${data.totals.overdue_count} overdue`} />
          </div>

          <div className="grid-1-1">
            <Card title="Monthly revenue" subtitle="Paid payments by month" actions={<ExportButton report="revenue" range={range} />}>
              <RevenueBars data={data.monthly_revenue} />
            </Card>
            <Card title="Renewal trends" subtitle="New subscriptions, renewals and cancellations per month" actions={<ExportButton report="renewals" range={range} />}>
              <TrendLines data={data.renewal_trends} />
            </Card>
          </div>

          <div className="grid-1-1">
            <Card title="Plan popularity" subtitle="Active subscriptions per plan" actions={<ExportButton report="plans" range={range} />}>
              <HorizontalBars data={data.plan_popularity} dataKey="active" labelKey="plan" name="Active subscriptions" />
              <div className="table-wrap">
                <table className="table table-compact">
                  <thead>
                    <tr>
                      <th>Plan</th>
                      <th className="num">Active</th>
                      <th className="num">Total</th>
                      <th className="num">Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.plan_popularity.map((p) => (
                      <tr key={p.plan_id}>
                        <td>
                          {p.plan} <span className="muted small">· {CYCLE_LABELS[p.billing_cycle]}</span>
                        </td>
                        <td className="num">{p.active}</td>
                        <td className="num">{p.subscriptions}</td>
                        <td className="num">{money(p.revenue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card title="Customer distribution" subtitle="Customers by number of active subscriptions" actions={<ExportButton report="customers" range={range} />}>
              <HorizontalBars data={data.customer_distribution} dataKey="customers" labelKey="label" name="Customers" />
            </Card>
          </div>

          <Card
            title="Pending & failed payments"
            subtitle="Outstanding payments to follow up"
            bodyClass="card-body-flush"
            actions={
              <>
                <ExportButton report="pending-payments" range={range} label="Pending CSV" />
                <ExportButton report="payments" range={range} label="All payments CSV" />
              </>
            }
          >
            {data.pending_payments.length ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Payment</th>
                      <th>Customer</th>
                      <th className="hide-sm">Plan</th>
                      <th>Due</th>
                      <th className="num">Amount</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.pending_payments.map((p) => (
                      <tr key={p.id}>
                        <td>{p.code}</td>
                        <td>
                          <Link to={`/subscriptions/${p.subscription.id}`}>{p.subscription.customer.full_name}</Link>
                        </td>
                        <td className="hide-sm">{p.subscription.plan.name}</td>
                        <td>
                          {formatDate(p.due_date)}
                          {p.is_overdue && <span className="days days-expired"> · overdue</span>}
                        </td>
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
              <EmptyState icon="checkCircle" title="No outstanding payments" />
            )}
          </Card>
        </div>
      )}
    </>
  );
}
