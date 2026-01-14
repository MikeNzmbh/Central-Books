import { useCallback, useEffect, useMemo, useState } from "react";
import { ensureCsrfToken, getCsrfToken } from "../utils/csrf";

type CatalogListResponse<T> = {
  count: number;
  results: T[];
  limit: number;
  offset: number;
  next_offset: number | null;
};

const apiFetch = async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const method = (init.method || "GET").toUpperCase();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (method !== "GET") {
    const csrf = (getCsrfToken() || (await ensureCsrfToken())) || "";
    if (csrf) headers["X-CSRFToken"] = csrf;
    if (init.body !== undefined && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
  }
  return fetch(input, {
    credentials: "same-origin",
    ...init,
    headers,
  });
};

export type TaxCatalogJurisdiction = {
  id: string;
  code: string;
  name: string;
  jurisdiction_type: string;
  country_code: string;
  region_code: string;
  sourcing_rule: string;
  parent_code?: string | null;
  is_active: boolean;
  is_custom?: boolean;
};

export type TaxCatalogRate = {
  id: string;
  jurisdiction_code?: string | null;
  tax_name: string;
  rate_decimal: number;
  is_compound: boolean;
  valid_from: string;
  valid_to?: string | null;
  product_category: string;
  meta_data: Record<string, any>;
};

export type TaxCatalogProductRule = {
  id: string;
  jurisdiction_code: string;
  product_code: string;
  rule_type: "TAXABLE" | "EXEMPT" | "ZERO_RATED" | "REDUCED";
  special_rate?: number | null;
  ssuta_code?: string;
  valid_from: string;
  valid_to?: string | null;
  notes?: string;
};

export type TaxGroupReportingCategory = "TAXABLE" | "ZERO_RATED" | "EXEMPT" | "OUT_OF_SCOPE";

export type TaxCatalogGroup = {
  id: string;
  display_name: string;
  calculation_method: string;
  tax_treatment?: string | null;
  reporting_category: TaxGroupReportingCategory;
  is_system_locked: boolean;
  component_count: number;
};

export type TaxImportType = "jurisdictions" | "rates" | "product_rules";

export type TaxImportPreviewRow = {
  index: number;
  raw: Record<string, any>;
  status: "ok" | "error" | "warning";
  messages: string[];
  would_create: boolean;
  would_update: boolean;
  target_id?: string | null;
};

export type TaxImportPreview = {
  import_type: TaxImportType;
  rows: TaxImportPreviewRow[];
  summary: {
    total_rows: number;
    ok: number;
    errors: number;
    warnings: number;
  };
};

export type TaxImportApplyResult = {
  import_type: TaxImportType;
  created: number;
  updated: number;
  skipped: number;
  warnings: string[];
};

const apiFetchForm = async (input: RequestInfo | URL, form: FormData) => {
  const headers: Record<string, string> = { Accept: "application/json" };
  const csrf = (getCsrfToken() || (await ensureCsrfToken())) || "";
  if (csrf) headers["X-CSRFToken"] = csrf;
  return fetch(input, {
    method: "POST",
    credentials: "same-origin",
    headers,
    body: form,
  });
};

export async function previewTaxCatalogImport(importType: TaxImportType, file: File): Promise<TaxImportPreview> {
  const form = new FormData();
  form.append("import_type", importType);
  form.append("file", file);
  const res = await apiFetchForm("/api/tax/catalog/import/preview/", form);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
  return body as TaxImportPreview;
}

export async function applyTaxCatalogImport(importType: TaxImportType, file: File): Promise<TaxImportApplyResult> {
  const form = new FormData();
  form.append("import_type", importType);
  form.append("file", file);
  const res = await apiFetchForm("/api/tax/catalog/import/apply/", form);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
  return body as TaxImportApplyResult;
}

export function useJurisdictions(params: {
  enabled?: boolean;
  countryCode?: string;
  regionCode?: string;
  jurisdictionType?: string;
  limit?: number;
}) {
  const enabled = params.enabled ?? true;
  const [data, setData] = useState<CatalogListResponse<TaxCatalogJurisdiction> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const limit = params.limit ?? 200;

  const query = useMemo(() => {
    const qs = new URLSearchParams();
    if (params.countryCode) qs.set("country_code", params.countryCode);
    if (params.regionCode) qs.set("region_code", params.regionCode);
    if (params.jurisdictionType) qs.set("jurisdiction_type", params.jurisdictionType);
    qs.set("limit", String(limit));
    qs.set("offset", String(offset));
    return qs.toString();
  }, [params.countryCode, params.regionCode, params.jurisdictionType, limit, offset]);

  const fetchJurisdictions = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/tax/catalog/jurisdictions/?${query}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as any)?.error || `Request failed (${res.status})`);
      }
      const json = (await res.json()) as CatalogListResponse<TaxCatalogJurisdiction>;
      setData(json);
    } catch (e: any) {
      setError(e?.message || "Failed to load jurisdictions");
    } finally {
      setLoading(false);
    }
  }, [enabled, query]);

  useEffect(() => {
    setOffset(0);
  }, [params.countryCode, params.regionCode, params.jurisdictionType]);

  useEffect(() => {
    fetchJurisdictions();
  }, [fetchJurisdictions]);

  const createJurisdiction = useCallback(async (payload: any) => {
    const res = await apiFetch("/api/tax/catalog/jurisdictions/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchJurisdictions();
    return body;
  }, [fetchJurisdictions]);

  const updateJurisdiction = useCallback(async (code: string, payload: any) => {
    const res = await apiFetch(`/api/tax/catalog/jurisdictions/${encodeURIComponent(code)}/`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchJurisdictions();
    return body;
  }, [fetchJurisdictions]);

  return {
    jurisdictions: data?.results || [],
    count: data?.count || 0,
    nextOffset: data?.next_offset ?? null,
    offset,
    setOffset,
    limit,
    loading,
    error,
    refetch: fetchJurisdictions,
    createJurisdiction,
    updateJurisdiction,
  };
}

export function useTaxRates(params: {
  enabled?: boolean;
  jurisdictionCode?: string;
  taxName?: string;
  activeOn?: string;
  limit?: number;
}) {
  const enabled = params.enabled ?? true;
  const [data, setData] = useState<CatalogListResponse<TaxCatalogRate> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const limit = params.limit ?? 200;
  const query = useMemo(() => {
    const qs = new URLSearchParams();
    if (params.jurisdictionCode) qs.set("jurisdiction_code", params.jurisdictionCode);
    if (params.taxName) qs.set("tax_name", params.taxName);
    if (params.activeOn) qs.set("active_on", params.activeOn);
    qs.set("limit", String(limit));
    qs.set("offset", String(offset));
    return qs.toString();
  }, [params.jurisdictionCode, params.taxName, params.activeOn, limit, offset]);

  const fetchRates = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/tax/catalog/rates/?${query}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as any)?.error || `Request failed (${res.status})`);
      }
      const json = (await res.json()) as CatalogListResponse<TaxCatalogRate>;
      setData(json);
    } catch (e: any) {
      setError(e?.message || "Failed to load rates");
    } finally {
      setLoading(false);
    }
  }, [enabled, query]);

  useEffect(() => {
    setOffset(0);
  }, [params.jurisdictionCode, params.taxName, params.activeOn]);

  useEffect(() => {
    fetchRates();
  }, [fetchRates]);

  const createRate = useCallback(async (payload: any) => {
    const res = await apiFetch("/api/tax/catalog/rates/", { method: "POST", body: JSON.stringify(payload) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchRates();
    return body;
  }, [fetchRates]);

  const updateRate = useCallback(async (id: string, payload: any) => {
    const res = await apiFetch(`/api/tax/catalog/rates/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchRates();
    return body;
  }, [fetchRates]);

  return {
    rates: data?.results || [],
    count: data?.count || 0,
    nextOffset: data?.next_offset ?? null,
    offset,
    setOffset,
    limit,
    loading,
    error,
    refetch: fetchRates,
    createRate,
    updateRate,
  };
}

export function useCatalogProductRules(params: {
  enabled?: boolean;
  jurisdictionCode?: string;
  productCode?: string;
  limit?: number;
}) {
  const enabled = params.enabled ?? true;
  const [data, setData] = useState<CatalogListResponse<TaxCatalogProductRule> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const limit = params.limit ?? 200;
  const query = useMemo(() => {
    const qs = new URLSearchParams();
    if (params.jurisdictionCode) qs.set("jurisdiction_code", params.jurisdictionCode);
    if (params.productCode) qs.set("product_code", params.productCode);
    qs.set("limit", String(limit));
    qs.set("offset", String(offset));
    return qs.toString();
  }, [params.jurisdictionCode, params.productCode, limit, offset]);

  const fetchRules = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/tax/catalog/product-rules/?${query}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as any)?.error || `Request failed (${res.status})`);
      }
      const json = (await res.json()) as CatalogListResponse<TaxCatalogProductRule>;
      setData(json);
    } catch (e: any) {
      setError(e?.message || "Failed to load product rules");
    } finally {
      setLoading(false);
    }
  }, [enabled, query]);

  useEffect(() => {
    setOffset(0);
  }, [params.jurisdictionCode, params.productCode]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const createProductRule = useCallback(async (payload: any) => {
    const res = await apiFetch("/api/tax/catalog/product-rules/", { method: "POST", body: JSON.stringify(payload) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchRules();
    return body;
  }, [fetchRules]);

  const updateProductRule = useCallback(async (id: string, payload: any) => {
    const res = await apiFetch(`/api/tax/catalog/product-rules/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchRules();
    return body;
  }, [fetchRules]);

  return {
    productRules: data?.results || [],
    count: data?.count || 0,
    nextOffset: data?.next_offset ?? null,
    offset,
    setOffset,
    limit,
    loading,
    error,
    refetch: fetchRules,
    createProductRule,
    updateProductRule,
  };
}

export function useTaxGroups(params: {
  enabled?: boolean;
  q?: string;
  limit?: number;
}) {
  const enabled = params.enabled ?? true;
  const [data, setData] = useState<CatalogListResponse<TaxCatalogGroup> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const limit = params.limit ?? 200;
  const query = useMemo(() => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    qs.set("limit", String(limit));
    qs.set("offset", String(offset));
    return qs.toString();
  }, [params.q, limit, offset]);

  const fetchGroups = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/tax/catalog/groups/?${query}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as any)?.error || `Request failed (${res.status})`);
      }
      const json = (await res.json()) as CatalogListResponse<TaxCatalogGroup>;
      setData(json);
    } catch (e: any) {
      setError(e?.message || "Failed to load tax groups");
    } finally {
      setLoading(false);
    }
  }, [enabled, query]);

  useEffect(() => {
    setOffset(0);
  }, [params.q]);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  const updateGroup = useCallback(async (id: string, payload: any) => {
    const res = await apiFetch(`/api/tax/catalog/groups/${id}/`, { method: "PATCH", body: JSON.stringify(payload) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((body as any)?.error || JSON.stringify((body as any)?.errors || body));
    await fetchGroups();
    return body;
  }, [fetchGroups]);

  return {
    groups: data?.results || [],
    count: data?.count || 0,
    nextOffset: data?.next_offset ?? null,
    offset,
    setOffset,
    limit,
    loading,
    error,
    refetch: fetchGroups,
    updateGroup,
  };
}
