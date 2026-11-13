import { useEffect } from "react";
import { ContactMap } from "../components/contact/ContactMap";
import { ContactSteps } from "../components/contact/ContactSteps";
import { HoursTicket } from "../components/contact/HoursTicket";
import { useSession } from "../session";
import { Pending, useTitle } from "../ui";

export function Contact() {
  useTitle("Contact");
  const { session } = useSession();
  const restaurant = session?.restaurant;

  useEffect(() => {
    if (!restaurant || window.location.hash !== "#horaires") return;
    document.getElementById("horaires")?.scrollIntoView();
  }, [restaurant]);

  if (!restaurant) {
    return (
      <div className="mx-auto max-w-3xl px-4">
        <Pending label="Chargement" />
      </div>
    );
  }

  const street = "24 rue Emmanuel Arago";
  const city = "93130 Noisy-le-Sec";
  const deliveryLine = restaurant.deliveryOpen
    ? "Le retrait se fait au comptoir. La livraison est ouverte."
    : "Le retrait se fait au comptoir. La livraison est fermée.";

  return (
    <article className="contact-page">
      <div className="contact-shell">
        <div className="contact-hero-grid">
          <div className="contact-copy">
            <h1 className="contact-kicker">Nous trouver</h1>
            <address className="contact-address">
              <span className="contact-street">{street}</span>
              <span className="contact-city">{city}</span>
            </address>
            <p className="contact-lead">{deliveryLine}</p>
            <div className="contact-actions">
              <a className="contact-btn" href={restaurant.maps}>
                Itinéraire
              </a>
              <a
                className="contact-ig"
                href={restaurant.instagram}
                target="_blank"
                rel="noopener noreferrer"
              >
                Instagram
              </a>
            </div>
          </div>
          <HoursTicket deliveryOpen={restaurant.deliveryOpen} />
        </div>

        <ContactMap />
        <ContactSteps />
      </div>
    </article>
  );
}
