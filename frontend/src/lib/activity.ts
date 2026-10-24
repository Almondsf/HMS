/**
 * Is anyone using this computer? Screens that refresh themselves (the queue,
 * lab and pharmacy lists, the notification bell) slow down when nobody has
 * touched it for a while, e.g. a reception PC left on the queue all day, and
 * catch up the moment someone moves the mouse or presses a key.
 *
 * Hidden tabs don't refresh at all (TanStack Query's default).
 */

export const IDLE_AFTER_MS = 5 * 60_000
const IDLE_REFRESH_MS = 2 * 60_000

let lastActivity = Date.now()

/** Start listening for activity; `onWake` runs when someone returns after being idle. */
export function trackActivity(onWake: () => void) {
  const touched = () => {
    const wasIdle = isIdle()
    lastActivity = Date.now()
    if (wasIdle) onWake()
  }
  for (const event of ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart']) {
    window.addEventListener(event, touched, { passive: true })
  }
}

export function isIdle(): boolean {
  return Date.now() - lastActivity > IDLE_AFTER_MS
}

/** A refetchInterval that relaxes to every 2 minutes (or 4× the normal interval) while nobody is around. */
export function liveInterval(ms: number): () => number {
  return () => (isIdle() ? Math.max(ms * 4, IDLE_REFRESH_MS) : ms)
}
