import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { Button, Field } from '../components/ui';
import Icon from '../components/Icon';

const DEMO_ACCOUNTS = [
  { role: 'Administrator', email: 'admin@subsmate.io', password: 'Admin@123' },
  { role: 'Staff', email: 'staff@subsmate.io', password: 'Staff@123' },
  { role: 'Customer', email: 'priya.sharma@brightdental.com', password: 'Customer@123' },
];

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      await login(email, password);
      navigate(location.state?.from || '/', { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <section className="login-brand">
        <div className="login-logo">
          <img src="/logo.svg" alt="" width="40" height="40" />
          <span>
            Subs<em>Mate</em>
          </span>
        </div>
        <div className="login-pitch">
          <h1>Never miss a renewal again.</h1>
          <p>Track customer subscriptions, renewal dates and payments in one calm, organised workspace.</p>
          <ul>
            <li>
              <Icon name="refresh" size={18} /> Automatic expiry dates and renewal reminders
            </li>
            <li>
              <Icon name="wallet" size={18} /> Manual payment tracking with pending alerts
            </li>
            <li>
              <Icon name="chart" size={18} /> Revenue, renewal and plan reports with CSV export
            </li>
          </ul>
        </div>
        <p className="login-foot">Subscription &amp; Renewal Management Platform</p>
      </section>

      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <h2>Sign in</h2>
          <p className="muted">Welcome back. Enter your account details.</p>
          {error && <div className="form-error">{error}</div>}
          <Field label="Email address">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </Field>
          <Field label="Password">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </Field>
          <Button variant="primary" type="submit" loading={busy} className="btn-block">
            Sign in
          </Button>

          <div className="demo-accounts">
            <p>Demo accounts — click to fill</p>
            <div className="demo-grid">
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  className="demo-account"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(account.password);
                    setError('');
                  }}
                >
                  <strong>{account.role}</strong>
                  <small>{account.email}</small>
                </button>
              ))}
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
