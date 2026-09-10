"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { HealthStatus } from "@/types/health";
import { fetchHealth } from "@/lib/api";

export function useHealth(pollingIntervalMs: number = 5000) {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<number | null>(null);

  const isMountedRef = useRef<boolean>(true);

  const check = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchHealth();
      if (isMountedRef.current) {
        setHealth(data);
        setError(null);
        setLastChecked(Date.now());
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        setHealth(null); // Clear health so offline is visibly reflected
        setError(err instanceof Error ? err.message : "Health check request failed");
        setLastChecked(Date.now());
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    check();

    // Auto-poll so UI dynamically updates when backend starts/stops
    let intervalId: NodeJS.Timeout | null = null;
    if (pollingIntervalMs > 0) {
      intervalId = setInterval(() => {
        check();
      }, pollingIntervalMs);
    }

    return () => {
      isMountedRef.current = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [check, pollingIntervalMs]);

  return { health, loading, error, lastChecked, refetch: check };
}
