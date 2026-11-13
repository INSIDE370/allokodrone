import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError } from "./api";
import { useSession } from "./session";
import type { Product } from "./types";
import { btn, btnLine } from "./ui";

export function ProductAction({ product, className = "" }: { product: Product; className?: string }) {
  const navigate = useNavigate();
  const { setCartCount } = useSession();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const href = `/produit/${product.slug}`;
  const ready = product.available && product.orderable;
  const quick = ready && product.priceConfirmed && product.hasOptions === false;
  const customize = ready && product.hasOptions === true;

  async function add() {
    setPending(true);
    setError("");
    try {
      const result = await api<{ cartCount: number }>("/api/panier/ajouter", {
        method: "POST",
        body: { produit: product.id, quantite: 1, choix: [], notes: "" },
      });
      setCartCount(result.cartCount);
      navigate("/panier");
    } catch (caught: unknown) {
      const message = caught instanceof ApiError ? caught.errors[0] : "Connexion interrompue. Réessayez.";
      setError(message || "Connexion interrompue. Réessayez.");
      setPending(false);
    }
  }

  return (
    <div>
      {error ? (
        <p className="mb-2 text-xs leading-relaxed text-terracotta-deep" role="alert">
          {error}
        </p>
      ) : null}
      {quick ? (
        <button className={`${btn} ${className}`} type="button" disabled={pending} aria-busy={pending} onClick={() => void add()}>
          {pending ? "Ajout…" : "Ajouter au panier"}
        </button>
      ) : (
        <Link className={`${customize ? btn : btnLine} ${className}`} to={href}>
          {customize ? "Personnaliser" : "Voir le plat"}
        </Link>
      )}
    </div>
  );
}

const CATEGORY_IMAGES: Record<string, string> = {
  burgers: "/images/burger.jpg",
  bowls: "/images/bowl.jpg",
  sides: "/images/wings.jpg",
  plats: "/images/bowl.jpg",
  boissons: "/images/alloko.jpg",
  desserts: "/images/alloko.jpg",
  midi: "/images/bowl.jpg",
};

export function DishCard({ product, badge = true }: { product: Product; badge?: boolean }) {
  const href = `/produit/${product.slug}`;
  const crop = product.slug === "bowl" || product.categorySlug === "plats" || product.categorySlug === "midi" || product.categorySlug === "bowls"
    ? "object-[center_22%]"
    : "object-center";
  const image = product.image || CATEGORY_IMAGES[product.categorySlug] || null;

  return (
    <article
      className={`flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-cream transition duration-300 hover:-translate-y-0.5 hover:border-terracotta/40 ${product.available ? "" : "opacity-80"}`}
    >
      <Link className="group flex min-h-0 flex-1 flex-col" to={href}>
        <span className="relative block aspect-[4/3] overflow-hidden bg-paper-2">
          {image ? (
            <img
              className={`h-full w-full max-w-full object-cover transition duration-500 ease-out group-hover:scale-[1.04] ${crop}`}
              src={image}
              alt={product.name}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span className="flex h-full items-center justify-center bg-paper-2 font-display text-4xl text-terracotta/80" aria-hidden="true">
              {product.name.trim().charAt(0)}
            </span>
          )}
          {(badge && product.featured) || !product.available ? (
            <span className="absolute left-2.5 top-2.5 flex flex-wrap gap-1.5">
              {badge && product.featured ? (
                <span className="bg-night/90 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-cream">
                  Signature
                </span>
              ) : null}
              {!product.available ? (
                <span className="bg-cream px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-terracotta-deep">
                  Indisponible
                </span>
              ) : null}
            </span>
          ) : null}
        </span>
        <span className="flex flex-1 flex-col px-3 pt-3 sm:px-4">
          <h3 className="font-display text-xl leading-tight text-ink transition-colors duration-300 group-hover:text-terracotta sm:text-2xl">
            {product.name}
          </h3>
          <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-ink-soft sm:line-clamp-3 sm:text-sm">
            {product.description}
          </p>
          {product.availability ? (
            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-terracotta-deep">{product.availability}</p>
          ) : null}
          <p className="mt-auto pt-3 font-display text-xl tabular-nums tracking-tight text-terracotta sm:text-2xl">
            {product.priceLabel}
          </p>
        </span>
      </Link>
      <div className="px-3 pt-3 pb-3 sm:px-4 sm:pb-4">
        <ProductAction product={product} className="w-full px-3 text-center" />
      </div>
    </article>
  );
}
