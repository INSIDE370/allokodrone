import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError } from "../api";
import { asset } from "../base";
import { ServiceBar } from "../ServiceBar";
import { useSession } from "../session";
import type { CatalogPayload, HomePayload, Product } from "../types";
import { Alert, Reveal, useTitle } from "../ui";

function shortName(name: string) {
  return name
    .replace(/^DKR Beef\s*[—–-]\s*/i, "DKR Beef")
    .replace(/\s*[—–-].*$/, "")
    .trim();
}

function isVeggie(product: Product) {
  return /veggie|végét|veget/i.test(`${product.name} ${product.description}`);
}

export function Home() {
  useTitle("Commander");
  const navigate = useNavigate();
  const { setCartCount, push } = useSession();
  const [data, setData] = useState<HomePayload | null>(null);
  const [catalog, setCatalog] = useState<CatalogPayload | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [pendingId, setPendingId] = useState<number | null>(null);

  useEffect(() => {
    const id = window.location.hash.replace("#", "");
    if (!id) return;
    document.getElementById(id)?.scrollIntoView({ behavior: "instant", block: "start" });
  }, [data, catalog]);

  useEffect(() => {
    let cancel = false;
    api<HomePayload>("/api/accueil")
      .then((payload) => {
        if (!cancel) setData(payload);
      })
      .catch((error: unknown) => {
        if (!cancel) setErrors([error instanceof ApiError ? error.message : "Connexion interrompue. Réessayez."]);
      });
    const loadCatalog = () => {
      api<CatalogPayload>("/api/catalogue")
        .then((payload) => {
          if (!cancel) setCatalog(payload);
        })
        .catch(() => {
          /* aperçu carte optionnel */
        });
    };
    const idle =
      "requestIdleCallback" in window
        ? window.requestIdleCallback(loadCatalog, { timeout: 1200 })
        : window.setTimeout(loadCatalog, 200);
    return () => {
      cancel = true;
      if ("cancelIdleCallback" in window && typeof idle === "number") {
        window.cancelIdleCallback(idle);
      } else {
        window.clearTimeout(idle);
      }
    };
  }, []);

  const featured = data?.featured ?? [];
  const lead = featured.find((item) => item.image) ?? featured[0];
  const signatures = featured.slice(0, 4);
  const restaurant = data?.restaurant;
  const openLabel = restaurant?.deliveryOpen ? "Ouvert" : "Retrait";
  const carteSections = (() => {
    const map = new Map<string, Product[]>();
    for (const product of catalog?.products ?? []) {
      const key = product.categoryName || "Autres";
      const list = map.get(key) ?? [];
      list.push(product);
      map.set(key, list);
    }
    return [...map.entries()].slice(0, 4);
  })();

  async function addProduct(product: Product) {
    if (!product.orderable || !product.priceConfirmed) {
      navigate(`/produit/${product.slug}`);
      return;
    }
    if (product.hasOptions) {
      navigate(`/produit/${product.slug}`);
      return;
    }
    setPendingId(product.id);
    try {
      const result = await api<{ cartCount: number }>("/api/panier/ajouter", {
        method: "POST",
        body: { produit: product.id, quantite: 1, choix: [], notes: "" },
      });
      setCartCount(result.cartCount);
      push(`${shortName(product.name)} ajouté au panier`);
    } catch (error: unknown) {
      setErrors([error instanceof ApiError ? error.message : "Connexion interrompue. Réessayez."]);
    } finally {
      setPendingId(null);
    }
  }

  return (
    <>
      <section id="accueil" className="home-hero cs-grain" aria-labelledby="home-hero-title">
        <div className="home-hero__stage">
          <div className="home-hero__bg" aria-hidden="true">
            <img
              src={`${import.meta.env.BASE_URL}images/burger-hero.jpg`}
              alt=""
              width={1310}
              height={831}
              fetchPriority="high"
              decoding="async"
            />
          </div>
          {lead ? (
            <span className="home-hero__tag">
              Signature · <b>{shortName(lead.name)}</b>
              {lead.priceLabel ? ` · ${lead.priceLabel}` : null}
            </span>
          ) : null}
          <div className="cs-wrap home-hero__inner">
            <p className="home-hero__eyebrow cs-k">Afro street food — Noisy-le-Sec (93)</p>
            <h1 id="home-hero-title" className="home-hero__title cs-big">
              L&apos;Afrique
              <br />
              <span className="out">servie à</span>
              <br />
              <span className="o">grande vitesse</span>
            </h1>
            <div className="home-hero__row">
              <p>
                Burgers yassa, bowls à composer, wings et alloko. Vous choisissez, vous personnalisez, vous retirez au
                comptoir.
              </p>
              <div>
                <small>Aujourd&apos;hui</small>
                <b className="home-hero__live">{openLabel}</b>
              </div>
              <div>
                <small>Retrait</small>
                <b>Au comptoir</b>
              </div>
              <div>
                <small>Spot</small>
                <b>24 rue E. Arago</b>
              </div>
              <Link className="cs-btn home-hero__cta" to="/carte">
                Commander à emporter <span className="ar">→</span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      <ServiceBar />

      {errors.length ? (
        <div className="cs-wrap pt-5">
          <Alert errors={errors} />
        </div>
      ) : null}

      <section id="signatures" className="cs-sec scroll-mt-28">
        <div className="cs-wrap">
          <Reveal>
            <div className="cs-head">
              <div>
                <div className="cs-idx">Notre signature</div>
                <h2 className="cs-big">Les signatures</h2>
              </div>
              <Link className="cs-ul" to="/carte">
                Toute la carte →
              </Link>
            </div>
            <div className="cs-drops">
              {signatures.map((product) => {
                const compose = product.hasOptions;
                return (
                  <article key={product.id} className="cs-drop">
                    <Link className="contents text-inherit no-underline" to={`/produit/${product.slug}`}>
                      <div className="cs-drop__top">
                        <span>{product.categoryName}</span>
                        <em>Signature</em>
                      </div>
                      <div className="cs-drop__ph">
                        {product.image ? (
                          <img src={product.image} alt={shortName(product.name)} loading="lazy" />
                        ) : null}
                      </div>
                      <h3>{shortName(product.name)}</h3>
                      <p>{product.description}</p>
                    </Link>
                    <div className="cs-drop__bt">
                      <span className="cs-drop__pr">{product.priceLabel || "—"}</span>
                      <button
                        className="cs-drop__add"
                        type="button"
                        disabled={pendingId === product.id}
                        onClick={() => void addProduct(product)}
                      >
                        {pendingId === product.id ? "…" : compose ? "Composer +" : "Ajouter +"}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </Reveal>
        </div>
      </section>

      <div className="overflow-hidden whitespace-nowrap border-y border-night bg-terracotta text-night" aria-hidden="true">
        <div className="cs-tick__track !py-[26px]" style={{ animationDuration: "30s" }}>
          {["Fait maison", "À emporter", "7 jours sur 7", "Noisy-le-Sec", "Fait maison", "À emporter", "7 jours sur 7", "Noisy-le-Sec"].map(
            (item, index) => (
              <span
                key={`${item}-${index}`}
                className="inline-flex items-center gap-11 pr-11 text-[clamp(46px,6vw,92px)] font-black uppercase leading-none tracking-[-0.03em] odd:text-transparent odd:[-webkit-text-stroke:1.5px_var(--color-night)]"
              >
                {item}
              </span>
            ),
          )}
        </div>
      </div>

      {lead ? (
        <section className="grid min-h-0 grid-cols-1 md:min-h-[720px] md:grid-cols-[1.15fr_0.85fr]">
          <div className="relative min-h-[320px] overflow-hidden md:min-h-0">
            {lead.image ? (
              <img className="absolute inset-0 h-full w-full object-cover" src={lead.image} alt={shortName(lead.name)} loading="lazy" />
            ) : null}
            <span className="absolute bottom-7 left-7 bg-cream px-4 py-3 text-[11px] font-bold uppercase tracking-[0.22em]">
              Focus
            </span>
          </div>
          <div className="cs-grain flex flex-col bg-night px-5 py-12 text-paper-2 sm:px-8 md:px-16 md:py-16">
            <span className="cs-idx !text-saffron">{lead.categoryName}</span>
            <h2 className="cs-big mt-5 text-[clamp(40px,10vw,88px)] text-cream">
              {shortName(lead.name).split(" ").map((word, index) => (
                <span key={`${word}-${index}`}>
                  {index > 0 ? <br /> : null}
                  {word}
                </span>
              ))}
              <small className="mt-4 block text-[0.22em] font-bold uppercase tracking-[0.3em] text-saffron">
                {lead.description.slice(0, 48)}
                {lead.description.length > 48 ? "…" : ""}
              </small>
            </h2>
            <p className="mt-8 max-w-[36ch] text-[15px] text-paper-2/70 sm:text-[15.5px]">{lead.description}</p>
            <div className="mt-auto flex flex-wrap items-center justify-between gap-5 pt-11">
              <span className="text-[40px] font-light tracking-[-0.03em] text-cream sm:text-[52px]">{lead.priceLabel}</span>
              <button className="cs-btn" type="button" disabled={pendingId === lead.id} onClick={() => void addProduct(lead)}>
                {lead.hasOptions ? "Composer" : "Ajouter au panier"} <span className="ar">→</span>
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <section id="bowl" className="cs-sec cs-grain scroll-mt-28 bg-night-2 text-paper-2">
        <div className="cs-wrap">
          <Reveal>
            <div className="cs-head">
              <div>
                <div className="cs-idx !text-saffron">Bowls à composer</div>
                <h2 className="cs-big mt-3.5 text-cream">
                  Votre bowl,
                  <br />
                  <span className="text-terracotta">votre façon</span>
                </h2>
              </div>
              <p className="max-w-[34ch] text-paper-2/70">Vous choisissez, vous personnalisez, vous retirez au comptoir.</p>
            </div>
            <div className="grid grid-cols-1 gap-0 border-t border-paper-2/15 sm:grid-cols-2 md:grid-cols-4">
              {[
                ["La base", "Riz blanc inclus · riz Jollof +1 €"],
                ["La viande", "Au choix"],
                ["La sauce", "Au choix"],
                ["Le side", "Au choix"],
              ].map(([title, text], index) => (
                <div
                  key={title}
                  className={`px-0 py-8 md:pr-8 ${index > 0 ? "border-t border-paper-2/15 sm:border-t-0 md:border-l md:border-paper-2/15 md:pl-8" : ""} ${index % 2 === 1 ? "sm:pl-6 md:pl-8" : ""} ${index >= 2 ? "sm:border-t sm:border-paper-2/15 md:border-t-0" : ""}`}
                >
                  <h3 className="text-xl font-black uppercase tracking-[-0.02em] text-cream sm:text-2xl">{title}</h3>
                  <p className="mt-1.5 text-[15px] text-paper-2/65">{text}</p>
                </div>
              ))}
            </div>
            <div className="mt-16 flex flex-wrap items-center justify-between gap-5 border-t border-paper-2/15 pt-8">
              <div>
                <small className="block text-[11px] font-bold uppercase tracking-[0.24em] text-paper-2/55">Bowl à composer</small>
                <span className="text-4xl font-black tracking-[-0.02em] text-saffron">13,90 €</span>
              </div>
              <Link className="cs-btn" to="/carte?categorie=bowls">
                Composer mon bowl <span className="ar">→</span>
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <section id="midi" className="cs-sec scroll-mt-28">
        <div className="cs-wrap">
          <Reveal>
            <div className="cs-head">
              <div>
                <div className="cs-idx">Le midi</div>
                <h2 className="cs-big">Menus midi</h2>
              </div>
              <p className="max-w-[30ch] text-ink-soft">Trois formules pour la pause déjeuner.</p>
            </div>
            <div className="border-t-2 border-ink">
              {[
                ["Bowl au choix + boisson", "Formule midi", "14,90 €"],
                ["Combo étudiant + boisson", "Formule midi", "9,90 €"],
                ["Spice Wings Combo", "Wings + side + boisson", "13,50 €"],
              ].map(([title, note, price]) => (
                <Link
                  key={title}
                  className="grid grid-cols-1 items-center gap-2 border-b border-line py-4 transition-[padding,background] hover:bg-terracotta/5 hover:pl-3 sm:grid-cols-[1fr_auto] sm:gap-6 md:gap-8 md:py-5"
                  to="/carte?categorie=midi"
                >
                  <span>
                    <span className="block text-[clamp(20px,5.5vw,42px)] font-black uppercase leading-none tracking-[-0.03em]">
                      {title}
                    </span>
                    <small className="mt-1 block text-[11px] font-bold uppercase tracking-[0.22em] text-ink-soft">{note}</small>
                  </span>
                  <span className="text-[clamp(26px,4vw,48px)] font-light tracking-[-0.03em] text-ink">
                    {price}
                  </span>
                </Link>
              ))}
            </div>
          </Reveal>
        </div>
      </section>

      {carteSections.length ? (
        <section id="carte-apercu" className="cs-sec cs-grain scroll-mt-28 bg-night text-paper-2">
          <div className="cs-wrap">
            <Reveal>
              <div className="cs-head !mb-8 md:!mb-10">
                <div>
                  <div className="cs-idx !text-saffron">La carte</div>
                  <h2 className="cs-big mt-3.5 text-cream">
                    Toute
                    <br />
                    la carte
                  </h2>
                </div>
                <Link className="cs-ul text-paper-2" to="/carte">
                  Voir la carte →
                </Link>
              </div>
              <div className="cs-carte">
                {carteSections.map(([name, products]) => (
                  <div key={name} className="cs-cat">
                    <h4>{name}</h4>
                    {products.slice(0, 6).map((product) => (
                      <Link key={product.id} className="cs-it" to={`/produit/${product.slug}`}>
                        <span>
                          <b>
                            {shortName(product.name)}
                            {isVeggie(product) ? <span className="cs-vg">Veggie</span> : null}
                          </b>
                          <em>{product.description}</em>
                        </span>
                        <span className="cs-it__p">{product.priceLabel || "—"}</span>
                      </Link>
                    ))}
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>
      ) : null}

      <section id="histoire" className="scroll-mt-28 py-14 md:py-20">
        <div className="cs-wrap grid items-center gap-8 md:grid-cols-2 md:gap-12">
          <Reveal>
            <div className="cs-idx">Histoire</div>
            <p className="cs-big mt-3 text-[clamp(40px,6vw,88px)] text-ink">
              La cuisine africaine <span className="text-terracotta">d&apos;aujourd&apos;hui.</span>
            </p>
            <p className="mt-3 max-w-[52ch] text-[15px] text-ink-soft">
              ALLOKODRONE, c&apos;est une cuisine africaine faite maison, inspirée des recettes qui accompagnent les repas de
              famille, les moments entre amis et les grandes occasions.
            </p>
            <p className="mt-3 max-w-[52ch] text-[15px] text-ink-soft">
              Notre carte met à l&apos;honneur des plats riches en caractère : viandes braisées, marinades travaillées, sauces
              parfumées et accompagnements emblématiques.
            </p>
            <div className="mt-6">
              <Link className="cs-ul" to="/concept">
                Le goût voyage autrement →
              </Link>
            </div>
          </Reveal>
          <Reveal>
            <div className="relative">
              <img
                className="aspect-[4/5] w-full object-cover"
                src={asset("images/bowl.jpg")}
                alt="Bowl ALLOKODRONE"
                loading="lazy"
              />
              <span className="absolute right-0 top-5 bg-terracotta px-4 py-2.5 text-[11px] font-bold uppercase tracking-[0.22em] text-white">
                Fait maison
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      <section id="avis" className="scroll-mt-28 border-y border-line py-14 md:py-20">
        <div className="cs-wrap">
          <Reveal>
            <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-[auto_1fr] md:gap-12">
              <span className="text-[88px] font-black leading-[0.7] text-terracotta md:text-[220px]" aria-hidden="true">
                “
              </span>
              <div>
                <div className="cs-idx">Ils ont goûté, ils témoignent</div>
                <blockquote className="mt-4 text-[clamp(24px,6vw,54px)] font-black uppercase leading-none tracking-[-0.03em]">
                  {restaurant?.review.quote ||
                    "Une vraie découverte ! Les saveurs sont au rendez-vous, le pulled beef yassa est incroyable et l'accueil est top."}
                </blockquote>
                <cite className="mt-6 block text-[11.5px] font-bold not-italic uppercase tracking-[0.24em] text-ink-soft">
                  <b className="text-ink">{restaurant?.review.author || "Sarah"}</b> —{" "}
                  {restaurant?.review.place || "Noisy-le-Sec"} · {restaurant?.review.source || "Google"} ·{" "}
                  <Link className="underline" to="/avis">
                    Tous les avis
                  </Link>
                </cite>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {restaurant ? (
        <section id="contact" className="cs-sec cs-grain scroll-mt-28 overflow-hidden bg-night text-paper-2">
          <div className="cs-wrap">
            <Reveal>
              <div className="cs-idx !text-saffron">Le spot</div>
              <div className="cs-big mt-4 text-[clamp(42px,12vw,210px)] text-cream">
                Noisy-<span className="cs-out text-transparent [-webkit-text-stroke:1.5px_var(--color-saffron)]">le-Sec</span>
              </div>
              <div className="mt-10 grid grid-cols-1 border-t border-paper-2/15 md:grid-cols-[1.2fr_1fr_1fr]">
                <div className="border-paper-2/15 py-10 md:border-r md:pr-9">
                  <h3 className="mb-4 text-[11px] font-bold uppercase tracking-[0.26em] text-saffron">Adresse</h3>
                  <p className="text-[26px] font-black uppercase leading-tight tracking-[-0.02em] text-cream">
                    {restaurant.address.replace(", ", "\n").split("\n").map((line) => (
                      <span key={line} className="block">
                        {line}
                      </span>
                    ))}
                  </p>
                  <div className="mt-8 flex flex-wrap gap-3.5">
                    <Link className="cs-btn" to="/carte">
                      Commander <span className="ar">→</span>
                    </Link>
                    <a className="cs-btn cs-btn-ln" href={restaurant.maps} target="_blank" rel="noopener noreferrer">
                      Itinéraire
                    </a>
                  </div>
                </div>
                <div className="border-paper-2/15 py-10 md:border-r md:px-9">
                  <h3 className="mb-4 text-[11px] font-bold uppercase tracking-[0.26em] text-saffron">Horaires</h3>
                  {(restaurant.hoursLines ?? [restaurant.hoursLabel]).map((line) => {
                    const [label, value] = line.split(" · ");
                    return (
                      <div key={line} className="flex justify-between gap-3 border-b border-paper-2/15 py-2.5 text-paper-2/80">
                        <span>{label}</span>
                        <span>{value || line}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="py-10 md:pl-9">
                  <h3 className="mb-4 text-[11px] font-bold uppercase tracking-[0.26em] text-saffron">Services</h3>
                  <div className="flex justify-between gap-3 border-b border-paper-2/15 py-2.5">
                    <span>Retrait au comptoir</span>
                    <em className="not-italic font-bold text-saffron">Disponible</em>
                  </div>
                  <div className="flex justify-between gap-3 border-b border-paper-2/15 py-2.5">
                    <span>Livraison</span>
                    <em className={`not-italic ${restaurant.deliveryOpen ? "font-bold text-saffron" : "font-medium text-paper-2/40"}`}>
                      {restaurant.deliveryOpen ? "Ouverte" : "Fermée pour le moment"}
                    </em>
                  </div>
                  <div className="flex justify-between gap-3 border-b border-paper-2/15 py-2.5">
                    <span>Instagram</span>
                    <a className="font-bold not-italic text-saffron" href={restaurant.instagram} target="_blank" rel="noopener noreferrer">
                      @alloko_drone
                    </a>
                  </div>
                </div>
              </div>
            </Reveal>
          </div>
        </section>
      ) : null}
    </>
  );
}
