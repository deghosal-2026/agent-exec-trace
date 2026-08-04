/** Generic async data-fetching hook with loading/error states.
 *
 * Provides a consistent pattern for all API calls: wraps a promise-returning
 * function, tracks `loading` and `error` states, and exposes a `refetch` to
 * re-run the query.  Cancellation is handled automatically via a flag in the
 * cleanup callback, preventing state updates on unmounted components.
 */

import { useState, useEffect, useCallback } from "react";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = []
): AsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  const execute = useCallback(() => {
    let cancelled = false;
    setState({ data: null, loading: true, error: null });
    fn()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setState({
            data: null,
            loading: false,
            error: err instanceof Error ? err.message : "Unknown error",
          });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    const cleanup = execute();
    return cleanup;
  }, [execute]);

  return { ...state, refetch: execute };
}