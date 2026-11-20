import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { useForm } from '../lib/hooks';
import { CYCLE_LABELS, METHOD_LABELS, calculateExpiry, formatDate, money, todayISO } from '../lib/format';
import { Button, Field, Modal, useToast } from './ui';

function FormError({ message }) {
  return message ? <div className="form-error">{message}</div> : null;
}

function PaymentFields({ form, prefix = 'payment_', showStatusHint }) {
  const { values, set } = form;
  return (
    <>
      <Field label="Payment status" hint={showStatusHint ? 'You can update this later on the Payments page.' : undefined}>
        <select value={values[`${prefix}status`]} onChange={set(`${prefix}status`)}>
          <option value="pending">Pending</option>
          <option value="paid">Paid</option>
          <option value="failed">Failed</option>
        </select>
      </Field>
      <Field label="Payment method">
        <select value={values[`${prefix}method`]} onChange={set(`${prefix}method`)}>
          <option value="">Not specified</option>
          {Object.entries(METHOD_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}

/* ------------------------------------------------------------------ customer */
export function CustomerForm({ customer, onClose, onSaved }) {
  const toast = useToast();
  const form = useForm({
    full_name: customer?.full_name || '',
    email: customer?.email || '',
    phone: customer?.phone || '',
    status: customer?.status || 'active',
    registration_date: customer?.registration_date || todayISO(),
    create_login: false,
    password: '',
  });
  const { values, set, errors } = form;

  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const body = { ...v };
      if (!body.create_login) delete body.password;
      const saved = customer ? await api.put(`/customers/${customer.id}`, body) : await api.post('/customers', body);
      toast.success(customer ? 'Customer updated.' : 'Customer registered.');
      onSaved(saved);
      return true;
    });
  };

  return (
    <Modal
      title={customer ? 'Edit customer' : 'Register customer'}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="customer-form" loading={form.submitting}>
            {customer ? 'Save changes' : 'Register customer'}
          </Button>
        </>
      }
    >
      <form id="customer-form" className="form-grid" onSubmit={save} noValidate>
        <FormError message={form.formError} />
        <Field label="Full name" error={errors.full_name} full>
          <input value={values.full_name} onChange={set('full_name')} required maxLength={150} />
        </Field>
        <Field label="Email address" error={errors.email}>
          <input type="email" value={values.email} onChange={set('email')} required />
        </Field>
        <Field label="Phone number" error={errors.phone}>
          <input type="tel" value={values.phone} onChange={set('phone')} placeholder="+1 555 0100" />
        </Field>
        <Field label="Registration date" error={errors.registration_date}>
          <input type="date" value={values.registration_date} max={todayISO()} onChange={set('registration_date')} />
        </Field>
        <Field label="Account status" error={errors.status}>
          <select value={values.status} onChange={set('status')}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </Field>
        {!customer?.has_login && (
          <>
            <label className="checkbox field-full">
              <input type="checkbox" checked={values.create_login} onChange={set('create_login')} />
              <span>
                Create a customer portal login
                <small>The customer can sign in to view their subscriptions and payments.</small>
              </span>
            </label>
            {values.create_login && (
              <Field label="Initial password" error={errors.password} hint="At least 8 characters." full>
                <input type="password" value={values.password} onChange={set('password')} autoComplete="new-password" />
              </Field>
            )}
          </>
        )}
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ subscription */
export function SubscriptionForm({ subscription, customerId, onClose, onSaved }) {
  const toast = useToast();
  const [customers, setCustomers] = useState([]);
  const editing = Boolean(subscription);
  const form = useForm({
    customer_id: subscription?.customer.id || customerId || '',
    service_name: subscription?.service_name || '',
    billing_cycle: subscription?.billing_cycle || 'monthly',
    start_date: subscription?.start_date || todayISO(),
    amount: subscription?.amount ?? '',
    notes: subscription?.notes || '',
    payment_status: 'pending',
    payment_method: '',
    payment_reference: '',
  });
  const { values, set, errors } = form;

  useEffect(() => {
    if (editing) return;
    api
      .get('/customers', { status: 'active', per_page: 100 })
      .then((d) => setCustomers(d.items))
      .catch(() => {});
  }, [editing]);

  const expiry = calculateExpiry(values.start_date, values.billing_cycle);
  const locked = editing && subscription.renewal_count > 0;

  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      let saved;
      if (editing) {
        const body = { service_name: v.service_name, amount: v.amount, notes: v.notes };
        if (!locked) Object.assign(body, { billing_cycle: v.billing_cycle, start_date: v.start_date });
        saved = await api.put(`/subscriptions/${subscription.id}`, body);
        toast.success('Subscription updated.');
      } else {
        saved = await api.post('/subscriptions', {
          customer_id: v.customer_id,
          service_name: v.service_name,
          billing_cycle: v.billing_cycle,
          start_date: v.start_date,
          amount: v.amount,
          notes: v.notes,
          payment: { status: v.payment_status, method: v.payment_method, reference: v.payment_reference },
        });
        toast.success(`Subscription ${saved.code} created.`);
      }
      onSaved(saved);
      return true;
    });
  };

  return (
    <Modal
      title={editing ? `Edit ${subscription.code}` : 'New subscription'}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="subscription-form" loading={form.submitting}>
            {editing ? 'Save changes' : 'Create subscription'}
          </Button>
        </>
      }
    >
      <form id="subscription-form" className="form-grid" onSubmit={save} noValidate>
        <FormError message={form.formError} />
        {!editing && (
          <Field label="Customer" error={errors.customer_id} full>
            <select value={values.customer_id} onChange={set('customer_id')}>
              <option value="">Select a customer…</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.full_name} — {c.email}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Service name" error={errors.service_name} hint="What the customer is subscribing to, e.g. Monthly gym pass." full>
          <input value={values.service_name} onChange={set('service_name')} maxLength={120} placeholder="Monthly gym pass" />
        </Field>
        <Field
          label="Billing cycle"
          error={errors.billing_cycle}
          hint={locked ? 'Locked after a renewal. Change it when renewing.' : undefined}
        >
          <select value={values.billing_cycle} onChange={set('billing_cycle')} disabled={locked}>
            {Object.entries(CYCLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Amount (USD)" error={errors.amount}>
          <input type="number" min="0" step="0.01" value={values.amount} onChange={set('amount')} />
        </Field>
        <Field label="Start date" error={errors.start_date}>
          <input type="date" value={values.start_date} onChange={set('start_date')} disabled={locked} />
        </Field>
        {expiry && !locked && (
          <div className="info-strip" style={{ alignSelf: 'end' }}>
            <span>Expires</span>
            <strong>{formatDate(expiry)}</strong>
          </div>
        )}
        {!editing && (
          <>
            <PaymentFields form={form} showStatusHint />
            <Field label="Payment reference" error={errors.reference} full>
              <input value={values.payment_reference} onChange={set('payment_reference')} placeholder="Optional" />
            </Field>
          </>
        )}
        <Field label="Notes" error={errors.notes} full>
          <textarea rows={2} value={values.notes} onChange={set('notes')} />
        </Field>
      </form>
    </Modal>
  );
}

export function RenewModal({ subscription, onClose, onSaved }) {
  const toast = useToast();
  const form = useForm({
    billing_cycle: subscription.billing_cycle,
    amount: subscription.amount,
    payment_status: 'pending',
    payment_method: '',
    payment_reference: '',
    notes: '',
  });
  const { values, set, errors } = form;
  const today = todayISO();
  const periodStart = subscription.expiry_date >= today ? subscription.expiry_date : today;
  const newExpiry = calculateExpiry(periodStart, values.billing_cycle);

  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const result = await api.post(`/subscriptions/${subscription.id}/renew`, {
        billing_cycle: v.billing_cycle,
        amount: v.amount,
        notes: v.notes,
        payment: { status: v.payment_status, method: v.payment_method, reference: v.payment_reference },
      });
      toast.success(`${subscription.code} renewed until ${formatDate(result.subscription.expiry_date)}.`);
      onSaved(result.subscription);
      return true;
    });
  };

  return (
    <Modal
      title={`Renew ${subscription.code}`}
      subtitle={`${subscription.customer.full_name} · ${subscription.service_name} · expires ${formatDate(subscription.expiry_date)}`}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="renew-form" loading={form.submitting} icon="refresh">
            Renew subscription
          </Button>
        </>
      }
    >
      <form id="renew-form" className="form-grid" onSubmit={save} noValidate>
        <FormError message={form.formError} />
        <Field label="Billing cycle" error={errors.billing_cycle}>
          <select value={values.billing_cycle} onChange={set('billing_cycle')}>
            {Object.entries(CYCLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Amount (USD)" error={errors.amount}>
          <input type="number" min="0" step="0.01" value={values.amount} onChange={set('amount')} />
        </Field>
        <div className="renew-preview field-full">
          <div>
            <span>New period starts</span>
            <strong>{formatDate(periodStart)}</strong>
          </div>
          <div>
            <span>New expiry date</span>
            <strong>{formatDate(newExpiry)}</strong>
          </div>
        </div>
        <PaymentFields form={form} />
        <Field label="Payment reference" full>
          <input value={values.payment_reference} onChange={set('payment_reference')} placeholder="Optional" />
        </Field>
        <Field label="Notes" full>
          <textarea rows={2} value={values.notes} onChange={set('notes')} />
        </Field>
        <p className="field-hint field-full">
          A renewal history entry and a payment record are created. Earlier payments and renewals are kept.
        </p>
      </form>
    </Modal>
  );
}

export function CancelModal({ subscription, onClose, onSaved }) {
  const toast = useToast();
  const form = useForm({ reason: '' });
  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const saved = await api.post(`/subscriptions/${subscription.id}/cancel`, v);
      toast.success(`${subscription.code} cancelled.`);
      onSaved(saved);
      return true;
    });
  };
  return (
    <Modal
      title={`Cancel ${subscription.code}?`}
      size="sm"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Keep subscription</Button>
          <Button variant="danger" type="submit" form="cancel-form" loading={form.submitting}>
            Cancel subscription
          </Button>
        </>
      }
    >
      <form id="cancel-form" className="form-grid" onSubmit={save}>
        <FormError message={form.formError} />
        <p className="confirm-message field-full">
          {subscription.customer.full_name}'s {subscription.service_name} subscription will stop renewing. Its payment and
          renewal history is kept.
        </p>
        <Field label="Reason (optional)" full>
          <input value={form.values.reason} onChange={form.set('reason')} maxLength={255} />
        </Field>
      </form>
    </Modal>
  );
}

/* ------------------------------------------------------------------ payments */
export function PaymentForm({ subscription, onClose, onSaved }) {
  const toast = useToast();
  const [subs, setSubs] = useState([]);
  const form = useForm({
    subscription_id: subscription?.id || '',
    amount: subscription?.amount ?? '',
    status: 'paid',
    method: '',
    paid_on: todayISO(),
    due_date: todayISO(),
    reference: '',
    notes: '',
  });
  const { values, set, errors, setValues } = form;

  useEffect(() => {
    if (subscription) return;
    api
      .get('/subscriptions', { per_page: 100, sort: 'expiry', status: 'current' })
      .then((d) => setSubs(d.items))
      .catch(() => {});
  }, [subscription]);

  const chooseSub = (event) => {
    const chosen = subs.find((s) => String(s.id) === event.target.value);
    setValues((v) => ({ ...v, subscription_id: event.target.value, amount: chosen ? chosen.amount : v.amount }));
  };

  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const body = { ...v };
      if (body.status !== 'paid') delete body.paid_on;
      const saved = await api.post('/payments', body);
      toast.success(`Payment ${saved.code} recorded.`);
      onSaved(saved);
      return true;
    });
  };

  return (
    <Modal
      title="Record payment"
      subtitle={subscription ? `${subscription.code} · ${subscription.customer.full_name}` : undefined}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="payment-form" loading={form.submitting}>
            Record payment
          </Button>
        </>
      }
    >
      <form id="payment-form" className="form-grid" onSubmit={save} noValidate>
        <FormError message={form.formError} />
        {!subscription && (
          <Field label="Subscription" error={errors.subscription_id} full>
            <select value={values.subscription_id} onChange={chooseSub}>
              <option value="">Select a subscription…</option>
              {subs.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} · {s.customer.full_name} — {s.service_name}
                </option>
              ))}
            </select>
          </Field>
        )}
        <Field label="Amount (USD)" error={errors.amount}>
          <input type="number" min="0.01" step="0.01" value={values.amount} onChange={set('amount')} />
        </Field>
        <Field label="Status" error={errors.status}>
          <select value={values.status} onChange={set('status')}>
            <option value="paid">Paid</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
        </Field>
        <Field label="Method" error={errors.method}>
          <select value={values.method} onChange={set('method')}>
            <option value="">Not specified</option>
            {Object.entries(METHOD_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {values.status === 'paid' ? (
          <Field label="Paid on" error={errors.paid_on}>
            <input type="date" max={todayISO()} value={values.paid_on} onChange={set('paid_on')} />
          </Field>
        ) : (
          <Field label="Due date" error={errors.due_date}>
            <input type="date" value={values.due_date} onChange={set('due_date')} />
          </Field>
        )}
        <Field label="Reference" error={errors.reference} full>
          <input value={values.reference} onChange={set('reference')} placeholder="Transaction ID, cheque no…" />
        </Field>
        <Field label="Notes" error={errors.notes} full>
          <textarea rows={2} value={values.notes} onChange={set('notes')} />
        </Field>
      </form>
    </Modal>
  );
}

export function PaymentUpdateModal({ payment, onClose, onSaved }) {
  const toast = useToast();
  const form = useForm({
    status: payment.status,
    method: payment.method || '',
    paid_on: payment.paid_on || todayISO(),
    reference: payment.reference || '',
    notes: payment.notes || '',
  });
  const { values, set, errors } = form;
  const subtitle = useMemo(
    () => (payment.subscription ? `${payment.subscription.customer.full_name} · ${payment.subscription.service_name}` : undefined),
    [payment],
  );

  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const body = { ...v };
      if (body.status !== 'paid') delete body.paid_on;
      const saved = await api.put(`/payments/${payment.id}`, body);
      toast.success(`Payment ${saved.code} updated.`);
      onSaved(saved);
      return true;
    });
  };

  return (
    <Modal
      title={`Update ${payment.code} · ${money(payment.amount)}`}
      subtitle={subtitle}
      size="sm"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="payment-update-form" loading={form.submitting}>
            Save
          </Button>
        </>
      }
    >
      <form id="payment-update-form" className="form-grid form-grid-1" onSubmit={save} noValidate>
        <FormError message={form.formError} />
        <Field label="Payment status" error={errors.status}>
          <div className="segmented">
            {['paid', 'pending', 'failed'].map((s) => (
              <button
                key={s}
                type="button"
                className={`segment segment-${s} ${values.status === s ? 'segment-active' : ''}`}
                onClick={() => set('status')(s)}
              >
                {s[0].toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </Field>
        {values.status === 'paid' && (
          <Field label="Paid on" error={errors.paid_on}>
            <input type="date" max={todayISO()} value={values.paid_on} onChange={set('paid_on')} />
          </Field>
        )}
        <Field label="Method" error={errors.method}>
          <select value={values.method} onChange={set('method')}>
            <option value="">Not specified</option>
            {Object.entries(METHOD_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Reference" error={errors.reference}>
          <input value={values.reference} onChange={set('reference')} />
        </Field>
        <Field label="Notes" error={errors.notes}>
          <textarea rows={2} value={values.notes} onChange={set('notes')} />
        </Field>
      </form>
    </Modal>
  );
}
