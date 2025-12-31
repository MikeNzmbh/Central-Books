import React, { useMemo, useState } from "react";
import { ArrowLeft, Database, MapPinned, Percent, Tag, Plus, Pencil, ShieldAlert, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { usePermissions } from "../hooks/usePermissions";
import {
  applyTaxCatalogImport,
  previewTaxCatalogImport,
  TaxCatalogGroup,
  TaxCatalogJurisdiction,
  TaxCatalogProductRule,
  TaxCatalogRate,
  TaxImportApplyResult,
  TaxImportPreview,
  TaxImportType,
  useCatalogProductRules,
  useTaxGroups,
  useJurisdictions,
  useTaxRates,
} from "./useTaxCatalog";

type TabKey = "jurisdictions" | "rates" | "groups" | "product_rules";

const tabs: Array<{ key: TabKey; label: string; icon: React.ReactNode }> = [
  { key: "jurisdictions", label: "Jurisdictions", icon: <MapPinned className="w-4 h-4" /> },
  { key: "rates", label: "Rates", icon: <Percent className="w-4 h-4" /> },
  { key: "groups", label: "Tax Groups", icon: <Database className="w-4 h-4" /> },
  { key: "product_rules", label: "Product Rules", icon: <Tag className="w-4 h-4" /> },
];

const TabButton: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({ active, onClick, children }) => (
  <button
    onClick={onClick}
    className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold rounded-lg border shadow-sm transition ${active
      ? "bg-white text-slate-900 border-slate-200 mb-accent-underline"
      : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50 hover:text-slate-900"
      }`}
  >
    {children}
  </button>
);

const todayIso = () => new Date().toISOString().slice(0, 10);

const TaxCatalogPage: React.FC = () => {
  const { auth } = useAuth();
  const { can } = usePermissions();
  // RBAC: check for view access (to see catalog) and manage access (to create/edit/import)
  const canViewCatalog = can("tax.catalog.view");
  const canManageCatalog = can("tax.catalog.manage");
  const [tab, setTab] = useState<TabKey>("jurisdictions");
  const [pageMessage, setPageMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Jurisdictions UI state
  const [countryCode, setCountryCode] = useState<string>("");
  const [regionCode, setRegionCode] = useState<string>("");
  const [jurType, setJurType] = useState<string>("");
  const jurisdictionsApi = useJurisdictions({
    enabled: canViewCatalog && tab === "jurisdictions",
    countryCode: countryCode || undefined,
    regionCode: regionCode || undefined,
    jurisdictionType: jurType || undefined,
    limit: 200,
  });
  const [jurFormOpen, setJurFormOpen] = useState(false);
  const [jurEditing, setJurEditing] = useState<TaxCatalogJurisdiction | null>(null);
  const [jurMessage, setJurMessage] = useState<string | null>(null);
  const [jurSaving, setJurSaving] = useState(false);
  const [jurForm, setJurForm] = useState<any>({
    code: "",
    name: "",
    jurisdiction_type: "STATE",
    country_code: "US",
    region_code: "",
    sourcing_rule: "DESTINATION",
    parent_code: "",
    is_active: true,
  });

  // Rates UI state
  const [rateJurisdiction, setRateJurisdiction] = useState<string>("");
  const [rateName, setRateName] = useState<string>("");
  const [activeOn, setActiveOn] = useState<string>("");
  const ratesApi = useTaxRates({
    enabled: canViewCatalog && tab === "rates",
    jurisdictionCode: rateJurisdiction || undefined,
    taxName: rateName || undefined,
    activeOn: activeOn || undefined,
    limit: 200,
  });
  const [rateFormOpen, setRateFormOpen] = useState(false);
  const [rateEditing, setRateEditing] = useState<TaxCatalogRate | null>(null);
  const [rateMessage, setRateMessage] = useState<string | null>(null);
  const [rateSaving, setRateSaving] = useState(false);
  const [rateForm, setRateForm] = useState<any>({
    jurisdiction_code: "",
    tax_name: "",
    rate_decimal: "",
    valid_from: todayIso(),
    valid_to: "",
    product_category: "STANDARD",
    is_compound: false,
    meta_data: {},
  });

  // Tax groups UI state
  const [groupQuery, setGroupQuery] = useState<string>("");
  const groupsApi = useTaxGroups({
    enabled: canViewCatalog && tab === "groups",
    q: groupQuery || undefined,
    limit: 200,
  });
  const [groupSavingId, setGroupSavingId] = useState<string | null>(null);

  // Product rules UI state
  const [ruleJurisdiction, setRuleJurisdiction] = useState<string>("");
  const [ruleProductCode, setRuleProductCode] = useState<string>("");
  const rulesApi = useCatalogProductRules({
    enabled: canViewCatalog && tab === "product_rules",
    jurisdictionCode: ruleJurisdiction || undefined,
    productCode: ruleProductCode || undefined,
    limit: 200,
  });
  const [ruleFormOpen, setRuleFormOpen] = useState(false);
  const [ruleEditing, setRuleEditing] = useState<TaxCatalogProductRule | null>(null);
  const [ruleMessage, setRuleMessage] = useState<string | null>(null);
  const [ruleSaving, setRuleSaving] = useState(false);
  const [ruleForm, setRuleForm] = useState<any>({
    jurisdiction_code: "",
    product_code: "",
    rule_type: "TAXABLE",
    special_rate: "",
    ssuta_code: "",
    valid_from: todayIso(),
    valid_to: "",
    notes: "",
  });

  // Import UI state (shared across tabs)
  const [importOpen, setImportOpen] = useState(false);
  const [importType, setImportType] = useState<TaxImportType>("jurisdictions");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<TaxImportPreview | null>(null);
  const [importPreviewing, setImportPreviewing] = useState(false);
  const [importApplying, setImportApplying] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<TaxImportApplyResult | null>(null);

  const openImport = (t: TaxImportType) => {
    setPageMessage(null);
    setImportError(null);
    setImportResult(null);
    setImportPreview(null);
    setImportFile(null);
    setImportType(t);
    setImportOpen(true);
  };

  const runPreviewImport = async () => {
    if (!importFile) {
      setImportError("Choose a .csv or .json file to preview.");
      return;
    }
    setImportPreviewing(true);
    setImportError(null);
    setImportResult(null);
    try {
      const preview = await previewTaxCatalogImport(importType, importFile);
      setImportPreview(preview);
    } catch (e: any) {
      setImportError(e?.message || "Preview failed");
    } finally {
      setImportPreviewing(false);
    }
  };

  const runApplyImport = async () => {
    if (!importFile) return;
    if (importPreview?.summary?.errors) return;
    setImportApplying(true);
    setImportError(null);
    try {
      const result = await applyTaxCatalogImport(importType, importFile);
      setImportResult(result);
      setImportOpen(false);
      setPageMessage({
        type: "success",
        text: `Import applied: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped.`,
      });
      if (importType === "jurisdictions") await jurisdictionsApi.refetch();
      if (importType === "rates") await ratesApi.refetch();
      if (importType === "product_rules") await rulesApi.refetch();
    } catch (e: any) {
      setImportError(e?.message || "Apply failed");
    } finally {
      setImportApplying(false);
    }
  };

  const openJurCreate = () => {
    setJurEditing(null);
    setJurMessage(null);
    setJurForm({
      code: "",
      name: "",
      jurisdiction_type: "DISTRICT",
      country_code: countryCode || "US",
      region_code: regionCode || "",
      sourcing_rule: "DESTINATION",
      parent_code: "",
      is_active: true,
    });
    setJurFormOpen(true);
  };
  const openJurEdit = (j: TaxCatalogJurisdiction) => {
    setJurEditing(j);
    setJurMessage(null);
    setJurForm({
      code: j.code,
      name: j.name,
      jurisdiction_type: j.jurisdiction_type,
      country_code: j.country_code,
      region_code: j.region_code,
      sourcing_rule: j.sourcing_rule,
      parent_code: j.parent_code || "",
      is_active: j.is_active,
    });
    setJurFormOpen(true);
  };
  const saveJurisdiction = async () => {
    setJurSaving(true);
    setJurMessage(null);
    try {
      if (jurEditing) {
        const payload: any = { name: jurForm.name, is_active: jurForm.is_active };
        if (jurEditing.is_custom && jurForm.sourcing_rule) payload.sourcing_rule = jurForm.sourcing_rule;
        await jurisdictionsApi.updateJurisdiction(jurEditing.code, payload);
        setJurMessage("Jurisdiction updated.");
      } else {
        await jurisdictionsApi.createJurisdiction(jurForm);
        setJurMessage("Jurisdiction created.");
      }
      setJurFormOpen(false);
    } catch (e: any) {
      setJurMessage(e?.message || "Failed to save jurisdiction");
    } finally {
      setJurSaving(false);
    }
  };

  const openRateCreate = () => {
    setRateEditing(null);
    setRateMessage(null);
    setRateForm({
      jurisdiction_code: rateJurisdiction || "",
      tax_name: "",
      rate_decimal: "",
      valid_from: todayIso(),
      valid_to: "",
      product_category: "STANDARD",
      is_compound: false,
      meta_data: {},
    });
    setRateFormOpen(true);
  };
  const openRateEdit = (r: TaxCatalogRate) => {
    setRateEditing(r);
    setRateMessage(null);
    setRateForm({
      jurisdiction_code: r.jurisdiction_code || "",
      tax_name: r.tax_name,
      rate_decimal: String(r.rate_decimal),
      valid_from: r.valid_from,
      valid_to: r.valid_to || "",
      product_category: r.product_category,
      is_compound: r.is_compound,
      meta_data: r.meta_data || {},
    });
    setRateFormOpen(true);
  };
  const saveRate = async () => {
    setRateSaving(true);
    setRateMessage(null);
    try {
      if (!rateForm.jurisdiction_code.trim()) throw new Error("jurisdiction_code is required.");
      if (!rateForm.tax_name.trim()) throw new Error("tax_name is required (must match an existing TaxComponent.name).");
      if (!rateForm.rate_decimal) throw new Error("rate_decimal is required.");
      const payload: any = {
        jurisdiction_code: rateForm.jurisdiction_code,
        tax_name: rateForm.tax_name,
        rate_decimal: rateForm.rate_decimal,
        valid_from: rateForm.valid_from,
        valid_to: rateForm.valid_to || null,
        product_category: rateForm.product_category,
        is_compound: Boolean(rateForm.is_compound),
        meta_data: rateForm.meta_data,
      };
      if (rateEditing) {
        await ratesApi.updateRate(rateEditing.id, {
          rate_decimal: payload.rate_decimal,
          valid_from: payload.valid_from,
          valid_to: payload.valid_to,
          product_category: payload.product_category,
          is_compound: payload.is_compound,
          meta_data: payload.meta_data,
        });
        setRateMessage("Rate updated.");
      } else {
        await ratesApi.createRate(payload);
        setRateMessage("Rate created.");
      }
      setRateFormOpen(false);
    } catch (e: any) {
      setRateMessage(e?.message || "Failed to save rate");
    } finally {
      setRateSaving(false);
    }
  };

  const openRuleCreate = () => {
    setRuleEditing(null);
    setRuleMessage(null);
    setRuleForm({
      jurisdiction_code: ruleJurisdiction || "",
      product_code: "",
      rule_type: "TAXABLE",
      special_rate: "",
      ssuta_code: "",
      valid_from: todayIso(),
      valid_to: "",
      notes: "",
    });
    setRuleFormOpen(true);
  };
  const openRuleEdit = (r: TaxCatalogProductRule) => {
    setRuleEditing(r);
    setRuleMessage(null);
    setRuleForm({
      jurisdiction_code: r.jurisdiction_code,
      product_code: r.product_code,
      rule_type: r.rule_type,
      special_rate: r.special_rate ?? "",
      ssuta_code: r.ssuta_code || "",
      valid_from: r.valid_from,
      valid_to: r.valid_to ?? "",
      notes: r.notes || "",
    });
    setRuleFormOpen(true);
  };
  const saveRule = async () => {
    setRuleSaving(true);
    setRuleMessage(null);
    try {
      if (!ruleForm.jurisdiction_code.trim()) throw new Error("jurisdiction_code is required.");
      if (!ruleForm.product_code.trim()) throw new Error("product_code is required.");
      if (!ruleForm.valid_from) throw new Error("valid_from is required.");
      const payload: any = {
        jurisdiction_code: ruleForm.jurisdiction_code,
        product_code: ruleForm.product_code,
        rule_type: ruleForm.rule_type,
        ssuta_code: (ruleForm.ssuta_code || "").trim(),
        valid_from: ruleForm.valid_from,
        valid_to: ruleForm.valid_to || null,
        notes: ruleForm.notes || "",
      };
      if (ruleForm.rule_type === "REDUCED") payload.special_rate = ruleForm.special_rate;
      if (ruleEditing) {
        await rulesApi.updateProductRule(ruleEditing.id, {
          product_code: payload.product_code,
          rule_type: payload.rule_type,
          special_rate: payload.special_rate,
          ssuta_code: payload.ssuta_code,
          valid_from: payload.valid_from,
          valid_to: payload.valid_to,
          notes: payload.notes,
        });
        setRuleMessage("Rule updated.");
      } else {
        await rulesApi.createProductRule(payload);
        setRuleMessage("Rule created.");
      }
      setRuleFormOpen(false);
    } catch (e: any) {
      setRuleMessage(e?.message || "Failed to save rule");
    } finally {
      setRuleSaving(false);
    }
  };

  const reportingCategoryOptions: Array<{ value: TaxCatalogGroup["reporting_category"]; label: string }> = [
    { value: "TAXABLE", label: "Taxable / Standard" },
    { value: "ZERO_RATED", label: "Zero-rated (0%)" },
    { value: "EXEMPT", label: "Exempt supply" },
    { value: "OUT_OF_SCOPE", label: "Out of scope" },
  ];

  const updateGroupReportingCategory = async (group: TaxCatalogGroup, category: TaxCatalogGroup["reporting_category"]) => {
    setGroupSavingId(group.id);
    setPageMessage(null);
    try {
      await groupsApi.updateGroup(group.id, { reporting_category: category });
      setPageMessage({ type: "success", text: `Updated ${group.display_name}.` });
    } catch (e: any) {
      setPageMessage({ type: "error", text: e?.message || "Failed to update tax group" });
    } finally {
      setGroupSavingId(null);
    }
  };

  const ratePercent = (r: number) => `${(r * 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}%`;

  if (auth.loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 text-sm text-slate-600">Loading…</div>
        </div>
      </div>
    );
  }

  if (!canViewCatalog) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="max-w-3xl mx-auto px-4 py-8">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-6">
            <div className="flex items-center gap-2 text-slate-900 font-semibold">
              <ShieldAlert className="w-5 h-5 text-amber-600" />
              Tax Catalog is restricted
            </div>
            <p className="text-sm text-slate-600 mt-2">
              This page is staff/admin tooling for maintaining jurisdictions, rates, and taxability rules. Ask an operator to grant access.
            </p>
            <div className="mt-4">
              <Link to="/tax" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-slate-900">
                <ArrowLeft className="w-4 h-4" />
                Back to Tax Guardian
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-900 flex items-center justify-center shadow-sm">
              <Database className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Tax Catalog</h1>
              <p className="text-sm text-slate-600">Jurisdictions, rates, and taxability rules that power your Tax Engine.</p>
              <div className="mt-1 text-xs text-slate-500">
                <Link to="/tax" className="text-sky-700 hover:text-sky-900 font-semibold">
                  Tax Guardian
                </Link>{" "}
                ·{" "}
                <Link to="/tax/settings" className="text-sky-700 hover:text-sky-900 font-semibold">
                  Tax Settings
                </Link>
              </div>
            </div>
          </div>
          <Link to="/tax" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-700 hover:text-slate-900">
            <ArrowLeft className="w-4 h-4" />
            Back to Tax Guardian
          </Link>
        </header>

        <div className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <TabButton key={t.key} active={tab === t.key} onClick={() => setTab(t.key)}>
              {t.icon}
              {t.label}
            </TabButton>
          ))}
        </div>

        {pageMessage && (
          <div
            className={`text-sm rounded-lg border p-3 ${pageMessage.type === "success"
              ? "text-emerald-800 bg-emerald-50 border-emerald-200"
              : "text-rose-800 bg-rose-50 border-rose-200"
              }`}
          >
            {pageMessage.text}
          </div>
        )}

        {tab === "jurisdictions" && (
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
            <div className="px-4 py-3 border-b border-slate-100 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-900">Jurisdictions</div>
                <div className="text-xs text-slate-500">Seeded jurisdictions are mostly locked; custom locals can be added for special cases.</div>
              </div>
              <div className="flex items-center gap-2">
                <select value={countryCode} onChange={(e) => setCountryCode(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-2 text-sm bg-white">
                  <option value="">All countries</option>
                  <option value="CA">CA</option>
                  <option value="US">US</option>
                </select>
                <input
                  value={regionCode}
                  onChange={(e) => setRegionCode(e.target.value.toUpperCase())}
                  placeholder="Region (e.g., CA, ON)"
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                />
                <select value={jurType} onChange={(e) => setJurType(e.target.value)} className="border border-slate-200 rounded-lg px-2 py-2 text-sm bg-white">
                  <option value="">All types</option>
                  <option value="STATE">STATE</option>
                  <option value="PROVINCIAL">PROVINCIAL</option>
                  <option value="COUNTY">COUNTY</option>
                  <option value="CITY">CITY</option>
                  <option value="DISTRICT">DISTRICT</option>
                  <option value="FEDERAL">FEDERAL</option>
                </select>
                <button
                  onClick={() => openImport("jurisdictions")}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
                  title="Advanced · staff only — import jurisdictions from CSV/JSON."
                >
                  <Upload className="w-4 h-4" />
                  Import…
                </button>
                <button
                  onClick={openJurCreate}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800"
                  title="Advanced: add custom jurisdictions (locals/districts)."
                >
                  <Plus className="w-4 h-4" />
                  New
                </button>
              </div>
            </div>
            {jurisdictionsApi.error && (
              <div className="px-4 py-3 text-sm text-rose-700 bg-rose-50 border-b border-rose-200">{jurisdictionsApi.error}</div>
            )}
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 text-left">Code</th>
                    <th className="px-3 py-2 text-left">Name</th>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Parent</th>
                    <th className="px-3 py-2 text-left">Sourcing</th>
                    <th className="px-3 py-2 text-left">Active</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jurisdictionsApi.jurisdictions.map((j) => (
                    <tr key={j.code} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-slate-800">
                        {j.code}
                        {j.is_custom && <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 border border-slate-200 text-slate-700">custom</span>}
                      </td>
                      <td className="px-3 py-2 text-slate-700">{j.name}</td>
                      <td className="px-3 py-2 text-slate-700">{j.jurisdiction_type}</td>
                      <td className="px-3 py-2 text-slate-600">{j.parent_code || "—"}</td>
                      <td className="px-3 py-2 text-slate-700">{j.sourcing_rule}</td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-1 rounded-full text-[11px] font-semibold border ${j.is_active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-600 border-slate-200"}`}>
                          {j.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => openJurEdit(j)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50"
                        >
                          <Pencil className="w-3 h-3" />
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!jurisdictionsApi.loading && jurisdictionsApi.jurisdictions.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-3 py-8 text-center text-sm text-slate-500">
                        No jurisdictions match these filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>{jurisdictionsApi.count} total</div>
              <div className="flex items-center gap-2">
                <button
                  disabled={jurisdictionsApi.offset === 0}
                  onClick={() => jurisdictionsApi.setOffset(Math.max(0, jurisdictionsApi.offset - jurisdictionsApi.limit))}
                  className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50"
                >
                  Prev
                </button>
                <button
                  disabled={jurisdictionsApi.nextOffset === null}
                  onClick={() => jurisdictionsApi.nextOffset !== null && jurisdictionsApi.setOffset(jurisdictionsApi.nextOffset)}
                  className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === "rates" && (
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
            <div className="px-4 py-3 border-b border-slate-100 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-900">Rates</div>
                <div className="text-xs text-slate-500">Time-versioned rates (SCD-ish). Non-overlapping date ranges enforced.</div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={rateJurisdiction}
                  onChange={(e) => setRateJurisdiction(e.target.value.toUpperCase())}
                  placeholder="Jurisdiction (e.g., CA-ON)"
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                />
                <input
                  value={rateName}
                  onChange={(e) => setRateName(e.target.value)}
                  placeholder="Tax name contains…"
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                />
                <input
                  type="date"
                  value={activeOn}
                  onChange={(e) => setActiveOn(e.target.value)}
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                  title="Filter by rates active on this date"
                />
                <button
                  onClick={() => openImport("rates")}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
                  title="Advanced · staff only — import rates from CSV/JSON."
                >
                  <Upload className="w-4 h-4" />
                  Import…
                </button>
                <button
                  onClick={openRateCreate}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800"
                >
                  <Plus className="w-4 h-4" />
                  New
                </button>
              </div>
            </div>
            {ratesApi.error && <div className="px-4 py-3 text-sm text-rose-700 bg-rose-50 border-b border-rose-200">{ratesApi.error}</div>}
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 text-left">Jurisdiction</th>
                    <th className="px-3 py-2 text-left">Tax name</th>
                    <th className="px-3 py-2 text-right">Rate</th>
                    <th className="px-3 py-2 text-left">Valid</th>
                    <th className="px-3 py-2 text-left">Category</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {ratesApi.rates.map((r) => (
                    <tr key={r.id} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-slate-800">{r.jurisdiction_code || "—"}</td>
                      <td className="px-3 py-2 text-slate-700">{r.tax_name}</td>
                      <td className="px-3 py-2 text-right font-mono-soft">{ratePercent(r.rate_decimal)}</td>
                      <td className="px-3 py-2 text-slate-700">
                        <div>{r.valid_from}</div>
                        <div className="text-xs text-slate-500">{r.valid_to ? `→ ${r.valid_to}` : "→ (open)"}</div>
                      </td>
                      <td className="px-3 py-2 text-slate-600 text-xs">{r.product_category}</td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => openRateEdit(r)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50"
                        >
                          <Pencil className="w-3 h-3" />
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!ratesApi.loading && ratesApi.rates.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-3 py-8 text-center text-sm text-slate-500">
                        No rates found. Tip: pick a jurisdiction filter (e.g., CA-ON) to narrow the list.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>{ratesApi.count} total</div>
              <div className="flex items-center gap-2">
                <button disabled={ratesApi.offset === 0} onClick={() => ratesApi.setOffset(Math.max(0, ratesApi.offset - ratesApi.limit))} className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50">
                  Prev
                </button>
                <button disabled={ratesApi.nextOffset === null} onClick={() => ratesApi.nextOffset !== null && ratesApi.setOffset(ratesApi.nextOffset)} className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50">
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === "groups" && (
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
            <div className="px-4 py-3 border-b border-slate-100 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-900">Tax Groups</div>
                <div className="text-xs text-slate-500">Reporting categories drive what is included in sales totals and filing line mappings.</div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={groupQuery}
                  onChange={(e) => setGroupQuery(e.target.value)}
                  placeholder="Search groups…"
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                />
              </div>
            </div>
            {groupsApi.error && <div className="px-4 py-3 text-sm text-rose-700 bg-rose-50 border-b border-rose-200">{groupsApi.error}</div>}
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 text-left">Group</th>
                    <th className="px-3 py-2 text-right">Components</th>
                    <th className="px-3 py-2 text-left">Reporting category</th>
                    <th className="px-3 py-2 text-left">Locked</th>
                  </tr>
                </thead>
                <tbody>
                  {groupsApi.groups.map((g) => (
                    <tr key={g.id} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-slate-800">{g.display_name}</td>
                      <td className="px-3 py-2 text-right font-mono-soft text-slate-700">{g.component_count}</td>
                      <td className="px-3 py-2">
                        <select
                          value={g.reporting_category}
                          disabled={groupSavingId === g.id}
                          onChange={(e) => updateGroupReportingCategory(g, e.target.value as TaxCatalogGroup["reporting_category"])}
                          className="border border-slate-200 rounded-lg px-2 py-2 text-sm bg-white disabled:opacity-60"
                        >
                          {reportingCategoryOptions.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-1 rounded-full text-[11px] font-semibold border ${g.is_system_locked ? "bg-slate-100 text-slate-700 border-slate-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"
                            }`}
                        >
                          {g.is_system_locked ? "System" : "Editable"}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!groupsApi.loading && groupsApi.groups.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-3 py-8 text-center text-sm text-slate-500">
                        No tax groups found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>{groupsApi.count} total</div>
              <div className="flex items-center gap-2">
                <button
                  disabled={groupsApi.offset === 0}
                  onClick={() => groupsApi.setOffset(Math.max(0, groupsApi.offset - groupsApi.limit))}
                  className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50"
                >
                  Prev
                </button>
                <button
                  disabled={groupsApi.nextOffset === null}
                  onClick={() => groupsApi.nextOffset !== null && groupsApi.setOffset(groupsApi.nextOffset)}
                  className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {tab === "product_rules" && (
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm">
            <div className="px-4 py-3 border-b border-slate-100 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-slate-900">Product Rules</div>
                <div className="text-xs text-slate-500">Taxability rules per jurisdiction (non-overlapping ranges enforced).</div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={ruleJurisdiction}
                  onChange={(e) => setRuleJurisdiction(e.target.value.toUpperCase())}
                  placeholder="Jurisdiction (e.g., CA-ON)"
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                />
                <input
                  value={ruleProductCode}
                  onChange={(e) => setRuleProductCode(e.target.value.toUpperCase())}
                  placeholder="Product code (e.g., FOOD)"
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white"
                />
                <button
                  onClick={() => openImport("product_rules")}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
                  title="Advanced · staff only — import product rules from CSV/JSON."
                >
                  <Upload className="w-4 h-4" />
                  Import…
                </button>
                <button
                  onClick={openRuleCreate}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800"
                >
                  <Plus className="w-4 h-4" />
                  New
                </button>
              </div>
            </div>
            {rulesApi.error && <div className="px-4 py-3 text-sm text-rose-700 bg-rose-50 border-b border-rose-200">{rulesApi.error}</div>}
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-3 py-2 text-left">Jurisdiction</th>
                    <th className="px-3 py-2 text-left">Product</th>
                    <th className="px-3 py-2 text-left">SSUTA</th>
                    <th className="px-3 py-2 text-left">Rule</th>
                    <th className="px-3 py-2 text-right">Special rate</th>
                    <th className="px-3 py-2 text-left">Valid</th>
                    <th className="px-3 py-2 text-left">Notes</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rulesApi.productRules.map((r) => (
                    <tr key={r.id} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold text-slate-800">{r.jurisdiction_code}</td>
                      <td className="px-3 py-2 text-slate-700">{r.product_code}</td>
                      <td className="px-3 py-2 text-slate-700">{r.ssuta_code || "—"}</td>
                      <td className="px-3 py-2 text-slate-700">{r.rule_type}</td>
                      <td className="px-3 py-2 text-right font-mono-soft">{r.special_rate ?? "—"}</td>
                      <td className="px-3 py-2 text-slate-700">
                        <div>{r.valid_from}</div>
                        <div className="text-xs text-slate-500">{r.valid_to ? `→ ${r.valid_to}` : "→ (open)"}</div>
                      </td>
                      <td className="px-3 py-2 text-slate-600 max-w-[360px] truncate" title={r.notes || ""}>
                        {r.notes || "—"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => openRuleEdit(r)}
                          className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-md hover:bg-slate-50"
                        >
                          <Pencil className="w-3 h-3" />
                          Edit
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!rulesApi.loading && rulesApi.productRules.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-3 py-8 text-center text-sm text-slate-500">
                        No catalog product rules found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>{rulesApi.count} total</div>
              <div className="flex items-center gap-2">
                <button disabled={rulesApi.offset === 0} onClick={() => rulesApi.setOffset(Math.max(0, rulesApi.offset - rulesApi.limit))} className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50">
                  Prev
                </button>
                <button disabled={rulesApi.nextOffset === null} onClick={() => rulesApi.nextOffset !== null && rulesApi.setOffset(rulesApi.nextOffset)} className="px-2 py-1 border border-slate-200 rounded-md bg-white disabled:opacity-50">
                  Next
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Jurisdiction modal */}
        {jurFormOpen && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-white border border-slate-200 rounded-xl shadow-lg p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900">{jurEditing ? `Edit ${jurEditing.code}` : "Add jurisdiction"}</h2>
                <button onClick={() => setJurFormOpen(false)} className="text-sm text-slate-500 hover:text-slate-700">
                  Close
                </button>
              </div>
              {jurMessage && <div className="mt-3 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-2">{jurMessage}</div>}
              <div className="grid grid-cols-1 gap-3 mt-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Code</label>
                    <input
                      disabled={!!jurEditing}
                      value={jurForm.code}
                      onChange={(e) => setJurForm({ ...jurForm, code: e.target.value.toUpperCase() })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                      placeholder="US-CA-SF"
                    />
                    <p className="text-xs text-slate-500 mt-1">Code is immutable once created.</p>
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Active</label>
                    <select
                      value={jurForm.is_active ? "true" : "false"}
                      onChange={(e) => setJurForm({ ...jurForm, is_active: e.target.value === "true" })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    >
                      <option value="true">Active</option>
                      <option value="false">Inactive</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-semibold text-slate-800">Name</label>
                  <input
                    value={jurForm.name}
                    onChange={(e) => setJurForm({ ...jurForm, name: e.target.value })}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    placeholder="San Francisco"
                  />
                </div>
                {!jurEditing && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="text-sm font-semibold text-slate-800">Country</label>
                      <select
                        value={jurForm.country_code}
                        onChange={(e) => setJurForm({ ...jurForm, country_code: e.target.value.toUpperCase() })}
                        className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                      >
                        <option value="US">US</option>
                        <option value="CA">CA</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-slate-800">Type</label>
                      <select
                        value={jurForm.jurisdiction_type}
                        onChange={(e) => setJurForm({ ...jurForm, jurisdiction_type: e.target.value })}
                        className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                      >
                        <option value="STATE">STATE</option>
                        <option value="PROVINCIAL">PROVINCIAL</option>
                        <option value="COUNTY">COUNTY</option>
                        <option value="CITY">CITY</option>
                        <option value="DISTRICT">DISTRICT</option>
                        <option value="FEDERAL">FEDERAL</option>
                      </select>
                    </div>
                  </div>
                )}
                {!jurEditing && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="text-sm font-semibold text-slate-800">Region code</label>
                      <input
                        value={jurForm.region_code}
                        onChange={(e) => setJurForm({ ...jurForm, region_code: e.target.value.toUpperCase() })}
                        className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                        placeholder="CA, ON, QC"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-semibold text-slate-800">Parent code (optional)</label>
                      <input
                        value={jurForm.parent_code}
                        onChange={(e) => setJurForm({ ...jurForm, parent_code: e.target.value.toUpperCase() })}
                        className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                        placeholder="US-CA"
                      />
                    </div>
                  </div>
                )}
                <div>
                  <label className="text-sm font-semibold text-slate-800">Sourcing rule</label>
                  <select
                    disabled={!!jurEditing && !jurEditing.is_custom}
                    value={jurForm.sourcing_rule}
                    onChange={(e) => setJurForm({ ...jurForm, sourcing_rule: e.target.value })}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                  >
                    <option value="DESTINATION">DESTINATION</option>
                    <option value="ORIGIN">ORIGIN</option>
                    <option value="HYBRID">HYBRID</option>
                  </select>
                  {!!jurEditing && !jurEditing.is_custom && (
                    <p className="text-xs text-slate-500 mt-1">Seeded jurisdictions lock sourcing_rule changes.</p>
                  )}
                </div>

                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setJurFormOpen(false)}
                    className="px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={jurSaving}
                    onClick={saveJurisdiction}
                    className="px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800 disabled:opacity-60"
                  >
                    {jurSaving ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Rate modal */}
        {rateFormOpen && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-white border border-slate-200 rounded-xl shadow-lg p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900">{rateEditing ? "Edit rate" : "Add rate"}</h2>
                <button onClick={() => setRateFormOpen(false)} className="text-sm text-slate-500 hover:text-slate-700">
                  Close
                </button>
              </div>
              {rateMessage && <div className="mt-3 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-2">{rateMessage}</div>}
              <div className="grid grid-cols-1 gap-3 mt-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Jurisdiction code</label>
                    <input
                      disabled={!!rateEditing}
                      value={rateForm.jurisdiction_code}
                      onChange={(e) => setRateForm({ ...rateForm, jurisdiction_code: e.target.value.toUpperCase() })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                      placeholder="CA-ON"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Product category</label>
                    <select
                      value={rateForm.product_category}
                      onChange={(e) => setRateForm({ ...rateForm, product_category: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    >
                      <option value="STANDARD">STANDARD</option>
                      <option value="SAAS">SAAS</option>
                      <option value="DIGITAL_GOOD">DIGITAL_GOOD</option>
                      <option value="ZERO_RATED">ZERO_RATED</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-semibold text-slate-800">Tax name (TaxComponent.name)</label>
                  <input
                    disabled={!!rateEditing}
                    value={rateForm.tax_name}
                    onChange={(e) => setRateForm({ ...rateForm, tax_name: e.target.value })}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                    placeholder="Ontario HST 13%"
                  />
                  <p className="text-xs text-slate-500 mt-1">This must match an existing TaxComponent name for this business.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Rate (decimal)</label>
                    <input
                      value={rateForm.rate_decimal}
                      onChange={(e) => setRateForm({ ...rateForm, rate_decimal: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                      placeholder="0.130000"
                    />
                  </div>
                  <div className="flex items-center gap-2 mt-6">
                    <input
                      id="rate_is_compound"
                      type="checkbox"
                      checked={Boolean(rateForm.is_compound)}
                      onChange={(e) => setRateForm({ ...rateForm, is_compound: e.target.checked })}
                      className="h-4 w-4"
                    />
                    <label htmlFor="rate_is_compound" className="text-sm text-slate-700">
                      Compound flag (reserved)
                    </label>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Valid from</label>
                    <input
                      type="date"
                      value={rateForm.valid_from}
                      onChange={(e) => setRateForm({ ...rateForm, valid_from: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Valid to (optional)</label>
                    <input
                      type="date"
                      value={rateForm.valid_to}
                      onChange={(e) => setRateForm({ ...rateForm, valid_to: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-semibold text-slate-800">Meta data (JSON)</label>
                  <textarea
                    value={JSON.stringify(rateForm.meta_data || {}, null, 2)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        setRateForm({ ...rateForm, meta_data: parsed });
                      } catch {
                        // ignore invalid JSON until save
                      }
                    }}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono bg-white shadow-sm"
                    rows={4}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button onClick={() => setRateFormOpen(false)} className="px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50">
                    Cancel
                  </button>
                  <button disabled={rateSaving} onClick={saveRate} className="px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800 disabled:opacity-60">
                    {rateSaving ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Product rule modal */}
        {ruleFormOpen && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-white border border-slate-200 rounded-xl shadow-lg p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900">{ruleEditing ? "Edit rule" : "Add rule"}</h2>
                <button onClick={() => setRuleFormOpen(false)} className="text-sm text-slate-500 hover:text-slate-700">
                  Close
                </button>
              </div>
              {ruleMessage && <div className="mt-3 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-2">{ruleMessage}</div>}
              <div className="grid grid-cols-1 gap-3 mt-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Jurisdiction</label>
                    <input
                      disabled={!!ruleEditing}
                      value={ruleForm.jurisdiction_code}
                      onChange={(e) => setRuleForm({ ...ruleForm, jurisdiction_code: e.target.value.toUpperCase() })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                      placeholder="CA-ON"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Product code</label>
                    <input
                      value={ruleForm.product_code}
                      onChange={(e) => setRuleForm({ ...ruleForm, product_code: e.target.value.toUpperCase() })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                      placeholder="FOOD"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Rule type</label>
                    <select
                      value={ruleForm.rule_type}
                      onChange={(e) => setRuleForm({ ...ruleForm, rule_type: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    >
                      <option value="TAXABLE">TAXABLE</option>
                      <option value="EXEMPT">EXEMPT</option>
                      <option value="ZERO_RATED">ZERO_RATED</option>
                      <option value="REDUCED">REDUCED</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Special rate</label>
                    <input
                      disabled={ruleForm.rule_type !== "REDUCED"}
                      value={ruleForm.special_rate}
                      onChange={(e) => setRuleForm({ ...ruleForm, special_rate: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
                      placeholder="0.050000"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-semibold text-slate-800">SSUTA code (optional)</label>
                  <input
                    value={ruleForm.ssuta_code}
                    onChange={(e) => setRuleForm({ ...ruleForm, ssuta_code: e.target.value })}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    placeholder="e.g., SRV_DIGITAL (optional)"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Valid from</label>
                    <input
                      type="date"
                      value={ruleForm.valid_from}
                      onChange={(e) => setRuleForm({ ...ruleForm, valid_from: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Valid to (optional)</label>
                    <input
                      type="date"
                      value={ruleForm.valid_to}
                      onChange={(e) => setRuleForm({ ...ruleForm, valid_to: e.target.value })}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-sm font-semibold text-slate-800">Notes</label>
                  <textarea
                    value={ruleForm.notes}
                    onChange={(e) => setRuleForm({ ...ruleForm, notes: e.target.value })}
                    className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    rows={3}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button onClick={() => setRuleFormOpen(false)} className="px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50">
                    Cancel
                  </button>
                  <button disabled={ruleSaving} onClick={saveRule} className="px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800 disabled:opacity-60">
                    {ruleSaving ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Import modal */}
        {importOpen && (
          <div className="fixed inset-0 bg-black/20 flex items-center justify-center p-4">
            <div className="w-full max-w-5xl bg-white border border-slate-200 rounded-xl shadow-lg">
              <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold text-slate-900">Import tax catalog</div>
                  <div className="text-xs text-slate-500 mt-1">
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                      Advanced · staff only
                    </span>{" "}
                    Preview first; apply only if there are no errors.
                  </div>
                </div>
                <button onClick={() => setImportOpen(false)} className="text-sm font-semibold text-slate-600 hover:text-slate-800">
                  Close
                </button>
              </div>

              <div className="p-4 space-y-3">
                {importError && (
                  <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg p-3">
                    {importError}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-sm font-semibold text-slate-800">Import type</label>
                    <select
                      value={importType}
                      onChange={(e) => {
                        setImportType(e.target.value as TaxImportType);
                        setImportPreview(null);
                        setImportResult(null);
                        setImportError(null);
                      }}
                      className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                    >
                      <option value="jurisdictions">Jurisdictions</option>
                      <option value="rates">Rates</option>
                      <option value="product_rules">Product rules</option>
                    </select>
                  </div>
                  <div className="md:col-span-2">
                    <label className="text-sm font-semibold text-slate-800">File (.csv or .json)</label>
                    <input
                      type="file"
                      accept=".csv,.json,text/csv,application/json"
                      onChange={(e) => {
                        setImportFile(e.target.files?.[0] || null);
                        setImportPreview(null);
                        setImportResult(null);
                        setImportError(null);
                      }}
                      className="mt-1 block w-full text-sm"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Imports create/update catalog records. Review the preview carefully before applying.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={runPreviewImport}
                    disabled={importPreviewing || !importFile}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-white bg-slate-900 rounded-lg shadow-sm hover:bg-slate-800 disabled:opacity-60"
                  >
                    {importPreviewing ? "Previewing…" : "Preview"}
                  </button>
                  <button
                    onClick={runApplyImport}
                    disabled={importApplying || !importPreview || importPreview.summary.errors > 0}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-900 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50 disabled:opacity-50"
                    title={importPreview?.summary?.errors ? "Fix preview errors before applying." : ""}
                  >
                    {importApplying ? "Applying…" : "Apply import"}
                  </button>
                  {importPreview && (
                    <div className="text-xs text-slate-600">
                      <span className="font-semibold">{importPreview.summary.ok}</span> ok ·{" "}
                      <span className="font-semibold">{importPreview.summary.warnings}</span> warnings ·{" "}
                      <span className="font-semibold">{importPreview.summary.errors}</span> errors
                    </div>
                  )}
                </div>

                {importPreview && (
                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <div className="px-3 py-2 bg-slate-50 text-xs text-slate-600 flex items-center justify-between">
                      <div className="font-semibold">Preview</div>
                      <div>Showing first 50 rows</div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-white text-slate-600">
                          <tr>
                            <th className="px-3 py-2 text-left">#</th>
                            <th className="px-3 py-2 text-left">Status</th>
                            <th className="px-3 py-2 text-left">Key</th>
                            <th className="px-3 py-2 text-left">Action</th>
                            <th className="px-3 py-2 text-left">Messages</th>
                          </tr>
                        </thead>
                        <tbody>
                          {importPreview.rows.slice(0, 50).map((r) => {
                            const badge =
                              r.status === "ok"
                                ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                : r.status === "warning"
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : "bg-rose-50 text-rose-700 border-rose-200";

                            const raw = r.raw || {};
                            const key =
                              importPreview.import_type === "jurisdictions"
                                ? `${raw.code || "—"} · ${raw.name || "—"} · ${raw.jurisdiction_type || "—"}`
                                : importPreview.import_type === "rates"
                                  ? `${raw.jurisdiction_code || "—"} · ${raw.tax_name || "—"} · ${raw.rate_decimal || "—"}`
                                  : `${raw.jurisdiction_code || "—"} · ${raw.product_code || "—"} · ${raw.rule_type || "—"}`;

                            const action = r.would_update ? "Update" : r.would_create ? "Create" : "—";
                            const messages = (r.messages || []).join(" · ");
                            return (
                              <tr key={r.index} className="border-t border-slate-100">
                                <td className="px-3 py-2 text-slate-600">{r.index}</td>
                                <td className="px-3 py-2">
                                  <span className={`px-2 py-1 rounded-full text-[11px] font-semibold border ${badge}`}>
                                    {r.status.toUpperCase()}
                                  </span>
                                </td>
                                <td className="px-3 py-2 text-slate-800">{key}</td>
                                <td className="px-3 py-2 text-slate-700">{action}</td>
                                <td className="px-3 py-2 text-slate-600 max-w-[520px] truncate" title={messages}>
                                  {messages || "—"}
                                </td>
                              </tr>
                            );
                          })}
                          {importPreview.rows.length === 0 && (
                            <tr>
                              <td colSpan={5} className="px-3 py-8 text-center text-sm text-slate-500">
                                No rows found in file.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TaxCatalogPage;
