import { useCallback, useEffect, useState } from "react";

export type TaxProductRule = {
  id: string;
  jurisdictionCode: string;
  jurisdictionName: string;
  productCode: string;
  ruleType: "TAXABLE" | "EXEMPT" | "ZERO_RATED" | "REDUCED";
  specialRate?: number | null;
  validFrom: string;
  validTo?: string | null;
  notes?: string;
};

type ApiRule = {
  id: string;
  jurisdiction_code: string;
  jurisdiction_name: string;
  product_code: string;
  rule_type: TaxProductRule["ruleType"];
  special_rate: number | null;
  valid_from: string;
  valid_to: string | null;
  notes: string;
};

const mapRule = (r: ApiRule): TaxProductRule => ({
  id: r.id,
  jurisdictionCode: r.jurisdiction_code,
  jurisdictionName: r.jurisdiction_name,
  productCode: r.product_code,
  ruleType: r.rule_type,
  specialRate: r.special_rate,
  validFrom: r.valid_from,
  validTo: r.valid_to,
  notes: r.notes,
});

export function useTaxProductRules(params: { jurisdiction?: string; productCode?: string }) {
  const [rules, setRules] = useState<TaxProductRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (params.jurisdiction) qs.set("jurisdiction", params.jurisdiction);
      if (params.productCode) qs.set("product_code", params.productCode);
      const url = `/api/tax/product-rules/${qs.toString() ? `?${qs.toString()}` : ""}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load tax product rules");
      const data = await res.json();
      setRules((data.rules || []).map(mapRule));
    } catch (e: any) {
      setError(e?.message || "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }, [params.jurisdiction, params.productCode]);

  const createRule = useCallback(async (payload: any) => {
    const res = await fetch("/api/tax/product-rules/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || JSON.stringify(data?.errors || {}) || "Failed to create rule");
    return mapRule(data as ApiRule);
  }, []);

  const updateRule = useCallback(async (id: string, payload: any) => {
    const res = await fetch(`/api/tax/product-rules/${id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.error || JSON.stringify(data?.errors || {}) || "Failed to update rule");
    return mapRule(data as ApiRule);
  }, []);

  const deleteRule = useCallback(async (id: string) => {
    const res = await fetch(`/api/tax/product-rules/${id}/`, { method: "DELETE" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data?.error || "Failed to delete rule");
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  return { rules, loading, error, refetch: fetchRules, createRule, updateRule, deleteRule };
}

