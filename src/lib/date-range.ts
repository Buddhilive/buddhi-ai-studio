export interface DateRange {
  start: Date;
  end: Date;
}

export type DateRangePreset = "today" | "7d" | "30d" | "all";

const ALL_TIME_START = new Date("2020-01-01T00:00:00Z");

export function presetToRange(preset: DateRangePreset, now: Date = new Date()): DateRange {
  const end = now;
  switch (preset) {
    case "today": {
      const start = new Date(now);
      start.setHours(0, 0, 0, 0);
      return { start, end };
    }
    case "7d":
      return { start: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000), end };
    case "30d":
      return { start: new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000), end };
    case "all":
      return { start: ALL_TIME_START, end };
  }
}

export function toApiParam(date: Date): string {
  return date.toISOString().slice(0, 19);
}

export function formatBucketLabel(iso: string, bucket: "hour" | "day"): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return bucket === "hour"
    ? date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric" })
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
