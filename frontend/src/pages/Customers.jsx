import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CustomerForm } from '../components/forms';
import {
  Avatar,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  IconButton,
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
import { formatDate } from '../lib/format';

export default function Customers() {
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [term, setTerm] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null); // null | 'new' | customer
  const [deleting, setDeleting] = useState(null);
  const q = useDebounced(term);
  const { data, error, loading, reload } = useApi('/customers', { q, status, page });

  const changeFilter = (setter) => (value) => {
    setter(value);
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title="Customers"
        subtitle="Register customers and review their subscription history."
        actions={
          can('manageCustomers') && (
            <Button variant="primary" icon="plus" onClick={() => setEditing('new')}>
              Add customer
            </Button>
          )
        }
      />
      <Card bodyClass="card-body-flush">
        <div className="toolbar">
          <Tabs
            value={status}
            onChange={changeFilter(setStatus)}
            tabs={[
              { value: '', label: 'All' },
              { value: 'active', label: 'Active' },
              { value: 'inactive', label: 'Inactive' },
            ]}
          />
          <SearchInput value={term} onChange={changeFilter(setTerm)} placeholder="Search by name, email or phone" />
        </div>
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : loading && !data ? (
          <Spinner />
        ) : data.items.length === 0 ? (
          <EmptyState
            icon="users"
            title={q || status ? 'No matching customers' : 'No customers yet'}
            message={q || status ? 'Try a different search or filter.' : 'Register your first customer to get started.'}
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Customer</th>
                  <th className="hide-sm">Phone</th>
                  <th className="hide-sm">Registered</th>
                  <th className="num">Subscriptions</th>
                  <th>Status</th>
                  <th className="actions-col" aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} className="row-link" onClick={() => navigate(`/customers/${c.id}`)}>
                    <td>
                      <div className="cell-person">
                        <Avatar name={c.full_name} />
                        <div className="cell-main">
                          <Link to={`/customers/${c.id}`} onClick={(e) => e.stopPropagation()}>
                            <strong>{c.full_name}</strong>
                          </Link>
                          <span className="muted">
                            {c.code} · {c.email}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="hide-sm">{c.phone || <span className="muted">—</span>}</td>
                    <td className="hide-sm">{formatDate(c.registration_date)}</td>
                    <td className="num">
                      <strong>{c.active_subscription_count}</strong>
                      <span className="muted"> / {c.subscription_count}</span>
                    </td>
                    <td>
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="actions-col" onClick={(e) => e.stopPropagation()}>
                      <div className="row-actions">
                        {can('manageCustomers') && <IconButton icon="edit" label="Edit" onClick={() => setEditing(c)} />}
                        {can('deleteCustomers') && (
                          <IconButton icon="trash" label="Delete" tone="danger" onClick={() => setDeleting(c)} />
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && <Pager page={data.page} pages={data.pages} total={data.total} onChange={setPage} />}
      </Card>

      {editing && (
        <CustomerForm
          customer={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            if (editing === 'new') navigate(`/customers/${saved.id}`);
            else reload();
          }}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.full_name}?`}
          message={
            deleting.subscription_count
              ? 'This customer has subscription history, which must be kept. Deletion will be refused — mark the customer inactive instead.'
              : 'This permanently removes the customer and any portal login. This cannot be undone.'
          }
          confirmLabel="Delete customer"
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            await api.del(`/customers/${deleting.id}`);
            toast.success('Customer deleted.');
            reload();
          }}
        />
      )}
    </>
  );
}
