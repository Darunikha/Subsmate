import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api';

/** Fetch `path` with `params`; refetches when either changes. */
export function useApi(path, params) {
  const [state, setState] = useState({ data: null, error: null, loading: Boolean(path) });
  const key = path ? `${path}?${JSON.stringify(params || {})}` : null;
  const latest = useRef(0);

  const load = useCallback(() => {
    if (!path) return Promise.resolve();
    const id = ++latest.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    return api
      .get(path, params)
      .then((data) => id === latest.current && setState({ data, error: null, loading: false }))
      .catch((error) => id === latest.current && setState({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: load };
}

export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Form state + submit handling with server-side field errors. */
export function useForm(initial) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const set = (name) => (event) => {
    const value = event?.target ? (event.target.type === 'checkbox' ? event.target.checked : event.target.value) : event;
    setValues((v) => ({ ...v, [name]: value }));
    setErrors((e) => ({ ...e, [name]: undefined }));
  };

  const submit = async (action) => {
    setSubmitting(true);
    setFormError('');
    try {
      return await action(values);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrors(error.errors || {});
        setFormError(error.message);
      } else {
        setFormError(String(error.message || error));
      }
      return undefined;
    } finally {
      setSubmitting(false);
    }
  };

  return { values, setValues, set, errors, setErrors, submitting, formError, submit };
}
