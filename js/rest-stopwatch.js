/* State only: the existing large/mini pill rendering and FLIP animations stay in index.html. */
(function(root) {
  'use strict';
  const empty = () => ({active: false, startedAt: 0, pausedAt: 0, pausedTotalMs: 0});
  function create({storage, key, now = Date.now, maxElapsedMs = 30 * 60 * 1000}) {
    let state = empty();
    const persist = () => {
      if (state.active) storage.setItem(key, JSON.stringify(state)); else storage.removeItem(key);
      return {...state};
    };
    return {
      restore() {
        try {
          const saved = JSON.parse(storage.getItem(key) || 'null');
          if (saved?.active && Number.isFinite(saved.startedAt) && saved.startedAt > 0 &&
            Number.isFinite(saved.pausedAt) && saved.pausedAt >= 0 &&
            Number.isFinite(saved.pausedTotalMs) && saved.pausedTotalMs >= 0 &&
            (!saved.pausedAt || saved.pausedAt >= saved.startedAt)) state = saved;
        } catch (_) { state = empty(); }
        if (state.active && Math.max(0, (state.pausedAt || now()) - state.startedAt - state.pausedTotalMs) >= maxElapsedMs) {
          state = empty(); storage.removeItem(key);
        }
        return {...state};
      },
      reset() { state = {active: true, startedAt: now(), pausedAt: 0, pausedTotalMs: 0}; return persist(); },
      togglePause() {
        if (!state.active) return {...state};
        if (state.pausedAt) { state.pausedTotalMs += Math.max(0, now() - state.pausedAt); state.pausedAt = 0; }
        else state.pausedAt = now();
        return persist();
      },
      stop() { state = empty(); return persist(); },
      elapsed() { return state.active ? Math.max(0, (state.pausedAt || now()) - state.startedAt - state.pausedTotalMs) : 0; },
      expired() { return state.active && Math.max(0, (state.pausedAt || now()) - state.startedAt - state.pausedTotalMs) >= maxElapsedMs; }
    };
  }
  const api = {create};
  if (typeof module !== 'undefined') module.exports = api;
  root.MFRestStopwatch = api;
})(typeof window === 'undefined' ? globalThis : window);
