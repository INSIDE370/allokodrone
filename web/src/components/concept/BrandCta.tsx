import { Link } from "react-router";
import { btn, btnLine } from "../../ui";
import { PinMark } from "./icons";

type BrandCtaProps = {
  slogan: string;
  address: string;
  mapsUrl?: string;
};

export function BrandCta({ slogan, address, mapsUrl }: BrandCtaProps) {
  return (
    <section className="mx-auto max-w-[68rem] px-4 pb-14 pt-8 sm:px-6 sm:pb-16 sm:pt-10 lg:px-8 lg:py-14">
      <div className="flex flex-col gap-7 sm:flex-row sm:items-center sm:gap-10 lg:gap-12">
        <img
          className="h-16 w-auto max-w-[11rem] object-contain object-left sm:h-20 sm:max-w-[13rem] lg:h-24 lg:max-w-[15rem]"
          src={`${import.meta.env.BASE_URL}images/logo-dark.png`}
          width={532}
          height={299}
          alt="ALLOKODRONE"
          decoding="async"
          loading="lazy"
        />
        <div className="min-w-0 flex-1">
          <p className="max-w-xl font-display text-[1.55rem] font-semibold leading-[1.2] tracking-[-0.02em] text-ink sm:text-[1.85rem] lg:text-[2.05rem]">
            {slogan}
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Link className={`${btn} w-full sm:w-auto`} to="/carte">
              Voir la carte →
            </Link>
            <Link className={`${btnLine} w-full border-ink/25 bg-cream sm:w-auto`} to="/contact">
              Nous trouver
            </Link>
          </div>
          {mapsUrl ? (
            <a
              className="mt-6 inline-flex max-w-full items-start gap-2.5 text-[0.95rem] leading-snug text-ink transition-colors hover:text-terracotta"
              href={mapsUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <PinMark className="mt-0.5 h-4 w-4 shrink-0 text-terracotta" />
              <span className="min-w-0">{address}</span>
            </a>
          ) : (
            <p className="mt-6 flex max-w-full items-start gap-2.5 text-[0.95rem] leading-snug text-ink">
              <PinMark className="mt-0.5 h-4 w-4 shrink-0 text-terracotta" />
              <span className="min-w-0">{address}</span>
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
