import { useSyncExternalStore } from "react";
import type { PickupSlot } from "./types";

export type Collect = {
  mode: "pickup" | "delivery";
  asap: boolean;
  slotId: string;
  rue: string;
  codePostal: string;
  ville: string;
  feeLabel: string;
};

const KEY = "alloko-collect";
const fallback: Collect = {
  mode: "pickup",
  asap: true,
  slotId: "",
  rue: "",
  codePostal: "",
  ville: "",
  feeLabel: "",
};

function read(): Collect {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return fallback;
    const data = JSON.parse(raw) as Partial<Collect>;
    if (data.mode !== "pickup" && data.mode !== "delivery") return fallback;
    return {
      mode: data.mode,
      asap: data.asap !== false,
      slotId: typeof data.slotId === "string" ? data.slotId : "",
      rue: typeof data.rue === "string" ? data.rue : "",
      codePostal: typeof data.codePostal === "string" ? data.codePostal : "",
      ville: typeof data.ville === "string" ? data.ville : "",
      feeLabel: typeof data.feeLabel === "string" ? data.feeLabel : "",
    };
  } catch {
    return fallback;
  }
}

let current = read();
const listeners = new Set<() => void>();

function emit(next: Collect) {
  current = next;
  localStorage.setItem(KEY, JSON.stringify(next));
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useCollect() {
  return useSyncExternalStore(subscribe, () => current, () => fallback);
}

export function setCollect(next: Collect) {
  emit(next);
}

export function resolveSlot(slots: PickupSlot[], collect: Collect) {
  if (!collect.asap) {
    const kept = slots.find((slot) => String(slot.id) === collect.slotId);
    if (kept) return kept;
  }
  return slots[0] ?? null;
}

function hour(value: string) {
  return value.replace(":", "h");
}

export function slotDetail(slot: PickupSlot) {
  if (!slot.start || !slot.end) return slot.label;
  const range = `${hour(slot.start)} – ${hour(slot.end)}`;
  if (!slot.date) return range;
  const [year, month, day] = slot.date.split("-").map(Number);
  const now = new Date();
  const sameDay = now.getFullYear() === year && now.getMonth() + 1 === month && now.getDate() === day;
  if (sameDay) return range;
  const written = new Date(year, month - 1, day).toLocaleDateString("fr-FR", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  return `${written} · ${range}`;
}
