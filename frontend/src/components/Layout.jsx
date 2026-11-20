import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import Icon from './Icon';
import { Avatar, StatusBadge } from './ui';
import { ROLE_LABELS, useAuth } from '../lib/auth';
import { api } from '../lib/api';
import { useDebounced } from '../lib/hooks';
import { timeAgo } from '../lib/format';

const NAV = [
  {
    section: 'Dashboard',
    items: [{ to: '/', label: 'Dashboard', icon: 'dashboard', end: true }],
  },
  {
    section: 'Manage',
    items: [
      { to: '/customers', label: 'Customers', icon: 'users', permission: 'viewCustomers' },
      { to: '/plans', label: 'Subscription Plans', icon: 'layers', permission: 'viewPlans' },
      { to: '/subscriptions', label: 'Subscriptions', icon: 'card', customerLabel: 'My Subscriptions' },
    ],
  },
  {
    section: 'Billing',
    items: [
      { to: '/renewals', label: 'Renewals', icon: 'refresh', badge: 'renewals' },
      { to: '/payments', label: 'Payments', icon: 'wallet', permission: 'viewPayments' },
    ],
  },
  {
    section: 'Insights',
    items: [{ to: '/reports', label: 'Reports', icon: 'chart', permission: 'viewReports' }],
  },
  {
    section: 'Account',
    items: [{ to: '/settings', label: 'Settings', icon: 'settings' }],
  },
];

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="Subsmate home">
      <img src="/logo.svg" alt="" width="32" height="32" />
      <span>
        Subs<em>Mate</em>
      </span>
    </Link>
  );
}

function Sidebar({ open, onClose, renewalCount }) {
  const { user, can } = useAuth();
  const isCustomer = user.role === 'customer';
  return (
    <>
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="sidebar-top">
          <Logo />
          <button type="button" className="icon-btn sidebar-close" onClick={onClose} aria-label="Close menu">
            <Icon name="x" />
          </button>
        </div>
        <nav className="nav">
          {NAV.map((group) => {
            const items = group.items.filter((item) => !item.permission || can(item.permission));
            if (!items.length) return null;
            return (
              <div key={group.section} className="nav-group">
                <p className="nav-section">{group.section}</p>
                {items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
                    onClick={onClose}
                  >
                    <Icon name={item.icon} size={19} />
                    <span>{isCustomer && item.customerLabel ? item.customerLabel : item.label}</span>
                    {item.badge === 'renewals' && renewalCount > 0 && <span className="nav-badge">{renewalCount}</span>}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <Avatar name={user.name} size="sm" />
          <div className="sidebar-user">
            <strong>{user.name}</strong>
            <span>{ROLE_LABELS[user.role]}</span>
          </div>
        </div>
      </aside>
      {open && <div className="sidebar-scrim" onClick={onClose} />}
    </>
  );
}

function useClickOutside(ref, onOutside) {
  useEffect(() => {
    const handler = (e) => ref.current && !ref.current.contains(e.target) && onOutside();
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [ref, onOutside]);
}

function GlobalSearch() {
  const [term, setTerm] = useState('');
  const [results, setResults] = useState(null);
  const [open, setOpen] = useState(false);
  const debounced = useDebounced(term, 250);
  const ref = useRef(null);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  useClickOutside(ref, () => setOpen(false));

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (debounced.trim().length < 2) {
      setResults(null);
      return;
    }
    let cancelled = false;
    api.get('/search', { q: debounced.trim() }).then((data) => !cancelled && setResults(data)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  const go = (path) => {
    setOpen(false);
    setTerm('');
    navigate(path);
  };
  const empty = results && !results.customers.length && !results.subscriptions.length && !results.plans.length;

  return (
    <div className="global-search" ref={ref}>
      <label className="search-input search-input-lg">
        <Icon name="search" size={17} />
        <input
          ref={inputRef}
          type="search"
          placeholder="Search customers, subscriptions, plans…"
          value={term}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setTerm(e.target.value);
            setOpen(true);
          }}
        />
        <kbd>Ctrl K</kbd>
      </label>
      {open && results && (
        <div className="dropdown search-results">
          {empty && <p className="dropdown-empty">No matches for “{debounced}”.</p>}
          {results.customers.length > 0 && (
            <div>
              <p className="dropdown-label">Customers</p>
              {results.customers.map((c) => (
                <button key={c.id} type="button" className="dropdown-item" onClick={() => go(`/customers/${c.id}`)}>
                  <Avatar name={c.full_name} size="sm" />
                  <span>
                    <strong>{c.full_name}</strong>
                    <small>{c.email}</small>
                  </span>
                </button>
              ))}
            </div>
          )}
          {results.subscriptions.length > 0 && (
            <div>
              <p className="dropdown-label">Subscriptions</p>
              {results.subscriptions.map((s) => (
                <button key={s.id} type="button" className="dropdown-item" onClick={() => go(`/subscriptions/${s.id}`)}>
                  <Icon name="card" size={17} />
                  <span>
                    <strong>
                      {s.code} · {s.plan.name}
                    </strong>
                    <small>{s.customer.full_name}</small>
                  </span>
                  <StatusBadge status={s.status} />
                </button>
              ))}
            </div>
          )}
          {results.plans.length > 0 && (
            <div>
              <p className="dropdown-label">Plans</p>
              {results.plans.map((p) => (
                <button key={p.id} type="button" className="dropdown-item" onClick={() => go('/plans')}>
                  <Icon name="layers" size={17} />
                  <span>
                    <strong>{p.name}</strong>
                    <small>${p.price} · {p.billing_cycle}</small>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const NOTE_ICONS = { renewal: 'clock', expired: 'alert', payment: 'wallet', system: 'bell' };

function Notifications() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ items: [], unread: 0 });
  const ref = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  useClickOutside(ref, () => setOpen(false));

  const load = () => api.get('/notifications').then(setData).catch(() => {});
  useEffect(() => {
    load();
  }, [location.pathname]);

  const openNote = async (note) => {
    if (!note.is_read) await api.post(`/notifications/${note.id}/read`).catch(() => {});
    setOpen(false);
    load();
    if (note.link) navigate(note.link);
  };
  const readAll = async () => {
    await api.post('/notifications/read-all');
    load();
  };

  return (
    <div className="topbar-menu" ref={ref}>
      <button type="button" className="icon-btn icon-btn-lg" aria-label="Notifications" onClick={() => setOpen((o) => !o)}>
        <Icon name="bell" size={19} />
        {data.unread > 0 && <span className="dot-count">{data.unread > 9 ? '9+' : data.unread}</span>}
      </button>
      {open && (
        <div className="dropdown notifications">
          <div className="dropdown-head">
            <strong>Notifications</strong>
            {data.unread > 0 && (
              <button type="button" className="link-btn" onClick={readAll}>
                Mark all as read
              </button>
            )}
          </div>
          {data.items.length === 0 && <p className="dropdown-empty">You're all caught up.</p>}
          <div className="notification-list">
            {data.items.map((note) => (
              <button
                key={note.id}
                type="button"
                className={`notification ${note.is_read ? '' : 'notification-unread'}`}
                onClick={() => openNote(note)}
              >
                <span className={`note-icon note-${note.category}`}>
                  <Icon name={NOTE_ICONS[note.category] || 'bell'} size={16} />
                </span>
                <span className="note-text">
                  <strong>{note.title}</strong>
                  <small>{note.message}</small>
                  <small className="muted">{timeAgo(note.created_at)}</small>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProfileMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  useClickOutside(ref, () => setOpen(false));
  return (
    <div className="topbar-menu" ref={ref}>
      <button type="button" className="profile-btn" onClick={() => setOpen((o) => !o)} aria-label="Account menu">
        <Avatar name={user.name} size="sm" />
        <span className="profile-name">
          <strong>{user.name.split(' ')[0]}</strong>
          <small>{ROLE_LABELS[user.role]}</small>
        </span>
        <Icon name="chevronDown" size={16} />
      </button>
      {open && (
        <div className="dropdown profile-dropdown">
          <div className="dropdown-head dropdown-head-col">
            <strong>{user.name}</strong>
            <small className="muted">{user.email}</small>
          </div>
          <button type="button" className="dropdown-item" onClick={() => { setOpen(false); navigate('/settings'); }}>
            <Icon name="settings" size={17} /> <span>Settings</span>
          </button>
          <button type="button" className="dropdown-item dropdown-item-danger" onClick={logout}>
            <Icon name="logout" size={17} /> <span>Log out</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renewalCount, setRenewalCount] = useState(0);
  const location = useLocation();

  useEffect(() => {
    api
      .get('/renewals/upcoming', { days: 7 })
      .then((d) => setRenewalCount(d.counts.overdue + d.counts.upcoming))
      .catch(() => {});
  }, [location.pathname]);

  return (
    <div className="shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} renewalCount={renewalCount} />
      <div className="main">
        <header className="topbar">
          <button type="button" className="icon-btn menu-btn" onClick={() => setMenuOpen(true)} aria-label="Open menu">
            <Icon name="menu" size={20} />
          </button>
          <div className="topbar-logo">
            <Logo />
          </div>
          <GlobalSearch />
          <div className="topbar-right">
            <Notifications />
            <ProfileMenu />
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
