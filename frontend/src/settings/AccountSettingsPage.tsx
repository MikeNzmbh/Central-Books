import React, { useCallback, useEffect, useMemo, useState } from "react";
import TeamManagement from "./TeamManagement";
import RolesSettingsPage from "./RolesSettingsPage";
import { usePermissions } from "../hooks/usePermissions";

type Choice = {
  value: string;
  label: string;
};

type SerializedField = {
  name: string;
  id: string;
  label: string;
  value: string;
  errors: string[];
  type: string;
  choices?: Choice[] | null;
  required: boolean;
  help_text?: string;
};

export type SerializedForm = {
  form_id: string;
  action?: string;
  method?: string;
  fields: SerializedField[];
  hidden_fields: string[];
  non_field_errors: string[];
} | null;

type TaxRateRow = {
  id: number;
  name: string;
  code?: string | null;
  rate: number;
  percentage: number;
  country?: string;
  region?: string;
  applies_to_sales: boolean;
  applies_to_purchases: boolean;
  is_active: boolean;
  is_default_sales_rate: boolean;
  is_default_purchase_rate: boolean;
};

type TaxSettingsPayload = {
  is_tax_registered: boolean;
  tax_country: string;
  tax_region: string;
  tax_rates: TaxRateRow[];
};

export interface AccountSettingsProps {
  csrfToken: string;
  profileForm: SerializedForm;
  businessForm: SerializedForm;
  passwordForm: SerializedForm;
  sessions: { current_ip?: string; user_agent?: string };
  postUrls: { profile: string; business: string; password: string; logoutAll: string };
  messages?: { level: string; message: string }[];
  taxSettings?: TaxSettingsPayload;
}

const AlertStack: React.FC<{ messages?: { level: string; message: string }[] }> = ({ messages }) => {
  if (!messages || !messages.length) {
    return null;
  }
  return (
    <div className="space-y-2">
      {messages.map((msg, idx) => (
        <div
          key={`${msg.message}-${idx}`}
          className={`rounded-2xl border px-4 py-2 text-sm ${msg.level === "success"
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
        >
          {msg.message}
        </div>
      ))}
    </div>
  );
};

const renderInput = (field: SerializedField) => {
  const baseClasses =
    "w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/10";
  if (field.type === "checkbox") {
    return (
      <label className="inline-flex items-center gap-2 text-sm text-slate-700">
        <input
          id={field.id}
          name={field.name}
          type="checkbox"
          defaultChecked={field.value === "True" || field.value === "on" || field.value === "1"}
          className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/20"
        />
        <span>{field.help_text || field.label}</span>
      </label>
    );
  }
  if (field.type === "textarea") {
    return (
      <textarea
        id={field.id}
        name={field.name}
        defaultValue={field.value}
        className={`${baseClasses} min-h-[120px]`}
        placeholder={field.help_text || field.label}
        required={field.required}
      />
    );
  }
  if (field.type === "select" && field.choices) {
    return (
      <select id={field.id} name={field.name} defaultValue={field.value} required={field.required} className={baseClasses}>
        {field.choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    );
  }
  const type = field.type === "password" ? "password" : field.type === "email" ? "email" : "text";
  return (
    <input
      id={field.id}
      name={field.name}
      type={type}
      required={field.required}
      defaultValue={type === "password" ? "" : field.value}
      className={baseClasses}
      placeholder={field.help_text || field.label}
      autoComplete={field.name}
    />
  );
};

const FieldErrors: React.FC<{ errors: string[] }> = ({ errors }) => {
  if (!errors.length) return null;
  return (
    <ul className="text-xs text-rose-600 space-y-1">
      {errors.map((err, idx) => (
        <li key={`${err}-${idx}`}>{err}</li>
      ))}
    </ul>
  );
};

const HiddenFields: React.FC<{ markup: string[] }> = ({ markup }) => {
  if (!markup.length) return null;
  return (
    <>
      {markup.map((html, idx) => (
        <span // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: html }}
          key={`hidden-${idx}`}
        />
      ))}
    </>
  );
};

const FormSection: React.FC<{
  form: SerializedForm;
  csrfToken: string;
  action: string;
  legend: string;
}> = ({ form, csrfToken, action, legend }) => {
  if (!form) {
    return <p className="text-sm text-slate-500">Complete your business setup to edit {legend.toLowerCase()}.</p>;
  }
  const fieldGrid = form.fields.length > 2 ? "grid gap-4 sm:grid-cols-2" : "space-y-4";
  return (
    <form method={form.method || "post"} action={action || form.action || ""} className="space-y-5">
      <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
      <input type="hidden" name="form_id" value={form.form_id} />
      <HiddenFields markup={form.hidden_fields} />
      {form.non_field_errors.length > 0 && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {form.non_field_errors.join(" ")}
        </div>
      )}
      <div className={fieldGrid}>
        {form.fields.map((field) => (
          <div key={field.name} className="space-y-1.5 sm:col-span-1">
            <label htmlFor={field.id} className="text-sm font-medium text-slate-700">
              {field.label}
            </label>
            {renderInput(field)}
            <FieldErrors errors={field.errors} />
          </div>
        ))}
      </div>
      <div className="flex justify-end">
        <button
          type="submit"
          className="inline-flex items-center rounded-2xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800"
        >
          Save {legend.toLowerCase()}
        </button>
      </div>
    </form>
  );
};

const Card: React.FC<{ title: string; subtitle: string; children: React.ReactNode; badge?: React.ReactNode }> = ({
  title,
  subtitle,
  children,
  badge,
}) => (
  <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
    <header className="flex items-start justify-between gap-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">Clover Books</p>
        <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-500">{subtitle}</p>
      </div>
      {badge}
    </header>
    {children}
  </section>
);

const TABS = [
  { id: "profile", label: "Profile" },
  { id: "business", label: "Business" },
  { id: "team", label: "Team", requiresOwner: true },
  { id: "roles", label: "Roles", requiresOwner: true },
  { id: "taxes", label: "Taxes" },
  { id: "security", label: "Security" },
  { id: "sessions", label: "Sessions" },
];

const AccountSettingsPage: React.FC<AccountSettingsProps> = ({
  csrfToken,
  profileForm,
  businessForm,
  passwordForm,
  sessions,
  postUrls,
  messages,
  taxSettings: taxSettingsInitial,
}) => {
  // RBAC v1: Get ownership status for permission-based UI
  const { isOwner } = usePermissions();

  const [activeTab, setActiveTab] = useState<string>("profile");
  const [taxSettings, setTaxSettings] = useState<TaxSettingsPayload>(
    taxSettingsInitial || {
      is_tax_registered: false,
      tax_country: "CA",
      tax_region: "",
      tax_rates: [],
    },
  );
  const [taxLoading, setTaxLoading] = useState(false);
  const [taxSaving, setTaxSaving] = useState(false);
  const [taxError, setTaxError] = useState<string | null>(null);
  const [taxSuccess, setTaxSuccess] = useState<string | null>(null);
  const [newRate, setNewRate] = useState<{
    name: string;
    rate: string;
    applies_to_sales: boolean;
    applies_to_purchases: boolean;
  }>({
    name: "",
    rate: "",
    applies_to_sales: true,
    applies_to_purchases: true,
  });

  const normalizeTaxRateRow = useCallback((row: any): TaxRateRow => {
    const percentage =
      row?.percentage !== undefined && row?.percentage !== null
        ? Number(row.percentage || 0)
        : Number(row?.rate || 0) * 100;
    return {
      id: row.id,
      name: row.name,
      code: row.code,
      rate: row?.rate !== undefined && row?.rate !== null ? Number(row.rate || 0) : percentage / 100,
      percentage,
      country: row.country || "CA",
      region: row.region || "",
      applies_to_sales: row.applies_to_sales !== false,
      applies_to_purchases: row.applies_to_purchases !== false,
      is_active: row.is_active !== false,
      is_default_sales_rate: row.is_default_sales_rate === true,
      is_default_purchase_rate: row.is_default_purchase_rate === true,
    };
  }, []);

  const refreshTaxes = useCallback(async () => {
    setTaxLoading(true);
    setTaxError(null);
    try {
      const res = await fetch("/api/taxes/settings/", { credentials: "same-origin" });
      if (!res.ok) {
        throw new Error("Unable to load tax settings.");
      }
      const data = await res.json();
      setTaxSettings({
        is_tax_registered: Boolean(data.is_tax_registered),
        tax_country: data.tax_country || "CA",
        tax_region: data.tax_region || "",
        tax_rates: (data.tax_rates || []).map(normalizeTaxRateRow),
      });
    } catch (err) {
      setTaxError(err instanceof Error ? err.message : "Unable to load tax settings.");
    } finally {
      setTaxLoading(false);
    }
  }, [normalizeTaxRateRow]);

  useEffect(() => {
    if (!taxSettingsInitial) {
      refreshTaxes();
    }
  }, [taxSettingsInitial, refreshTaxes]);

  const handleSaveTaxSettings = useCallback(async () => {
    setTaxSaving(true);
    setTaxError(null);
    setTaxSuccess(null);
    try {
      const res = await fetch("/api/taxes/settings/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          is_tax_registered: taxSettings.is_tax_registered,
          tax_country: taxSettings.tax_country,
          tax_region: taxSettings.tax_region,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Unable to save tax settings.");
      }
      setTaxSettings({
        is_tax_registered: Boolean(data.is_tax_registered),
        tax_country: data.tax_country || "CA",
        tax_region: data.tax_region || "",
        tax_rates: (data.tax_rates || taxSettings.tax_rates).map(normalizeTaxRateRow),
      });
      setTaxSuccess("Tax settings saved.");
    } catch (err) {
      setTaxError(err instanceof Error ? err.message : "Unable to save tax settings.");
    } finally {
      setTaxSaving(false);
    }
  }, [csrfToken, normalizeTaxRateRow, taxSettings]);

  const handleCreateRate = useCallback(async () => {
    setTaxSaving(true);
    setTaxError(null);
    setTaxSuccess(null);
    const rateNumber = Number(newRate.rate);
    if (!newRate.name.trim() || !Number.isFinite(rateNumber)) {
      setTaxError("Enter a name and percentage for the tax rate.");
      setTaxSaving(false);
      return;
    }
    const rateDecimal = rateNumber > 1 ? rateNumber / 100 : rateNumber;
    try {
      const res = await fetch("/api/taxes/rates/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          name: newRate.name.trim(),
          rate: rateDecimal,
          applies_to_sales: newRate.applies_to_sales,
          applies_to_purchases: newRate.applies_to_purchases,
          country: taxSettings.tax_country,
          region: taxSettings.tax_region,
          is_active: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Unable to create tax rate.");
      }
      setTaxSettings((prev) => ({
        ...prev,
        tax_rates: [...(prev.tax_rates || []), normalizeTaxRateRow(data.tax_rate)],
      }));
      setNewRate({ name: "", rate: "", applies_to_sales: true, applies_to_purchases: true });
      setTaxSuccess("Tax rate added.");
    } catch (err) {
      setTaxError(err instanceof Error ? err.message : "Unable to create tax rate.");
    } finally {
      setTaxSaving(false);
    }
  }, [csrfToken, newRate, normalizeTaxRateRow, taxSettings.tax_country, taxSettings.tax_region]);

  const updateRate = useCallback(
    async (rateId: number, patch: Partial<TaxRateRow>) => {
      setTaxSaving(true);
      setTaxError(null);
      setTaxSuccess(null);
      try {
        const res = await fetch(`/api/taxes/rates/${rateId}/`, {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify(patch),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || "Unable to update tax rate.");
        }
        setTaxSettings((prev) => ({
          ...prev,
          tax_rates: prev.tax_rates.map((rate) => (rate.id === rateId ? normalizeTaxRateRow(data.tax_rate) : rate)),
        }));
        setTaxSuccess("Tax rate updated.");
      } catch (err) {
        setTaxError(err instanceof Error ? err.message : "Unable to update tax rate.");
      } finally {
        setTaxSaving(false);
      }
    },
    [csrfToken, normalizeTaxRateRow],
  );

  const deactivateRate = useCallback(
    async (rateId: number) => {
      setTaxSaving(true);
      setTaxError(null);
      setTaxSuccess(null);
      try {
        const res = await fetch(`/api/taxes/rates/${rateId}/`, {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "X-CSRFToken": csrfToken },
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || "Unable to update tax rate.");
        }
        setTaxSettings((prev) => ({
          ...prev,
          tax_rates: prev.tax_rates.map((rate) => (rate.id === rateId ? normalizeTaxRateRow(data.tax_rate) : rate)),
        }));
        setTaxSuccess("Tax rate deactivated.");
      } catch (err) {
        setTaxError(err instanceof Error ? err.message : "Unable to update tax rate.");
      } finally {
        setTaxSaving(false);
      }
    },
    [csrfToken, normalizeTaxRateRow],
  );

  const content = useMemo(() => {
    switch (activeTab) {
      case "profile":
        return (
          <Card title="Profile" subtitle="Your personal details for invoices and invites.">
            <FormSection form={profileForm} csrfToken={csrfToken} action={postUrls.profile} legend="Profile" />
          </Card>
        );
      case "business":
        return (
          <Card
            title="Business"
            subtitle="Workspace identity, currency, and fiscal year."
            badge={
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-600">
                Workspace
              </span>
            }
          >
            <FormSection form={businessForm} csrfToken={csrfToken} action={postUrls.business} legend="Business" />
          </Card>
        );
      case "security":
        return (
          <Card
            title="Security"
            subtitle="Update your password; we keep you signed in everywhere."
            badge={
              <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] text-emerald-700">
                Recommended
              </span>
            }
          >
            <FormSection form={passwordForm} csrfToken={csrfToken} action={postUrls.password} legend="Password" />
          </Card>
        );
      case "team":
        return (
          <Card
            title="Team"
            subtitle="Manage who has access to your workspace and their roles."
            badge={
              <span className="inline-flex items-center rounded-full border border-purple-200 bg-purple-50 px-3 py-1 text-[11px] text-purple-700">
                RBAC v1
              </span>
            }
          >
            <TeamManagement />
          </Card>
        );
      case "roles":
        return (
          <Card
            title="Roles & permissions"
            subtitle="Configure role templates, custom roles, and guardrails."
            badge={
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] text-slate-600">
                RBAC v2
              </span>
            }
          >
            <RolesSettingsPage />
          </Card>
        );
      case "taxes":
        return (
          <div className="space-y-4">
            {taxError && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
                {taxError}
              </div>
            )}
            {taxSuccess && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
                {taxSuccess}
              </div>
            )}
            <Card
              title="Tax registration"
              subtitle="Tell us whether you collect tax and where your business is registered."
            >
              <div className="space-y-3 text-sm">
                <label className="flex items-center gap-3 text-slate-800">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                    checked={taxSettings.is_tax_registered}
                    onChange={(e) =>
                      setTaxSettings((prev) => ({ ...prev, is_tax_registered: e.target.checked }))
                    }
                  />
                  <span>My business is registered for GST/HST / Sales tax</span>
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600">Country</label>
                    <select
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                      value={taxSettings.tax_country}
                      onChange={(e) =>
                        setTaxSettings((prev) => ({ ...prev, tax_country: e.target.value }))
                      }
                    >
                      <option value="CA">Canada</option>
                      <option value="US">United States</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600">
                      Province / State (e.g., ON, CA, NY)
                    </label>
                    <input
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                      value={taxSettings.tax_region}
                      onChange={(e) =>
                        setTaxSettings((prev) => ({ ...prev, tax_region: e.target.value.toUpperCase() }))
                      }
                      placeholder="ON"
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>
                    Registration stays optional. If you&apos;re not registered, bank feed tax controls stay disabled.
                  </span>
                  <button
                    type="button"
                    onClick={handleSaveTaxSettings}
                    disabled={taxSaving}
                    className="inline-flex items-center rounded-2xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                  >
                    {taxSaving ? "Saving…" : "Save tax settings"}
                  </button>
                </div>
              </div>
            </Card>

            <Card
              title="Tax rates"
              subtitle="Simple GST/HST or sales tax codes used in bank feed review and invoices."
            >
              <div className="space-y-4 text-sm">
                <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-xs font-semibold text-slate-600 uppercase">Add a tax rate</p>
                    {taxLoading && <span className="text-[11px] text-slate-500">Refreshing…</span>}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-[1.4fr,0.6fr,auto] sm:items-end">
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-600">Name</label>
                      <input
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                        placeholder="HST 13% (ON)"
                        value={newRate.name}
                        onChange={(e) => setNewRate((prev) => ({ ...prev, name: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-slate-600">Rate (%)</label>
                      <input
                        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
                        placeholder="13"
                        value={newRate.rate}
                        onChange={(e) => setNewRate((prev) => ({ ...prev, rate: e.target.value }))}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleCreateRate}
                      disabled={taxSaving}
                      className="inline-flex items-center justify-center rounded-2xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-emerald-300"
                    >
                      {taxSaving ? "Saving…" : "Add rate"}
                    </button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-600">
                    <label className="inline-flex items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                        checked={newRate.applies_to_sales}
                        onChange={(e) =>
                          setNewRate((prev) => ({ ...prev, applies_to_sales: e.target.checked }))
                        }
                      />
                      <span>Applies to sales</span>
                    </label>
                    <label className="inline-flex items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                        checked={newRate.applies_to_purchases}
                        onChange={(e) =>
                          setNewRate((prev) => ({ ...prev, applies_to_purchases: e.target.checked }))
                        }
                      />
                      <span>Applies to purchases</span>
                    </label>
                  </div>
                </div>

                <div className="space-y-3">
                  {taxSettings.tax_rates.length === 0 ? (
                    <p className="text-sm text-slate-600">
                      No tax rates yet. Add GST/HST or a basic sales tax rate to enable tax in the bank feed.
                    </p>
                  ) : (
                    <div className="divide-y divide-slate-100 rounded-2xl border border-slate-100 bg-white">
                      {taxSettings.tax_rates.map((rate) => (
                        <div key={rate.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-semibold text-slate-900">
                                {rate.name} ({rate.percentage}%)
                              </p>
                              {!rate.is_active && (
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">
                                  Inactive
                                </span>
                              )}
                              {rate.is_default_sales_rate && (
                                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
                                  Default sales
                                </span>
                              )}
                              {rate.is_default_purchase_rate && (
                                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] text-blue-700">
                                  Default purchases
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-500">
                              {rate.applies_to_sales ? "Sales" : ""} {rate.applies_to_sales && rate.applies_to_purchases ? "·" : ""} {rate.applies_to_purchases ? "Purchases" : ""}
                              {rate.region ? ` · ${rate.region}` : ""}
                              {rate.country ? ` · ${rate.country}` : ""}
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <button
                              type="button"
                              onClick={() => updateRate(rate.id, { is_default_sales_rate: true })}
                              disabled={taxSaving}
                              className="rounded-full border border-slate-200 px-3 py-1 font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                            >
                              Set default sales
                            </button>
                            <button
                              type="button"
                              onClick={() => updateRate(rate.id, { is_default_purchase_rate: true })}
                              disabled={taxSaving}
                              className="rounded-full border border-slate-200 px-3 py-1 font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                            >
                              Set default purchases
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                rate.is_active
                                  ? deactivateRate(rate.id)
                                  : updateRate(rate.id, { is_active: true })
                              }
                              disabled={taxSaving}
                              className="rounded-full border border-slate-200 px-3 py-1 font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                            >
                              {rate.is_active ? "Deactivate" : "Activate"}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>
        );
      case "sessions":
        return (
          <Card title="Sessions" subtitle="Devices currently signed in to Clover Books.">
            <div className="space-y-4 text-sm">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <p className="text-base font-semibold text-slate-900">This device</p>
                <p className="text-xs text-slate-500">
                  {sessions.current_ip || "0.0.0.0"} · {sessions.user_agent || "Browser session"}
                </p>
              </div>
              <form method="post" action={postUrls.logoutAll} className="flex justify-end">
                <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                <button
                  type="submit"
                  className="inline-flex items-center rounded-2xl border border-rose-200 bg-white px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50"
                >
                  Sign out of all sessions
                </button>
              </form>
            </div>
          </Card>
        );
      default:
        return null;
    }
  }, [
    activeTab,
    profileForm,
    businessForm,
    passwordForm,
    sessions,
    csrfToken,
    postUrls,
    taxSettings,
    taxError,
    taxSuccess,
    taxSaving,
    taxLoading,
    newRate,
    handleSaveTaxSettings,
    handleCreateRate,
    updateRate,
    deactivateRate,
  ]);

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-10">
        <header className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Account</p>
          <h1 className="text-3xl font-semibold text-slate-900">Account settings</h1>
          <p className="text-sm text-slate-500">Keep your workspace and credentials aligned with this single panel.</p>
        </header>
        <AlertStack messages={messages} />
        <div className="grid gap-6 lg:grid-cols-[220px,1fr]">
          <aside className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <nav className="flex flex-col gap-2">
              {TABS.filter((tab) => {
                // Only show Team tab if user is owner
                if (tab.requiresOwner && !isOwner) return false;
                return true;
              }).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full rounded-2xl px-4 py-2 text-left text-sm font-medium transition ${activeTab === tab.id ? "bg-slate-900 text-white" : "bg-slate-50 text-slate-700 hover:bg-slate-100"
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </aside>
          <div>{content}</div>
        </div>
      </div>
    </div>
  );
};

export default AccountSettingsPage;
