import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { asset } from "./base";
import { CalendarMark, InstagramMark, PinMark, PlaneMark } from "./components/brand/Marks";
import { PromotionPopup } from "./components/PromotionPopup";
import { ServiceBar } from "./ServiceBar";
import { useSession } from "./session";

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

function Item({ to, children, className = "", end }: { to: string; children: React.ReactNode; className?: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `text-[11.5px] font-bold uppercase tracking-[0.22em] transition-opacity duration-200 hover:opacity-100 ${className} ${
          isActive ? "opacity-100 text-saffron" : "opacity-70 text-paper-2"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

const TICKER = [
  "Afro street food",
  "Noisy-le-Sec (93)",
  "Click & collect",
  "Ouvert 7j/7",
  "Fait maison",
  "Burgers yassa · bowls · wings · alloko",
];

export function Shell() {
  const { session, error, refresh } = useSession();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const count = session?.cartCount ?? 0;
  const restaurant = session?.restaurant;
  const home = pathname === "/";
  const entries: [string, React.ReactNode][] = [
    ["/", "Accueil"],
    ["/signature", "Signatures"],
    ["/carte", "La carte"],
    ["/avis", "Avis"],
    ["/contact", "Le spot"],
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

  return (
    <div className="flex min-h-screen flex-col overflow-x-clip bg-paper font-sans text-ink antialiased">
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:bg-cream focus:px-3 focus:py-2"
        href="#contenu"
      >
        Aller au contenu
      </a>

      <div className="cs-tick" aria-hidden="true">
        <div className="cs-tick__track">
          {TICKER.map((item) => (
            <span key={`a-${item}`}>{item}</span>
          ))}
          {TICKER.map((item) => (
            <span key={`b-${item}`}>{item}</span>
          ))}
        </div>
      </div>

      <header className="relative sticky top-0 z-50 shrink-0 border-b border-paper-2/15 bg-night text-paper-2">
        <div className="cs-wrap flex h-20 items-center justify-between gap-4 md:h-[94px]">
          <Link className="flex h-[66px] w-auto shrink-0 items-center overflow-hidden md:h-20" to="/">
            <img
              className="max-h-full w-auto max-w-[11rem] object-contain object-left md:max-w-[13rem]"
              src={asset("images/logo-light.png")}
              width="176"
              height="99"
              alt="ALLOKODRONE — L'Afrique servie à grande vitesse"
            />
          </Link>

          <nav className="hidden min-w-0 flex-1 lg:block" aria-label="Navigation principale">
            <ul className="flex items-center justify-center gap-7 xl:gap-8">
              {entries.map(([to, label]) => (
                <li key={to}>
                  <Item to={to} end={to === "/"}>
                    {label}
                  </Item>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex shrink-0 items-center gap-2">
            <NavLink
              to="/panier"
              className={({ isActive }) =>
                `inline-flex h-11 min-w-11 items-center justify-center gap-2 rounded-full border border-paper-2/25 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-paper-2 transition-colors hover:border-paper-2 sm:px-4 ${
                  isActive ? "border-saffron text-saffron" : ""
                }`
              }
              aria-label={count > 0 ? `Panier, ${count} article${count > 1 ? "s" : ""}` : "Panier"}
            >
              <BasketMark />
              <span className="hidden sm:inline">Panier</span>
              {count > 0 ? <span className="tabular-nums text-saffron">{count}</span> : null}
            </NavLink>
            <Link className="cs-btn hidden !px-[22px] !py-3.5 lg:inline-flex" to={count > 0 ? "/panier" : "/carte"}>
              Commander <span className="ar">→</span>
            </Link>
            <button
              className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-paper-2/20 text-paper-2 lg:hidden"
              type="button"
              aria-expanded={menuOpen}
              aria-controls="menu-mobile"
              aria-label={menuOpen ? "Fermer le menu" : "Ouvrir le menu"}
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? "✕" : "☰"}
            </button>
          </div>
        </div>

        <nav
          id="menu-mobile"
          className={`${menuOpen ? "flex" : "hidden"} absolute left-0 right-0 top-full flex-col gap-4 border-b border-paper-2/15 bg-night px-6 py-6 lg:hidden`}
          aria-label="Sections"
        >
          {entries.map(([to, label]) => (
            <Item key={to} className="!text-sm !opacity-90" to={to} end={to === "/"}>
              {label}
            </Item>
          ))}
          <Link className="cs-btn mt-2 w-fit" to={count > 0 ? "/panier" : "/carte"}>
            Commander <span className="ar">→</span>
          </Link>
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

      {!home ? <ServiceBar /> : null}

      <main id="contenu" className="relative z-0 min-w-0 flex-1">
        <div key={pathname} className="motion-fade">
          <Outlet />
        </div>
      </main>

      <footer className="site-footer relative z-0 mt-auto overflow-hidden bg-black text-paper-2/70">
        <div className="cs-wrap grid grid-cols-1 gap-10 pt-10 pb-8 sm:grid-cols-2 md:grid-cols-4 md:gap-8 md:pt-14 md:pb-10">
          <div>
            <Link to="/" className="inline-block shrink-0">
              <img className="w-[150px] max-w-full md:w-[170px]" src={asset("images/logo-light.png")} width="200" height="112" alt="ALLOKODRONE" />
            </Link>
          </div>

          <nav className="flex flex-col gap-3 text-[15px] text-paper-2/80" aria-label="Pied de page">
            <Link className="hover:text-saffron" to="/carte">
              La carte
            </Link>
            <Link className="hover:text-saffron" to="/panier">
              Panier
            </Link>
            <Link className="hover:text-saffron" to="/contact">
              Contact
            </Link>
          </nav>

          <div>
            <h3 className="text-[15px] font-bold text-paper-2">Restaurant</h3>
            <ul className="mt-4 space-y-3 text-sm text-paper-2/75">
              <li className="flex items-start gap-2.5">
                <PinMark className="mt-0.5 h-4 w-4 shrink-0 text-terracotta" />
                <span>{restaurant?.address ?? "24 rue Emmanuel Arago, 93130 Noisy-le-Sec"}</span>
              </li>
              {(
                restaurant?.hoursLines ?? [
                  "Lundi – samedi : 11h30 – 22h30",
                  "Dimanche : 17h00 – 22h30",
                ]
              )
                .filter(Boolean)
                .map((line) => (
                  <li key={String(line)} className="flex items-start gap-2.5">
                    <CalendarMark className="mt-0.5 h-4 w-4 shrink-0 text-terracotta" />
                    <span>{String(line).replace(/ · /g, " : ")}</span>
                  </li>
                ))}
              <li>
                <a
                  className="inline-flex items-center gap-2.5 hover:text-saffron"
                  href={
                    restaurant?.maps ??
                    "https://www.google.com/maps/dir/?api=1&destination=24+rue+Emmanuel+Arago+93130+Noisy-le-Sec"
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <PlaneMark className="h-4 w-4 shrink-0 text-terracotta" />
                  Itinéraire
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-[15px] font-bold text-paper-2">Réseaux</h3>
            <a
              className="mt-4 inline-flex items-center gap-2.5 text-sm text-paper-2/75 hover:text-saffron"
              href={restaurant?.instagram ?? "https://www.instagram.com/alloko_drone/"}
              target="_blank"
              rel="noopener noreferrer"
            >
              <InstagramMark className="h-4 w-4 shrink-0 text-terracotta" />
              Instagram
            </a>
          </div>
        </div>

        <div className="cs-wrap border-t border-paper-2/15 py-5 text-xs tracking-[0.06em] text-paper-2/45">
          © 2026 ALLOKODRONE. Tous droits réservés.
        </div>

        <div className="cs-foot-marquee" aria-hidden="true">
          <div className="cs-foot-marquee__track">
            {Array.from({ length: 4 }, (_, index) => (
              <span key={index} className="cs-foot-marquee__item">
                L&apos;Afrique servie à grande vitesse
              </span>
            ))}
          </div>
        </div>
      </footer>

      <PromotionPopup pathname={pathname} />
    </div>
  );
}
