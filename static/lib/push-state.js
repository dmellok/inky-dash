// Cross-tab "is a push in flight" guard.
//
// Any UI flow that publishes to the panel wraps its fetch in
// `runWithPushLock(fn)`. While the lock is held:
//   - This tab knows it (in-memory flag).
//   - Other tabs of /editor /send /schedules know it (localStorage event).
// Buttons disable themselves when `isPushing()` is true. The state is
// timestamp-bound so a crashed tab can't leave the lock stuck forever.
//
// This is layered on top of the server-side debounce + single-flight lock;
// the UI side prevents the multi-click in the first place, the server side
// catches it if anything slips through.

const STORAGE_KEY = "inky_push_inflight";
const MAX_AGE_MS = 60_000; // a single render shouldn't take more than this
const listeners = new Set();

let memoryState = readStorage();

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.startedAt !== "number") return null;
    if (Date.now() - parsed.startedAt > MAX_AGE_MS) {
      // Stale entry (tab crashed mid-push). Clear it.
      localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function writeStorage(state) {
  try {
    if (state) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    /* Storage may be disabled / quota'd; fall through to in-memory only. */
  }
}

function emit() {
  for (const cb of listeners) {
    try {
      cb(memoryState);
    } catch {
      /* listener errors don't break the others */
    }
  }
}

// React to other-tab updates.
window.addEventListener("storage", (e) => {
  if (e.key !== STORAGE_KEY) return;
  memoryState = readStorage();
  emit();
});

// Periodic sweep in case our own tab's clock advances past MAX_AGE_MS.
setInterval(() => {
  const fresh = readStorage();
  if ((fresh == null) !== (memoryState == null)) {
    memoryState = fresh;
    emit();
  }
}, 5_000);

export function isPushing() {
  // Refresh from storage in case another tab wrote since the last event.
  memoryState = readStorage();
  return memoryState !== null;
}

export function pushSource() {
  return memoryState?.source ?? null;
}

export function onPushStateChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

/**
 * Mark a push as in-flight while `fn()` runs. Always clears the flag,
 * even if `fn` throws. Returns whatever `fn` returns.
 *
 * Use this around every Send / Resend / Fire-now path so the guard is
 * automatic — never call mark/clear directly from feature code.
 */
export async function runWithPushLock(source, fn) {
  const state = { startedAt: Date.now(), source };
  memoryState = state;
  writeStorage(state);
  emit();
  try {
    return await fn();
  } finally {
    memoryState = null;
    writeStorage(null);
    emit();
  }
}
