import { useEffect, useState, useCallback } from "react";

export type TaxSettings = {
  tax_country: string;
  tax_region: string;
  tax_regime_ca: "GST_ONLY" | "HST_ONLY" | "GST_QST" | "GST_PST" | null;
  tax_filing_frequency: "MONTHLY" | "QUARTERLY" | "ANNUAL";
  tax_filing_due_day: number;
  gst_hst_number: string;
  qst_number: string;
  us_sales_tax_id: string;
  default_nexus_jurisdictions: string[];
  is_country_locked: boolean;
};

export function useTaxSettings() {
  const [settings, setSettings] = useState<TaxSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/tax/settings/");
      if (!res.ok) throw new Error("Failed to load tax settings");
      const data = await res.json();
      setSettings(data);
    } catch (e: any) {
      setError(e?.message || "Failed to load tax settings");
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSettings = useCallback(
    async (updates: Partial<TaxSettings>) => {
      const res = await fetch("/api/tax/settings/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = (data && data.error) || (data && data.errors && JSON.stringify(data.errors)) || "Failed to save";
        throw new Error(msg);
      }
      const data = await res.json();
      setSettings(data);
      return data;
    },
    []
  );

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  return { settings, loading, error, fetchSettings, updateSettings };
}
