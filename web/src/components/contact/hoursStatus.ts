const PARIS = "Europe/Paris";

function partsInParis(date = new Date()) {
  const fmt = new Intl.DateTimeFormat("en-GB", {
    timeZone: PARIS,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const bits = Object.fromEntries(fmt.formatToParts(date).map((part) => [part.type, part.value]));
  const weekday = (bits.weekday || "Mon").slice(0, 3);
  const hour = Number(bits.hour);
  const minute = Number(bits.minute);
  return { weekday, minutes: hour * 60 + minute };
}

function parseClock(value: string) {
  const [h, m] = value.split(":").map(Number);
  return h * 60 + m;
}

export type DayHours = {
  key: string;
  label: string;
  open: string;
  close: string;
};

export const WEEK: DayHours[] = [
  { key: "Mon", label: "Lundi", open: "11:30", close: "22:30" },
  { key: "Tue", label: "Mardi", open: "11:30", close: "22:30" },
  { key: "Wed", label: "Mercredi", open: "11:30", close: "22:30" },
  { key: "Thu", label: "Jeudi", open: "11:30", close: "22:30" },
  { key: "Fri", label: "Vendredi", open: "11:30", close: "22:30" },
  { key: "Sat", label: "Samedi", open: "11:30", close: "22:30" },
  { key: "Sun", label: "Dimanche", open: "17:00", close: "22:30" },
];

function clockLabel(value: string) {
  return value.replace(":", "h");
}

export function hoursStatus(now = new Date()) {
  const { weekday, minutes } = partsInParis(now);
  const day = WEEK.find((row) => row.key === weekday) || WEEK[0];
  const open = parseClock(day.open);
  const close = parseClock(day.close);
  const openNow = minutes >= open && minutes < close;
  if (openNow) {
    return {
      open: true,
      todayKey: day.key,
      text: `Ouvert maintenant, jusqu'à ${clockLabel(day.close)}`,
    };
  }
  if (minutes < open) {
    return {
      open: false,
      todayKey: day.key,
      text: `Fermé, ouvre à ${clockLabel(day.open)}`,
    };
  }
  const index = WEEK.findIndex((row) => row.key === day.key);
  const next = WEEK[(index + 1) % WEEK.length];
  return {
    open: false,
    todayKey: day.key,
    text: `Fermé, ouvre ${next.label.toLowerCase()} à ${clockLabel(next.open)}`,
  };
}

export function formatHours(value: string) {
  return clockLabel(value);
}
