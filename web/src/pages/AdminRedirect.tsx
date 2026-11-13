import { useEffect } from "react";
import { adminUrl } from "../base";

/** Renvoie vers le backend Python (/admin), local ou via tunnel. */
export function AdminRedirect() {
  useEffect(() => {
    window.location.replace(adminUrl("/admin"));
  }, []);

  return (
    <main className="mx-auto max-w-lg px-4 py-16 text-center">
      <p className="text-sm text-ink-soft">Ouverture de l’administration…</p>
      <p className="mt-4">
        <a className="text-terracotta underline" href={adminUrl("/admin")}>
          Continuer vers l’admin
        </a>
      </p>
    </main>
  );
}
