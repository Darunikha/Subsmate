import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import { STATUS_LABELS, initials } from '../lib/format';

/* ------------------------------------------------------------------ basics */
export function Button({ variant = 'secondary', size, icon, loading, children, className = '', ...props }) {
  return (
    <button
      type="button"
      className={`btn btn-${variant} ${size ? `btn-${size}` : ''} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <span className="spinner spinner-sm" /> : icon && <Icon name={icon} size={16} />}
      {children && <span>{children}</span>}
    </button>
  );
}

export function IconButton({ icon, label, tone, ...props }) {
  return (
    <button type="button" className={`icon-btn ${tone ? `icon-btn-${tone}` : ''}`} aria-label={label} data-tip={label} {...props}>
      <Icon name={icon} size={17} />
    </button>
  );
}

export function Card({ title, icon, actions, children, className = '', bodyClass = '', subtitle }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          <div className="card-title">
            {icon && <Icon name={icon} size={18} className="muted-icon" />}
            <div>
              <h3>{title}</h3>
              {subtitle && <p className="card-subtitle">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className={`card-body ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions, back }) {
  return (
    <div className="page-header">
      <div>
        {back}
        <h1>{title}</h1>
        {subtitle && <p className="page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

const STATUS_TONES = {
  active: 'green',
  paid: 'green',
  expiring_soon: 'orange',
  pending: 'orange',
  expired: 'red',
  failed: 'red',
  cancelled: 'gray',
  inactive: 'gray',
};

export function StatusBadge({ status, label }) {
  return (
    <span className={`badge badge-${STATUS_TONES[status] || 'gray'}`}>
      <span className="badge-dot" />
      {label || STATUS_LABELS[status] || status}
    </span>
  );
}

export function Badge({ tone = 'gray', children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Avatar({ name, size = 'md' }) {
  return <span className={`avatar avatar-${size}`}>{initials(name)}</span>;
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="loading-block" role="status">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ icon = 'inbox', title, message, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} size={22} />
      </span>
      <h4>{title}</h4>
      {message && <p>{message}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="empty-state">
      <span className="empty-icon empty-icon-red">
        <Icon name="alert" size={22} />
      </span>
      <h4>Something went wrong</h4>
      <p>{error?.message || 'Could not load data.'}</p>
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Pager({ page, pages, total, onChange }) {
  if (!total) return null;
  return (
    <div className="pager">
      <span className="muted">
        {total} record{total === 1 ? '' : 's'}
      </span>
      {pages > 1 && (
        <div className="pager-controls">
          <IconButton icon="chevronLeft" label="Previous page" disabled={page <= 1} onClick={() => onChange(page - 1)} />
          <span>
            Page {page} of {pages}
          </span>
          <IconButton icon="chevronRight" label="Next page" disabled={page >= pages} onClick={() => onChange(page + 1)} />
        </div>
      )}
    </div>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={value === tab.value}
          className={`tab ${value === tab.value ? 'tab-active' : ''}`}
          onClick={() => onChange(tab.value)}
        >
          {tab.label}
          {tab.count !== undefined && <span className="tab-count">{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = 'Search…' }) {
  return (
    <label className="search-input">
      <Icon name="search" size={16} />
      <input type="search" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

/* ------------------------------------------------------------------ forms */
export function Field({ label, error, hint, children, full }) {
  return (
    <label className={`field ${full ? 'field-full' : ''}`}>
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

/* ------------------------------------------------------------------ modal */
export function Modal({ title, subtitle, onClose, children, footer, size = 'md' }) {
  const ref = useRef(null);
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const first = ref.current?.querySelector('input, select, textarea');
    first?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <header className="modal-header">
          <div>
            <h2>{title}</h2>
            {subtitle && <p className="muted">{subtitle}</p>}
          </div>
          <IconButton icon="x" label="Close" onClick={onClose} />
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-footer">{footer}</footer>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel = 'Confirm', tone = 'danger', onConfirm, onClose }) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const run = async () => {
    setBusy(true);
    try {
      await onConfirm();
      onClose();
    } catch (error) {
      toast.error(error.message);
      setBusy(false);
    }
  };
  return (
    <Modal
      title={title}
      onClose={onClose}
      size="sm"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant={tone} loading={busy} onClick={run}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="confirm-message">{message}</p>
    </Modal>
  );
}

/* ------------------------------------------------------------------ toasts */
const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, tone) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((list) => [...list, { id, message, tone }]);
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 4000);
  }, []);
  const api = useRef({ success: (m) => push(m, 'success'), error: (m) => push(m, 'error') });
  return (
    <ToastContext.Provider value={api.current}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`}>
            <Icon name={toast.tone === 'success' ? 'checkCircle' : 'alert'} size={18} />
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
