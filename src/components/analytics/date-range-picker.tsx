"use client";

import { useState } from "react";
import type { DateRange as DayPickerRange } from "react-day-picker";
import { CalendarIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { presetToRange, type DateRange, type DateRangePreset } from "@/lib/date-range";

const PRESETS: { key: DateRangePreset; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
  { key: "all", label: "All time" },
];

function formatRangeLabel(range: DateRange): string {
  const fmt = (d: Date) => d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  return `${fmt(range.start)} - ${fmt(range.end)}`;
}

export function DateRangePicker({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
}) {
  const [open, setOpen] = useState(false);

  const dayPickerValue: DayPickerRange = { from: value.start, to: value.end };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={<Button variant="outline" className={cn("justify-start gap-2 font-normal")} />}
      >
        <CalendarIcon className="size-4" />
        {formatRangeLabel(value)}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <div className="flex flex-col gap-2 p-3 sm:flex-row">
          <div className="flex flex-row gap-1 sm:flex-col">
            {PRESETS.map((preset) => (
              <Button
                key={preset.key}
                variant="ghost"
                size="sm"
                className="justify-start"
                onClick={() => {
                  onChange(presetToRange(preset.key));
                  setOpen(false);
                }}
              >
                {preset.label}
              </Button>
            ))}
          </div>
          <Calendar
            mode="range"
            selected={dayPickerValue}
            onSelect={(range) => {
              if (range?.from) {
                onChange({ start: range.from, end: range.to ?? range.from });
              }
            }}
            numberOfMonths={2}
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}
