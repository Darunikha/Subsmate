import { useState } from 'react';
import Icon from '../components/Icon';
import { PlanForm } from '../components/forms';
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  IconButton,
  PageHeader,
  Spinner,
  StatusBadge,
  Tabs,
  useToast,
} from '../components/ui';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { useApi } from '../lib/hooks';
import { CYCLE_LABELS, CYCLE_SHORT, money } from '../lib/format';

export default function Plans() {
  const { can } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState('');
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const { data, error, loading, reload } = useApi('/plans', { status });
  const manage = can('managePlans');

  return (
    <>
      <PageHeader
        title="Subscription Plans"
        subtitle="Plans define the price and billing cycle used to calculate expiry dates."
        actions={
          manage && (
            <Button variant="primary" icon="plus" onClick={() => setEditing('new')}>
              New plan
            </Button>
          )
        }
      />
      <div className="toolbar toolbar-plain">
        <Tabs
          value={status}
          onChange={setStatus}
          tabs={[
            { value: '', label: 'All plans' },
            { value: 'active', label: 'Active' },
            { value: 'inactive', label: 'Inactive' },
          ]}
        />
      </div>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <Spinner />
      ) : data.items.length === 0 ? (
        <EmptyState icon="layers" title="No plans" message={manage ? 'Create a plan to start selling subscriptions.' : undefined} />
      ) : (
        <div className="plan-grid">
          {data.items.map((plan) => (
            <article key={plan.id} className={`card plan-card ${plan.status === 'inactive' ? 'plan-inactive' : ''}`}>
              <header className="plan-head">
                <div>
                  <h3>{plan.name}</h3>
                  <span className="muted">{CYCLE_LABELS[plan.billing_cycle]} billing</span>
                </div>
                <StatusBadge status={plan.status} />
              </header>
              <div className="plan-price">
                {money(plan.price)}
                <span>/ {CYCLE_SHORT[plan.billing_cycle]}</span>
              </div>
              {plan.description && <p className="plan-desc">{plan.description}</p>}
              {plan.features.length > 0 && (
                <ul className="plan-features">
                  {plan.features.map((f) => (
                    <li key={f}>
                      <Icon name="check" size={15} /> {f}
                    </li>
                  ))}
                </ul>
              )}
              <footer className="plan-foot">
                <span>
                  <strong>{plan.subscriber_count}</strong> active subscriber{plan.subscriber_count === 1 ? '' : 's'}
                </span>
                {manage && (
                  <div className="row-actions">
                    <IconButton icon="edit" label="Edit plan" onClick={() => setEditing(plan)} />
                    <IconButton icon="trash" label="Delete plan" tone="danger" onClick={() => setDeleting(plan)} />
                  </div>
                )}
              </footer>
            </article>
          ))}
        </div>
      )}

      {editing && (
        <PlanForm
          plan={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.name}?`}
          message={
            deleting.total_subscriptions
              ? `This plan has ${deleting.total_subscriptions} subscription(s), so it can't be deleted. Mark it inactive to stop new sign-ups.`
              : 'This plan has never been used and will be permanently deleted.'
          }
          confirmLabel={deleting.total_subscriptions ? 'Mark inactive' : 'Delete plan'}
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            if (deleting.total_subscriptions) {
              await api.put(`/plans/${deleting.id}`, { status: 'inactive' });
              toast.success('Plan marked inactive.');
            } else {
              await api.del(`/plans/${deleting.id}`);
              toast.success('Plan deleted.');
            }
            reload();
          }}
        />
      )}
    </>
  );
}
