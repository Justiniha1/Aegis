"use client";

import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";
import type { RunStatus, ProfileOut, TestResult } from "./types";
import { triggerRun as apiTriggerRun, getRun, listProfiles, apiGet } from "./api";
import { useAuth } from "./auth";

const PROFILE_STORAGE_KEY = "aegis_active_profile";

type RunCtx = {
  profiles: ProfileOut[];
  selectedProfile: string | null;
  setSelectedProfile: (name: string) => void;
  refreshProfiles: () => void;
  runId: number | null;
  runStatus: RunStatus | null;
  runError: string | null;
  isTriggering: boolean;
  trigger: () => Promise<void>;
  lastCompleted: number;
  passingCount: number;
  warningCount: number;
  profilesLoading: boolean;
  profilesError: string | null;
};

const RunContext = createContext<RunCtx | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  const [profiles, setProfiles] = useState<ProfileOut[]>([]);
  const [selectedProfile, setSelectedProfileState] = useState<string | null>(() =>
    typeof window !== "undefined" ? localStorage.getItem(PROFILE_STORAGE_KEY) : null
  );
  const [runId, setRunId] = useState<number | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [lastCompleted, setLastCompleted] = useState(0);
  const [passingCount, setPassingCount] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [profilesLoading, setProfilesLoading] = useState(true);
  const [profilesError, setProfilesError] = useState<string | null>(null);
  const runStatusRef = useRef<RunStatus | null>(null);
  const isTriggeringRef = useRef(false);
  runStatusRef.current = runStatus;

  const setSelectedProfile = useCallback((name: string) => {
    setSelectedProfileState(name);
    if (typeof window !== "undefined") localStorage.setItem(PROFILE_STORAGE_KEY, name);
  }, []);

  const loadProfiles = useCallback(() => {
    if (!token) return;
    setProfilesLoading(true);
    setProfilesError(null);
    listProfiles(token).then((p) => {
      setProfiles(p);
      const storedName = typeof window !== "undefined" ? localStorage.getItem(PROFILE_STORAGE_KEY) : null;
      if (!storedName && p.length > 0) {
        setSelectedProfile(p[0].name);
      } else if (storedName && !p.find((prof) => prof.name === storedName)) {
        setSelectedProfileState(null);
        if (typeof window !== "undefined") localStorage.removeItem(PROFILE_STORAGE_KEY);
      }
      setProfilesLoading(false);
    }).catch((err: unknown) => {
      setProfilesError(err instanceof Error ? err.message : "Failed to load profiles");
      setProfilesLoading(false);
    });
  }, [token, setSelectedProfile]);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  // Fetch latest run counts for TopBar badges. Re-runs on initial load and after each run completes.
  useEffect(() => {
    if (!token) return;
    apiGet("/api/v1/results?limit=500", token)
      .then((results: unknown) => {
        if (!Array.isArray(results) || results.length === 0) return;
        const typedResults = results as TestResult[];
        const latestRunId = typedResults[0].run_id;
        const latest = latestRunId != null
          ? typedResults.filter((r) => r.run_id === latestRunId)
          : typedResults.filter((r) => r.run_at === typedResults[0].run_at);
        setPassingCount(latest.filter((r) => r.status === "PASSED").length);
        setWarningCount(latest.filter((r) => r.status !== "PASSED").length);
      })
      .catch(() => {});
  }, [token, lastCompleted]);

  useEffect(() => {
    if (!runId || !token) return;
    if (runStatusRef.current === "COMPLETE" || runStatusRef.current === "FAILED") return;

    const interval = setInterval(async () => {
      try {
        const run = await getRun(runId, token);
        setRunStatus(run.status);
        if (run.error) setRunError(run.error.reason);
        if (run.status === "COMPLETE" || run.status === "FAILED") {
          clearInterval(interval);
          setLastCompleted((n) => n + 1);
        }
      } catch {
        // ignore transient poll errors
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [runId, token]); // eslint-disable-line react-hooks/exhaustive-deps

  const trigger = useCallback(async () => {
    if (!token || !selectedProfile || isTriggeringRef.current) return;
    isTriggeringRef.current = true;
    setIsTriggering(true);
    setRunError(null);
    setRunStatus(null);
    try {
      const res = await apiTriggerRun(selectedProfile, null, token);
      setRunId(res.run_id);
      setRunStatus(res.status);
    } catch (e: unknown) {
      setRunError(e instanceof Error ? e.message : "Run failed");
    } finally {
      isTriggeringRef.current = false;
      setIsTriggering(false);
    }
  }, [token, selectedProfile]);

  return (
    <RunContext.Provider
      value={{ profiles, selectedProfile, setSelectedProfile, refreshProfiles: loadProfiles,
               profilesLoading, profilesError,
               runId, runStatus, runError, isTriggering, trigger, lastCompleted, passingCount, warningCount }}
    >
      {children}
    </RunContext.Provider>
  );
}

export function useRunContext() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRunContext must be used inside RunProvider");
  return ctx;
}
