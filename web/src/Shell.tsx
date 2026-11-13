import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { ServiceBar } from "./ServiceBar";
import { useSession } from "./session";

const link = "block text-sm tracking-wide transition-colors duration-300 hover:text-terracotta";

function Item({ to, children, className = "" }: { to: string; children: string; className?: string }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) => `${link} ${className} ${isActive ? "text-terracotta" : "text-cream"}`}
    >
      {children}
    </NavLink>
  );
}

function BasketMark() {
  return (
    <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 9h14l-1.2 10.2a1 1 0 0 1-1 .8H7.2a1 1 0 0 1-1-.8L5 9z" />
      <path d="M8.5 9 10 4.5h4L15.5 9" />
      <path d="M9 13.5v3.5" />
      <path d="M12 13.5v3.5" />
      <path d="M15 13.5v3.5" />
    </svg>
  );
}

const hungry = "inline-flex h-11 shrink-0 items-center bg-terracotta px-3 text-sm font-semibold uppercase tracking-[0.14em] text-white [text-shadow:none] transition-colors duration-300 hover:bg-terracotta-deep sm:px-5";
const cartLink = "inline-flex h-11 shrink-0 items-center gap-2 border border-cream/50 px-3 text-xs font-semibold uppercase tracking-[0.14em] text-cream transition-colors duration-300 hover:border-cream sm:px-4 sm:text-sm";

function MenuMark({ open }: { open: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6">
      {open ? (
        <>
          <path d="M5 5l12 12" />
          <path d="M17 5L5 17" />
        </>
      ) : (
        <>
          <path d="M3 6h16" />
          <path d="M3 11h16" />
          <path d="M3 16h16" />
        </>
      )}
    </svg>
  );
}

export function Shell() {
  const { session, error, refresh } = useSession();
  const { pathname } = useLocation();
  const home = pathname === "/";
  const [menuOpen, setMenuOpen] = useState(false);
  const [overHero, setOverHero] = useState(false);
  const melted = home && overHero;
  const count = session?.cartCount ?? 0;
  const restaurant = session?.restaurant;
  const entries: [string, string][] = [
    ["/", "Accueil"],
    ["/concept", "Concept"],
    ["/signature", "Signature"],
    ["/carte", "La carte"],
    ["/avis", "Avis"],
    ["/contact", "Nous trouver"],
  ];

  useEffect(() => {
    setMenuOpen(false);
    if (window.location.hash) return;
    window.scrollTo(0, 0);
  }, [pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  useEffect(() => {
    if (!home) return;
    const update = () => {
      const hero = document.getElementById("accueil");
      if (!hero) {
        setOverHero(false);
        return;
      }
      setOverHero(window.scrollY < 16 && hero.getBoundingClientRect().bottom > 72);
    };
    update();
    const root = document.getElementById("contenu");
    const observer = root ? new MutationObserver(update) : null;
    observer?.observe(root as Node, { childList: true, subtree: true });
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      observer?.disconnect();
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [home]);

  return (
    <div className="min-h-screen overflow-x-clip bg-paper font-sans text-ink antialiased">
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-cream focus:px-3 focus:py-2"
        href="#contenu"
      >
        Aller au contenu
      </a>
      <header className={melted
        ? "sticky top-0 z-40 bg-transparent text-cream [text-shadow:0_1px_2px_rgb(43_36_34_/_0.95),0_0_14px_rgb(43_36_34_/_0.8)]"
        : "sticky top-0 z-40 bg-night text-cream"}>
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 md:grid md:h-20 md:grid-cols-[auto_minmax(0,1fr)_auto] md:gap-10 md:px-8">
          <a className="shrink-0" href="/">
            <img className={`h-10 w-auto md:h-12 ${melted ? "drop-shadow-[0_2px_6px_rgba(28,22,18,0.9)]" : ""}`} src="/images/logo-light.png" width="532" height="299" alt="ALLOKODRONE" />
          </a>
          <nav className="hidden min-w-0 md:block" aria-label="Navigation principale">
            <ul className="flex items-center justify-center gap-6 whitespace-nowrap">
              {entries.map(([to, label]) => (
                <li key={to}><Item to={to}>{label}</Item></li>
              ))}
            </ul>
          </nav>
          <div className="flex shrink-0 items-center gap-2">
            <NavLink
              to="/panier"
              className={({ isActive }) => `${cartLink} ${isActive ? "border-terracotta text-terracotta" : ""}`}
              aria-label={count > 0 ? `Panier, ${count} article${count > 1 ? "s" : ""}` : "Panier"}
            >
              <BasketMark />
              Panier
              {count > 0 ? <span className="tabular-nums">{count}</span> : null}
            </NavLink>
            <a className={hungry} href={count > 0 ? "/panier" : "/carte"}>
              J'ai faim
            </a>
            <button
              className="inline-flex h-10 w-10 items-center justify-center text-cream md:hidden"
              type="button"
              aria-expanded={menuOpen}
              aria-controls="menu-mobile"
              aria-label={menuOpen ? "Fermer le menu" : "Ouvrir le menu"}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <MenuMark open={menuOpen} />
            </button>
          </div>
        </div>
        <nav id="menu-mobile" className={`${menuOpen ? "block" : "hidden"} border-t border-cream/15 bg-night px-4 py-2 md:hidden`} aria-label="Sections">
          <ul className="flex flex-col">
            {entries.map(([to, label]) => (
              <li key={to} className="border-b border-cream/10 last:border-b-0">
                <Item className="py-3 text-base" to={to}>{label}</Item>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      {error ? (
        <div className="border-b border-line bg-paper-2 px-4 py-3 text-sm" role="alert">
          {error}{" "}
          <button className="underline" type="button" onClick={() => void refresh()}>
            Réessayer
          </button>
        </div>
      ) : null}
      <ServiceBar />
      <main id="contenu">
        <div key={pathname} className="motion-fade">
          <Outlet />
        </div>
      </main>
      <footer className="mt-10 border-t border-line bg-night text-cream sm:mt-14">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <a href="/">
              <img className="h-14 w-auto" src="/images/logo-light.png" width="532" height="299" alt="ALLOKODRONE" />
            </a>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-cream/75">L'Afrique servie à grande vitesse.</p>
          </div>
          <div>
            <ul className="space-y-2 text-sm lg:pt-1">
              <li><a className="hover:text-saffron" href="/carte">La carte</a></li>
              <li><a className="hover:text-saffron" href="/panier">Panier</a></li>
              <li><a className="hover:text-saffron" href="/contact">Contact</a></li>
            </ul>
          </div>
          <div>
            <h2 className="font-display text-xl">Restaurant</h2>
            <p className="mt-3 text-sm leading-relaxed text-cream/75">{restaurant?.address ?? "24 rue Emmanuel Arago, 93130 Noisy-le-Sec"}</p>
            <p className="mt-3 text-sm text-cream/75">{restaurant?.hoursLabel}</p>
            <p className="mt-3 text-sm">
              <a className="hover:text-saffron" href={restaurant?.maps ?? "https://www.google.com/maps/dir/?api=1&destination=24+rue+Emmanuel+Arago+93130+Noisy-le-Sec"} target="_blank" rel="noopener noreferrer">Itinéraire</a>
            </p>
          </div>
          <div>
            <h2 className="font-display text-xl">Réseaux</h2>
            <ul className="mt-3 space-y-2 text-sm">
              <li><a className="hover:text-saffron" href={restaurant?.instagram ?? "https://www.instagram.com/alloko_drone/"} target="_blank" rel="noopener noreferrer">Instagram</a></li>
            </ul>
          </div>
        </div>
        <div className="border-t border-cream/15">
          <div className="mx-auto max-w-6xl px-4 py-4 text-xs text-cream/60">
            <p>© 2026 ALLOKODRONE. Tous droits réservés.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
