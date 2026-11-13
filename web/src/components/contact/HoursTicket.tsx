import { useEffect, useState } from "react";
import { Link } from "react-router";
import { formatHours, hoursStatus, WEEK } from "./hoursStatus";

function DroneMark() {
  return (
    <svg className="contact-ticket-logo" viewBox="0 0 64 40" aria-hidden="true">
      <path
        d="M10 14h10l4 4h16l4-4h10M14 14l-4-6M50 14l4-6M18 8h6M40 8h6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <ellipse cx="32" cy="26" rx="14" ry="8" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <path d="M24 26h16M28 22v8M36 22v8" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function HoursTicket({ deliveryOpen }: { deliveryOpen: boolean }) {
  const [status, setStatus] = useState(() => hoursStatus());

  useEffect(() => {
    const tick = () => setStatus(hoursStatus());
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="contact-ticket-wrap" id="horaires">
      <div className="contact-ticket">
        <span className="contact-stamp" aria-hidden="true">
          Fait maison
        </span>
        <header className="contact-ticket-head">
          <DroneMark />
          <div>
            <p className="contact-ticket-brand">AlloKoDrone</p>
            <p className="contact-ticket-place">Noisy-le-Sec</p>
          </div>
        </header>

        <h2 className="contact-ticket-title">Horaires</h2>
        <p className="contact-ticket-status" aria-live="polite">
          {status.text}
        </p>
        <div className="contact-ticket-rule" aria-hidden="true" />

        <ul className="contact-hours">
          {WEEK.map((day) => {
            const current = day.key === status.todayKey;
            return (
              <li key={day.key} className={current ? "is-today" : undefined}>
                <span className={current ? "contact-day-pill" : undefined}>{day.label}</span>
                <span className="contact-hours-dots" aria-hidden="true" />
                <time dateTime={`T${day.open}`}>
                  {formatHours(day.open)}–{formatHours(day.close)}
                </time>
              </li>
            );
          })}
        </ul>

        <div className="contact-ticket-rule" aria-hidden="true" />
        <div className="contact-ticket-notes">
          <p>Retrait au comptoir. Votre bowl est prêt à votre arrivée.</p>
          <p>
            {deliveryOpen
              ? "Livraison ouverte. Commandez, le drone s'occupe du reste."
              : "Livraison fermée pour le moment. Le retrait au comptoir reste possible."}
          </p>
          <Link className="contact-ticket-link" to="/carte">
            Voir la carte
          </Link>
        </div>

        <div className="contact-barcode" aria-hidden="true" />
        <p className="contact-thanks">Merci, à très vite !</p>
      </div>
    </div>
  );
}
