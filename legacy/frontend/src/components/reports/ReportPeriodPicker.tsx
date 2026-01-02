import React, { useMemo, useState } from "react";

export type PeriodPreset =
  | "this_month"
  | "last_month"
  | "last_3_months"
  | "last_6_months"
  | "last_year"
  | "last_30_days"
  | "last_90_days"
  | "custom"
  | string;

export type CompareTo = "previous_period" | "previous_year" | "none" | string;

export interface PeriodSelection {
  preset: PeriodPreset;
  startDate?: string;
  endDate?: string;
  compareTo?: CompareTo;
}

interface ReportPeriodPickerProps {
  preset?: PeriodPreset;
  startDate?: string;
  endDate?: string;
  compareTo?: CompareTo;
  onChange?: (selection: PeriodSelection) => void;
  onApply?: (selection: PeriodSelection) => void;
  className?: string;
  compact?: boolean;
}

const PRESETS: Array<{ value: PeriodPreset; label: string }> = [
  { value: "this_month", label: "This Month" },
  { value: "last_month", label: "Last Month" },
  { value: "last_3_months", label: "Last 3 Months" },
  { value: "last_6_months", label: "Last 6 Months" },
  { value: "this_quarter", label: "This Quarter" },
  { value: "last_quarter", label: "Last Quarter" },
  { value: "this_year", label: "Year to Date" },
  { value: "last_year", label: "Last Year" },
  { value: "last_30_days", label: "Last 30 Days" },
  { value: "last_90_days", label: "Last 90 Days" },
  { value: "custom", label: "Custom Range" },
];

const COMPARE_OPTIONS: Array<{ value: CompareTo; label: string }> = [
  { value: "previous_period", label: "Previous period" },
  { value: "previous_year", label: "Previous year" },
  { value: "none", label: "Off" },
];

export const ReportPeriodPicker: React.FC<ReportPeriodPickerProps> = ({
  preset = "this_month",
  startDate = "",
  endDate = "",
  compareTo = "previous_period",
  onChange,
  onApply,
  className,
  compact = false,
}) => {
  const initialPreset: PeriodPreset = preset || (startDate || endDate ? "custom" : "this_month");
  const [currentPreset, setCurrentPreset] = useState<PeriodPreset>(initialPreset);
  const [customStart, setCustomStart] = useState(startDate);
  const [customEnd, setCustomEnd] = useState(endDate);
  const [comparison, setComparison] = useState<CompareTo>(compareTo);

  const selection = useMemo<PeriodSelection>(
    () => ({
      preset: currentPreset,
      startDate: currentPreset === "custom" ? customStart : undefined,
      endDate: currentPreset === "custom" ? customEnd : undefined,
      compareTo: comparison,
    }),
    [comparison, currentPreset, customEnd, customStart]
  );

  const emitChange = (next: PeriodSelection) => {
    onChange?.(next);
  };

  const handlePresetChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as PeriodPreset;
    setCurrentPreset(value);
    if (value !== "custom") {
      emitChange({ preset: value, compareTo: comparison });
    }
  };

  const handleCompareChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value as CompareTo;
    setComparison(value);
    emitChange({ ...selection, compareTo: value });
  };

  const handleApply = () => {
    const payload = { ...selection };
    emitChange(payload);
    onApply?.(payload);
  };

  const currentPresetLabel = PRESETS.find((p) => p.value === currentPreset)?.label || "Select period";
  const currentCompareLabel = COMPARE_OPTIONS.find((c) => c.value === comparison)?.label || "Off";

  return (
    <div className={`flex flex-wrap items-center gap-3 ${className || ""}`}>
      {/* Period Dropdown */}
      <div className="flex items-center gap-2">
        <label className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
          Period
        </label>
        <select
          value={currentPreset}
          onChange={handlePresetChange}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-800 shadow-sm transition hover:border-slate-300 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-300"
        >
          {PRESETS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Custom Date Range */}
      {currentPreset === "custom" && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            value={customStart}
            onChange={(e) => setCustomStart(e.target.value)}
            className="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] text-slate-700 focus:border-slate-400 focus:outline-none"
          />
          <span className="text-slate-400">–</span>
          <input
            type="date"
            value={customEnd}
            onChange={(e) => setCustomEnd(e.target.value)}
            className="rounded-lg border border-slate-200 px-2 py-1.5 text-[12px] text-slate-700 focus:border-slate-400 focus:outline-none"
          />
          <button
            type="button"
            onClick={handleApply}
            className="rounded-lg bg-slate-800 px-3 py-1.5 text-[12px] font-semibold text-white shadow-sm hover:bg-slate-700"
          >
            Apply
          </button>
        </div>
      )}

      {/* Compare Dropdown */}
      <div className="flex items-center gap-2">
        <label className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
          Compare
        </label>
        <select
          value={comparison}
          onChange={handleCompareChange}
          className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] font-medium text-slate-800 shadow-sm transition hover:border-slate-300 focus:border-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-300"
        >
          {COMPARE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};

export default ReportPeriodPicker;
