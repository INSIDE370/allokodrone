import { TriangleMark } from "./icons";

export type ConceptValue = {
  title: string;
  body: string;
};

export function ValueGrid({ values }: { values: readonly ConceptValue[] }) {
  return (
    <section className="mx-auto max-w-[78rem] px-4 pb-10 sm:px-6 lg:px-8 lg:pb-14">
      <ul className="grid gap-9 sm:grid-cols-3 sm:gap-6 lg:gap-10">
        {values.map((value) => (
          <li key={value.title} className="flex gap-3">
            <TriangleMark />
            <div>
              <h2 className="font-display text-[1.35rem] font-semibold leading-tight tracking-[-0.02em] text-ink sm:text-[1.55rem]">
                {value.title}
              </h2>
              <p className="mt-2.5 text-sm leading-relaxed text-ink-soft sm:text-[0.95rem] sm:leading-[1.6]">
                {value.body}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
