import { useEffect, useState } from "react";

export type TaxDocumentAnomaly = {
  id: string;
  code: string;
  severity: "low" | "medium" | "high";
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED" | "IGNORED";
  description: string;
};

export type TaxDocumentTaxDetail = {
  tax_component_name: string;
  jurisdiction_code: string;
  rate?: string | null;
  tax_amount: string;
  is_recoverable: boolean;
};

export type TaxDocumentLine = {
  line_id: string;
  description: string;
  net_amount: string;
  tax_group?: string | null;
  tax_details: TaxDocumentTaxDetail[];
};

export type TaxDocumentBreakdown = {
  by_jurisdiction: Array<{ jurisdiction_code: string; taxable_base: string; tax_total: string }>;
  by_tax_group: Array<{ tax_group: string; tax_total: string }>;
};

export type TaxDocumentDrilldown = {
  document_type: "invoice" | "expense";
  id: number;
  number?: string | null;
  date?: string | null;
  currency: string;
  period_key: string;
  totals: {
    net_total: string;
    tax_total: string;
    gross_total: string;
  };
  breakdown: TaxDocumentBreakdown;
  lines: TaxDocumentLine[];
  anomalies: TaxDocumentAnomaly[];
  tax_guardian_link: string;
  line_level_available: boolean;
  breakdown_note?: string | null;
};

const fetchJson = async <T,>(url: string): Promise<T> => {
  const res = await fetch(url, { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = (body as any)?.error || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return body as T;
};

export function useInvoiceTaxDrilldown(invoiceId?: string | number | null) {
  const [data, setData] = useState<TaxDocumentDrilldown | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!invoiceId) return;
    let canceled = false;
    setIsLoading(true);
    setError(null);
    fetchJson<TaxDocumentDrilldown>(`/api/tax/document/invoice/${invoiceId}/`)
      .then((d) => {
        if (!canceled) setData(d);
      })
      .catch((e: any) => {
        if (!canceled) setError(e?.message || "Failed to load tax drilldown");
      })
      .finally(() => {
        if (!canceled) setIsLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, [invoiceId]);

  return { data, isLoading, error };
}

export function useExpenseTaxDrilldown(expenseId?: string | number | null) {
  const [data, setData] = useState<TaxDocumentDrilldown | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!expenseId) return;
    let canceled = false;
    setIsLoading(true);
    setError(null);
    fetchJson<TaxDocumentDrilldown>(`/api/tax/document/expense/${expenseId}/`)
      .then((d) => {
        if (!canceled) setData(d);
      })
      .catch((e: any) => {
        if (!canceled) setError(e?.message || "Failed to load tax drilldown");
      })
      .finally(() => {
        if (!canceled) setIsLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, [expenseId]);

  return { data, isLoading, error };
}

