/**
 * Generic async data-fetching hook with loading, error, and data states.
 *
 * Provides a consistent pattern for all API calls throughout the application.
 * Every page uses this hook to wrap an API client call and receives:
 * - `data` — the resolved typed value (or `null` before completion)
 * - `loading` — `true` while the promise is in-flight
 * - `error` — human-readable error string (or `null`)
 * - `refetch` — re-runs the promise function (also auto-called on dependency changes)
 *
 * ## Cancellation
 * Each invocation sets a `cancelled` flag in the cleanup callback. If the
 * component unmounts before the promise settles, the state update is silently
 * dropped. This prevents the classic "setState on unmounted component" warning.
 *
 * ## Dependency tracking
 * The `deps` array is passed to `useCallback` and controls when the promise
 * is re-executed. Changing a dependency triggers a new fetch. Empty `deps` (default)
 * means the fetch runs once on mount.
 *
 * ## Usage pattern across pages
 * ```ts
 * const { data, loading, error, refetch } = useAsync(
 *   () => api.getFleet({ agent_name: filter }),
 *   [filter]  // re-fetch when filter changes
 * );
 * ```
 *
 * @param fn - Async function that returns a promise of T (typically an API call)
 * @param deps - Dependency array controlling re-execution (default: [])
 * @returns An object with data, loading, error, and refetch properties
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
    loading: true,    // Start in loading state; first fetch begins immediately
    error: null,
  });

  /**
   * Executes the async function and manages the loading/error/data state transitions.
   *
   * Wrapped in `useCallback` to ensure referential stability based on `deps`.
   * Returns a cleanup function that sets `cancelled = true` to prevent
   * state updates after unmount.
   */
  const execute = useCallback(() => {
    let cancelled = false;
    // Reset to loading state before each execution
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
    // Return the cancellation function
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // Re-run execute whenever deps change (or on mount)
  // eslint-disable-next-line react-hooks/rules-of-hooks
  useEffect(() => {
    const cleanup = execute();
    return cleanup;   // Call cleanup on unmount or before re-execution
  }, [execute]);

  return { ...state, refetch: execute };
}