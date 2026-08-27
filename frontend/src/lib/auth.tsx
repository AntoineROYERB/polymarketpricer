"use client";

import { createContext, useContext, useCallback, useSyncExternalStore, type ReactNode } from "react";

const STORAGE_KEY = "pm-api-key";
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    listeners.delete(callback);
    window.removeEventListener("storage", callback);
  };
}

function getSnapshot(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

function getServerSnapshot(): string | null {
  return null;
}

interface AuthContextValue {
  apiKey: string | null;
  setApiKey: (key: string) => void;
  clearApiKey: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const apiKey = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const setApiKey = useCallback((key: string) => {
    localStorage.setItem(STORAGE_KEY, key);
    notify();
  }, []);

  const clearApiKey = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    notify();
  }, []);

  return (
    <AuthContext.Provider value={{ apiKey, setApiKey, clearApiKey, isAuthenticated: !!apiKey }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
