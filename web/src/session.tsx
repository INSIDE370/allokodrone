import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setCsrf } from "./api";
import type { Session } from "./types";

type Store = {
  session: Session | null;
  error: string;
  refresh: () => Promise<void>;
  setCartCount: (count: number) => void;
  notice: string;
  push: (message: string) => void;
};

const Context = createContext<Store | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    try {
      const next = await api<Session>("/api/session");
      setCsrf(next.csrf);
      setSession(next);
      setError("");
    } catch {
      setError("Connexion interrompue. Réessayez.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(""), 3400);
    return () => window.clearTimeout(id);
  }, [notice]);

  const setCartCount = useCallback((count: number) => {
    setSession((current) => (current ? { ...current, cartCount: count } : current));
  }, []);

  return (
    <Context.Provider value={{ session, error, refresh, setCartCount, notice, push: setNotice }}>
      {children}
    </Context.Provider>
  );
}

export function useSession() {
  const value = useContext(Context);
  if (!value) throw new Error("session");
  return value;
}
