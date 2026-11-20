import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import { EmptyState, Spinner } from './components/ui';
import { useAuth } from './lib/auth';
import CustomerDetail from './pages/CustomerDetail';
import Customers from './pages/Customers';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import Payments from './pages/Payments';
import Renewals from './pages/Renewals';
import Reports from './pages/Reports';
import Settings from './pages/Settings';
import SubscriptionDetail from './pages/SubscriptionDetail';
import Subscriptions from './pages/Subscriptions';

function RequireAuth({ children }) {
  const { user, loading, signedOutByUser } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner label="Loading Subsmate…" />;
  if (!user) {
    // After a deliberate logout the next sign-in starts at the dashboard, not the page the last person was on.
    const from = signedOutByUser ? '/' : location.pathname + location.search;
    return <Navigate to="/login" replace state={{ from }} />;
  }
  return children;
}

function Allow({ permission, children }) {
  const { can } = useAuth();
  if (can(permission)) return children;
  return (
    <EmptyState
      icon="lock"
      title="Access restricted"
      message="Your role does not have access to this page."
      action={
        <Link to="/" className="btn btn-primary">
          Back to dashboard
        </Link>
      }
    />
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="customers" element={<Allow permission="viewCustomers"><Customers /></Allow>} />
        <Route path="customers/:id" element={<Allow permission="viewCustomers"><CustomerDetail /></Allow>} />
        <Route path="subscriptions" element={<Subscriptions />} />
        <Route path="subscriptions/:id" element={<SubscriptionDetail />} />
        <Route path="renewals" element={<Renewals />} />
        <Route path="payments" element={<Allow permission="viewPayments"><Payments /></Allow>} />
        <Route path="reports" element={<Allow permission="viewReports"><Reports /></Allow>} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<EmptyState icon="alert" title="Page not found" message="The page you're looking for doesn't exist." />} />
      </Route>
    </Routes>
  );
}
