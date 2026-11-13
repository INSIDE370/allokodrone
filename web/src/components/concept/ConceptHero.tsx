type ConceptPoint = {
  title: string;
  body: string;
};

type ConceptHeroProps = {
  eyebrow?: string;
  title: string;
  lead: string;
  points?: readonly ConceptPoint[];
  imageAlt: string;
  imageSrc?: string;
  imageWidth?: number;
  imageHeight?: number;
};

const ALT_DEFAULT =
  "Bowl AlloKoDrone avec poulet effiloché, oignons caramélisés, riz et plantains frits";

const DEFAULT_POINTS = [
  {
    title: "Fait maison",
    body: "Recettes de famille, préparées avec soin.",
  },
  {
    title: "Saveurs africaines",
    body: "Viandes braisées, sauces parfumées, alloko.",
  },
  {
    title: "Service rapide",
    body: "Retrait au comptoir ou livraison.",
  },
] as const;

export function ConceptHero({
  eyebrow = "Notre concept",
  title,
  lead,
  points = DEFAULT_POINTS,
  imageAlt = ALT_DEFAULT,
  imageSrc = "/images/bowl-concept.png",
  imageWidth = 1024,
  imageHeight = 603,
}: ConceptHeroProps) {
  const titleId = "concept-title";

  return (
    <section
      className="concept-reveal mx-auto max-w-[78rem] px-4 py-8 sm:px-6 sm:py-10 lg:px-8 lg:py-12"
      aria-labelledby={titleId}
    >
      <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.35fr)] lg:gap-10 xl:gap-12">
        <div className="order-2 lg:order-1">
          <p className="text-[0.7rem] font-semibold uppercase tracking-[0.2em] text-terracotta">
            {eyebrow}
          </p>
          <h1
            id={titleId}
            className="mt-2 max-w-[15ch] font-display text-[clamp(2.15rem,4.2vw,3.15rem)] font-semibold leading-[0.95] tracking-[-0.03em] text-ink"
          >
            {title === "Le goût voyage autrement" ? (
              <>
                Le goût voyage
                <br />
                autrement
              </>
            ) : (
              title
            )}
          </h1>
          <p className="mt-4 max-w-[32rem] text-base leading-[1.6] text-ink">
            {lead}
          </p>
          <ul className="mt-6 space-y-5">
            {points.map((point) => (
              <li key={point.title}>
                <p className="font-display text-[1.05rem] font-semibold leading-tight tracking-[-0.02em] text-ink">
                  {point.title}
                </p>
                <p className="mt-1 text-[0.95rem] leading-[1.55] text-ink-soft">{point.body}</p>
              </li>
            ))}
          </ul>
        </div>

        <figure className="order-1 m-0 w-full overflow-visible justify-self-stretch lg:order-2 lg:-mr-2">
          <img
            className="concept-bowl-img"
            src={imageSrc}
            width={imageWidth}
            height={imageHeight}
            alt={imageAlt}
            decoding="async"
            fetchPriority="high"
          />
        </figure>
      </div>
    </section>
  );
}
