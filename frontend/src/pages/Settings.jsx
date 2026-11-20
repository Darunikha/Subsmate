import { useState } from 'react';
import {
  Avatar,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  ErrorState,
  Field,
  IconButton,
  Modal,
  PageHeader,
  Spinner,
  useToast,
} from '../components/ui';
import { api, setToken } from '../lib/api';
import { ROLE_LABELS, useAuth } from '../lib/auth';
import { useApi, useForm } from '../lib/hooks';
import { formatDate, timeAgo } from '../lib/format';

function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const form = useForm({ name: user.name });
  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const updated = await api.put('/auth/me', v);
      setUser(updated);
      toast.success('Profile updated.');
      return true;
    });
  };
  return (
    <Card title="Profile" icon="user">
      <form className="form-grid form-grid-1" onSubmit={save}>
        <div className="profile-inline">
          <Avatar name={user.name} size="lg" />
          <div>
            <strong>{user.name}</strong>
            <span className="muted">
              {ROLE_LABELS[user.role]} · {user.email}
            </span>
          </div>
        </div>
        {form.formError && <div className="form-error">{form.formError}</div>}
        <Field label="Display name" error={form.errors.name}>
          <input value={form.values.name} onChange={form.set('name')} maxLength={120} />
        </Field>
        <div>
          <Button type="submit" variant="primary" loading={form.submitting}>
            Save profile
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ChangePassword() {
  const toast = useToast();
  const form = useForm({ current_password: '', new_password: '', confirm: '' });
  const save = (e) => {
    e.preventDefault();
    if (form.values.new_password !== form.values.confirm) {
      form.setErrors({ confirm: 'Passwords do not match.' });
      return;
    }
    form.submit(async (v) => {
      const result = await api.post('/auth/change-password', {
        current_password: v.current_password,
        new_password: v.new_password,
      });
      setToken(result.token);
      form.setValues({ current_password: '', new_password: '', confirm: '' });
      toast.success('Password changed.');
      return true;
    });
  };
  return (
    <Card title="Change password" icon="lock">
      <form className="form-grid form-grid-1" onSubmit={save}>
        {form.formError && <div className="form-error">{form.formError}</div>}
        <Field label="Current password" error={form.errors.current_password}>
          <input type="password" value={form.values.current_password} onChange={form.set('current_password')} autoComplete="current-password" />
        </Field>
        <Field label="New password" error={form.errors.new_password} hint="At least 8 characters.">
          <input type="password" value={form.values.new_password} onChange={form.set('new_password')} autoComplete="new-password" />
        </Field>
        <Field label="Confirm new password" error={form.errors.confirm}>
          <input type="password" value={form.values.confirm} onChange={form.set('confirm')} autoComplete="new-password" />
        </Field>
        <div>
          <Button type="submit" variant="primary" loading={form.submitting}>
            Update password
          </Button>
        </div>
      </form>
    </Card>
  );
}

function UserForm({ editUser, onClose, onSaved }) {
  const toast = useToast();
  const form = useForm({
    name: editUser?.name || '',
    email: editUser?.email || '',
    role: editUser?.role || 'sales',
    password: '',
    is_active: editUser ? editUser.is_active : true,
  });
  const { values, set, errors } = form;
  const save = (e) => {
    e.preventDefault();
    form.submit(async (v) => {
      const body = { ...v };
      if (editUser && !body.password) delete body.password;
      if (editUser) await api.put(`/users/${editUser.id}`, body);
      else await api.post('/users', body);
      toast.success(editUser ? 'User updated.' : 'User created.');
      onSaved();
      return true;
    });
  };
  return (
    <Modal
      title={editUser ? 'Edit user' : 'Add staff user'}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="user-form" loading={form.submitting}>
            {editUser ? 'Save changes' : 'Create user'}
          </Button>
        </>
      }
    >
      <form id="user-form" className="form-grid" onSubmit={save} noValidate>
        {form.formError && <div className="form-error">{form.formError}</div>}
        <Field label="Full name" error={errors.name}>
          <input value={values.name} onChange={set('name')} />
        </Field>
        <Field label="Email" error={errors.email}>
          <input type="email" value={values.email} onChange={set('email')} />
        </Field>
        <Field label="Role" error={errors.role} hint={editUser?.role === 'customer' ? 'Customer logins keep the customer role.' : 'Customer logins are created from the Customers page.'}>
          <select value={values.role} onChange={set('role')} disabled={editUser?.role === 'customer'}>
            {Object.entries(ROLE_LABELS)
              .filter(([value]) => value !== 'customer' || editUser?.role === 'customer')
              .map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
          </select>
        </Field>
        <Field label={editUser ? 'Reset password' : 'Password'} error={errors.password} hint={editUser ? 'Leave blank to keep the current password.' : 'At least 8 characters.'}>
          <input type="password" value={values.password} onChange={set('password')} autoComplete="new-password" />
        </Field>
        {editUser && (
          <label className="checkbox field-full">
            <input type="checkbox" checked={values.is_active} onChange={set('is_active')} />
            <span>Account is active</span>
          </label>
        )}
      </form>
    </Modal>
  );
}

function UserManagement() {
  const { user: me } = useAuth();
  const toast = useToast();
  const { data, error, loading, reload } = useApi('/users', { per_page: 100 });
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);

  return (
    <Card
      title="Users & roles"
      subtitle="Staff accounts and customer portal logins"
      bodyClass="card-body-flush"
      actions={
        <Button size="sm" icon="plus" variant="primary" onClick={() => setEditing('new')}>
          Add user
        </Button>
      }
    >
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <Spinner />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th className="hide-sm">Last sign-in</th>
                <th>Status</th>
                <th className="actions-col" aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div className="cell-person">
                      <Avatar name={u.name} size="sm" />
                      <div className="cell-main">
                        <strong>
                          {u.name} {u.id === me.id && <span className="muted">(you)</span>}
                        </strong>
                        <span className="muted">{u.email}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <Badge tone={u.role === 'admin' ? 'accent' : u.role === 'customer' ? 'gray' : 'blue'}>{ROLE_LABELS[u.role]}</Badge>
                  </td>
                  <td className="hide-sm">{u.last_login_at ? timeAgo(u.last_login_at) : <span className="muted">Never</span>}</td>
                  <td>
                    <Badge tone={u.is_active ? 'green' : 'gray'}>{u.is_active ? 'Active' : 'Disabled'}</Badge>
                  </td>
                  <td className="actions-col">
                    <div className="row-actions">
                      <IconButton icon="edit" label="Edit user" onClick={() => setEditing(u)} />
                      {u.id !== me.id && <IconButton icon="trash" label="Delete user" tone="danger" onClick={() => setDeleting(u)} />}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && (
        <UserForm
          editUser={editing === 'new' ? null : editing}
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
          message={`Their account is removed, but records they created stay intact. Created ${formatDate(deleting.created_at)}. Consider disabling the account instead.`}
          confirmLabel="Delete user"
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            await api.del(`/users/${deleting.id}`);
            toast.success('User deleted.');
            reload();
          }}
        />
      )}
    </Card>
  );
}

export default function Settings() {
  const { can } = useAuth();
  return (
    <>
      <PageHeader title="Settings" subtitle="Manage your profile, password and team access." />
      <div className="grid-1-1">
        <Profile />
        <ChangePassword />
      </div>
      {can('manageUsers') && <UserManagement />}
    </>
  );
}
