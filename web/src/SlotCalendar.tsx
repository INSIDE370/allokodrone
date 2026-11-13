import { useMemo, useState } from "react";

type Slot = { id: number; label: string; date?: string; start?: string; end?: string };

const WEEKDAYS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"];
const MONTHS = [
  "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

function parts(slot: Slot) {
  if (slot.date && slot.start && slot.end) return { date: slot.date, start: slot.start, end: slot.end };
  const match = slot.label.match(/^(\d{4}-\d{2}-\d{2}) · (\d{2}:\d{2})[–-](\d{2}:\d{2})$/);
  if (!match) return null;
  return { date: match[1], start: match[2], end: match[3] };
}

function iso(year: number, month: number, day: number) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function hour(value: string) {
  return value.replace(":", "h");
}

export function SlotCalendar({
  slots,
  selectedId,
  onSelect,
}: {
  slots: Slot[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const today = new Date();
  const todayKey = iso(today.getFullYear(), today.getMonth() + 1, today.getDate());
  const rows = useMemo(
    () => slots.flatMap((slot) => {
      const when = parts(slot);
      return when ? [{ id: slot.id, ...when }] : [];
    }),
    [slots],
  );
  const byDay = useMemo(() => {
    const map = new Map<string, { id: number; start: string; end: string }[]>();
    for (const row of rows) {
      const list = map.get(row.date) ?? [];
      list.push({ id: row.id, start: row.start, end: row.end });
      map.set(row.date, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.start.localeCompare(b.start));
    return map;
  }, [rows]);

  const selected = rows.find((row) => String(row.id) === selectedId);
  const [cursor, setCursor] = useState(() => {
    const source = selected?.date ?? todayKey;
    const [year, month] = source.split("-").map(Number);
    return { year, month };
  });
  const [day, setDay] = useState(selected?.date ?? "");

  const first = (cursor.year - today.getFullYear()) * 12 + (cursor.month - (today.getMonth() + 1));
  const lastSlot = rows.reduce((max, row) => (row.date > max ? row.date : max), "");
  const lastIndex = lastSlot
    ? (Number(lastSlot.slice(0, 4)) - today.getFullYear()) * 12 + (Number(lastSlot.slice(5, 7)) - (today.getMonth() + 1))
    : 0;
  const canPrev = first > 0;
  const canNext = first < lastIndex;

  const offset = (new Date(cursor.year, cursor.month - 1, 1).getDay() + 6) % 7;
  const count = new Date(cursor.year, cursor.month, 0).getDate();
  const cells: (number | null)[] = Array.from({ length: offset }, () => null);
  for (let dayNumber = 1; dayNumber <= count; dayNumber += 1) cells.push(dayNumber);
  while (cells.length % 7) cells.push(null);

  const times = day ? byDay.get(day) ?? [] : [];

  function pickDay(date: string) {
    setDay(date);
    if (!timesOf(date).some((slot) => String(slot.id) === selectedId)) onSelect("");
  }

  function timesOf(date: string) {
    return byDay.get(date) ?? [];
  }

  return (
    <div className="mt-3">
      <div className="flex items-center justify-between gap-3">
        <button
          className="h-11 w-11 border border-line text-lg disabled:cursor-not-allowed disabled:opacity-30"
          type="button"
          aria-label="Mois précédent"
          disabled={!canPrev}
          onClick={() => setCursor((current) => current.month === 1 ? { year: current.year - 1, month: 12 } : { year: current.year, month: current.month - 1 })}
        >
          ←
        </button>
        <p className="font-display text-2xl capitalize">{MONTHS[cursor.month - 1]} {cursor.year}</p>
        <button
          className="h-11 w-11 border border-line text-lg disabled:cursor-not-allowed disabled:opacity-30"
          type="button"
          aria-label="Mois suivant"
          disabled={!canNext}
          onClick={() => setCursor((current) => current.month === 12 ? { year: current.year + 1, month: 1 } : { year: current.year, month: current.month + 1 })}
        >
          →
        </button>
      </div>
      <div className="mt-3 grid grid-cols-7 gap-1 text-center text-xs uppercase tracking-wide text-ink-soft" aria-hidden="true">
        {WEEKDAYS.map((name) => <span key={name} className="py-1">{name}</span>)}
      </div>
      <div className="grid grid-cols-7 gap-1" role="grid" aria-label="Jours de retrait">
        {cells.map((dayNumber, index) => {
          if (!dayNumber) return <span key={`empty-${index}`} />;
          const date = iso(cursor.year, cursor.month, dayNumber);
          const open = timesOf(date).length > 0;
          const active = date === day;
          const spoken = new Date(cursor.year, cursor.month - 1, dayNumber).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
          return (
            <button
              key={date}
              className={`h-11 text-sm ${active ? "bg-terracotta text-white" : open ? "border border-line hover:border-ink" : "cursor-not-allowed text-ink-soft/35"}`}
              type="button"
              role="gridcell"
              disabled={!open}
              aria-pressed={active}
              aria-label={`${spoken}${open ? ", disponible" : ", indisponible"}`}
              onClick={() => pickDay(date)}
            >
              {dayNumber}
            </button>
          );
        })}
      </div>
      {day ? (
        <div className="mt-4">
          <p className="text-sm capitalize">{new Date(Number(day.slice(0, 4)), Number(day.slice(5, 7)) - 1, Number(day.slice(8, 10))).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}</p>
          {times.length ? (
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Horaires disponibles">
              {times.map((slot) => {
                const active = String(slot.id) === selectedId;
                return (
                  <button
                    key={slot.id}
                    className={`h-11 px-3 text-sm ${active ? "border border-ink bg-paper-2" : "border border-line hover:border-ink"}`}
                    type="button"
                    aria-pressed={active}
                    onClick={() => onSelect(String(slot.id))}
                  >
                    {hour(slot.start)}–{hour(slot.end)}
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="mt-2 text-sm text-ink-soft">Aucun horaire ce jour-là.</p>
          )}
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink-soft">Choisissez un jour disponible, puis un horaire.</p>
      )}
    </div>
  );
}
