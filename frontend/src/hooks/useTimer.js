import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Counts UP from a fixed start timestamp. Used for the workout-duration
 * header timer (White Paper §7.1): reading Date.now() - start on every
 * tick means a backgrounded tab or a missed interval never causes drift.
 */
export function useElapsed(startedAt, paused = false) {
  const [elapsedSec, setElapsedSec] = useState(0);
  const pauseAccumRef = useRef(0);
  const pauseStartRef = useRef(null);

  useEffect(() => {
    if (paused) {
      pauseStartRef.current = Date.now();
      return;
    }
    if (pauseStartRef.current) {
      pauseAccumRef.current += Date.now() - pauseStartRef.current;
      pauseStartRef.current = null;
    }
    const tick = () => {
      const raw = Date.now() - startedAt - pauseAccumRef.current;
      setElapsedSec(Math.max(0, Math.floor(raw / 1000)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt, paused]);

  return elapsedSec;
}

/**
 * Counts DOWN from a target duration for the rest timer (White Paper §7.1).
 * Restarting resets the target timestamp rather than an interval counter,
 * so +30s/-30s adjustments and tab switches stay accurate.
 */
export function useCountdown() {
  const [targetAt, setTargetAt] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(0);

  useEffect(() => {
    if (!targetAt) return;
    const tick = () => {
      const remaining = Math.round((targetAt - Date.now()) / 1000);
      setSecondsLeft(Math.max(0, remaining));
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [targetAt]);

  const start = useCallback((seconds) => {
    setTargetAt(Date.now() + seconds * 1000);
  }, []);

  const addSeconds = useCallback((delta) => {
    setTargetAt((prev) => (prev ? prev + delta * 1000 : prev));
  }, []);

  const stop = useCallback(() => setTargetAt(null), []);

  return { secondsLeft, isRunning: !!targetAt, start, addSeconds, stop };
}

export function formatMMSS(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}
