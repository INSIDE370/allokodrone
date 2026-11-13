import type { ReactNode } from "react";

export function QuoteBand({ children }: { children: ReactNode }) {
  return (
    <section className="bg-paper px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
      <div className="mx-auto max-w-[68rem] rounded-2xl bg-night px-5 py-6 text-cream sm:rounded-3xl sm:px-7 sm:py-6 lg:px-8 lg:py-7">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-5">
          <div className="flex shrink-0 items-center gap-3">
            <span
              className="font-display text-[2.4rem] leading-none text-terracotta sm:text-[3rem]"
              aria-hidden="true"
            >
              “
            </span>
            <span className="hidden h-12 w-px bg-terracotta sm:block" aria-hidden="true" />
          </div>
          <p className="min-w-0 text-[1.05rem] font-medium leading-[1.55] tracking-[-0.01em] text-cream sm:text-[1.1rem] sm:leading-[1.5] lg:text-[1.2rem]">
            {children}
          </p>
        </div>
      </div>
    </section>
  );
}
