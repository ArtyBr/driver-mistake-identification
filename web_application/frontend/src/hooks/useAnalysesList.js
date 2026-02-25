import { useState, useEffect, useRef, useCallback } from 'react';
import { listAnalyses } from '../services/api';

const ACTIVE_STATUSES = new Set(['PENDING', 'SUBMITTED', 'RUNNING']);
const LS_KEY = 'safedrive_job_etas';

// ── localStorage helpers (all synchronous, never throw) ──────────────────────

const loadAllStoredEtas = () => {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}'); }
  catch { return {}; }
};

/** Persist a fresh ETA estimate together with the wall-clock time it was made. */
const persistEta = (jobId, etaMs) => {
  try {
    const all = loadAllStoredEtas();
    all[jobId] = { etaMs, savedAt: Date.now() };
    localStorage.setItem(LS_KEY, JSON.stringify(all));
  } catch { /* storage full or private-mode — silently ignore */ }
};

/** Remove stored ETA for jobs that are no longer active. */
const clearStoredEta = (jobId) => {
  try {
    const all = loadAllStoredEtas();
    if (all[jobId]) {
      delete all[jobId];
      localStorage.setItem(LS_KEY, JSON.stringify(all));
    }
  } catch {
    /* Silently ignore storage errors */
  }
};

/**
 * Return the stored ETA for a job, adjusted for elapsed time since it was
 * saved.  Returns null if nothing is stored or the stored value has expired.
 */
const getAdjustedStoredEtaMs = (jobId) => {
  try {
    const entry = loadAllStoredEtas()[jobId];
    if (!entry) return null;
    const adjusted = entry.etaMs - (Date.now() - entry.savedAt);
    return adjusted > 0 ? adjusted : null;
  } catch { return null; }
};

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Fetches and polls the analyses list, tracking per-job progress history
 * so that an ETA can be estimated for active jobs.
 *
 * ETAs are persisted to localStorage so that re-loading the page shows an
 * immediate approximate value while fresh readings are being collected.
 */
export const useAnalysesList = () => {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const pollRef = useRef(null);
  // jobId -> [{ time: ms, progress: 0-100 }, ...]
  const historyRef = useRef({});

  const fetchAnalyses = useCallback(async () => {
    try {
      const data = await listAnalyses();
      const now = Date.now();
      data.forEach(a => {
        if (!ACTIVE_STATUSES.has(a.status)) {
          // Clean up stale stored ETAs when a job finishes
          clearStoredEta(a.id);
          return;
        }
        if (!historyRef.current[a.id]) historyRef.current[a.id] = [];
        const hist = historyRef.current[a.id];
        const p = a.progress || 0;
        const last = hist[hist.length - 1];
        // Require at least 2% progress gain before recording a new point.
        // This avoids a skewed first estimate when polling starts mid-increment.
        if (!last || (p - last.progress) >= 2) {
          hist.push({ time: now, progress: p });
          if (hist.length > 30) hist.shift();
        }
      });
      setAnalyses(data);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchAnalyses();
  }, [fetchAnalyses]);

  // Poll every 5s while any job is active; stop when all settle
  useEffect(() => {
    clearInterval(pollRef.current);
    if (analyses.some(a => ACTIVE_STATUSES.has(a.status))) {
      pollRef.current = setInterval(fetchAnalyses, 5000);
    }
    return () => clearInterval(pollRef.current);
  }, [analyses, fetchAnalyses]);

  /**
   * Returns the estimated milliseconds remaining for a job, or null if unknown.
   *
   * Priority:
   *   1. Live calculation from ≥2 progress readings (persisted to localStorage).
   *   2. Previously-stored estimate adjusted for elapsed time (used on page load
   *      before enough fresh readings have been collected).
   */
  const getEtaMs = useCallback((jobId, currentProgress) => {
    const hist = historyRef.current[jobId];
    if (hist && hist.length >= 2) {
      const oldest = hist[0];
      const newest = hist[hist.length - 1];
      const dt = newest.time - oldest.time;   // ms elapsed
      const dp = newest.progress - oldest.progress; // % gained
      if (dp > 0 && dt > 0) {
        const etaMs = ((100 - currentProgress) / dp) * dt;
        persistEta(jobId, etaMs); // keep localStorage up to date
        return etaMs;
      }
    }

    // Not enough live data yet — fall back to the stored estimate
    return getAdjustedStoredEtaMs(jobId);
  }, []);

  return { analyses, loading, refetch: fetchAnalyses, getEtaMs };
};
