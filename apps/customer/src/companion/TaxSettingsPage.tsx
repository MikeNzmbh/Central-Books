import React, { useEffect, useMemo, useState } from "react";
import { Shield, Save, ArrowLeft, Database } from "lucide-react";
import { Link } from "react-router-dom";
import { useTaxSettings, TaxSettings } from "./useTaxSettings";
import { useAuth } from "../contexts/AuthContext";
import { usePermissions } from "../hooks/usePermissions";

const frequencies = [
  { value: "MONTHLY", label: "Monthly" },
  { value: "QUARTERLY", label: "Quarterly" },
  { value: "ANNUAL", label: "Annual" },
];

const caRegimes = [
  { value: "", label: "(Not set)" },
  { value: "GST_ONLY", label: "GST only" },
  { value: "HST_ONLY", label: "HST only (HST province)" },
  { value: "GST_QST", label: "GST + QST (Quebec)" },
  { value: "GST_PST", label: "GST + PST (non-harmonized)" },
];

const TaxSettingsPage: React.FC = () => {
  const { auth } = useAuth();
  const { can } = usePermissions();
  const { settings, loading, error, updateSettings } = useTaxSettings();
  const [local, setLocal] = useState<Partial<TaxSettings>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (settings) {
      setLocal(settings);
    }
  }, [settings]);

  const nexusText = useMemo(() => (local.default_nexus_jurisdictions || []).join(", "), [local.default_nexus_jurisdictions]);

  const handleSave = async () => {
    if (!local) return;
    setSaving(true);
    setMessage(null);
    try {
      await updateSettings({
        ...local,
        default_nexus_jurisdictions: (local.default_nexus_jurisdictions || nexusText.split(",").map((v) => v.trim()).filter(Boolean)),
      });
      setMessage("Settings saved.");
    } catch (e: any) {
      setMessage(e?.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-4">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center border border-emerald-200">
              <Shield className="w-5 h-5 text-emerald-700" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Tax Settings</h1>
              <p className="text-sm text-slate-600">Configure tax country, filing cadence, and registration numbers for this business.</p>
            </div>
          </div>
          <Link to="/tax" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-800">
            <ArrowLeft className="w-4 h-4" />
            Back to Tax Guardian
          </Link>
        </header>

        {error && <div className="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-lg p-3">{error}</div>}
        {message && <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3">{message}</div>}

        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-semibold text-slate-800">Tax Country</label>
              <select
                disabled={settings?.is_country_locked}
                value={local.tax_country || ""}
                onChange={(e) => setLocal({ ...local, tax_country: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm disabled:bg-slate-50 disabled:text-slate-500"
              >
                <option value="">Select country</option>
                <option value="CA">Canada</option>
                <option value="US">United States</option>
              </select>
              <p className="text-xs text-slate-500 mt-1">
                {settings?.is_country_locked
                  ? "Tax country is locked once set. Contact support to change."
                  : "Locked after first set."}
              </p>
            </div>
            <div>
              <label className="text-sm font-semibold text-slate-800">Tax Region (province/state code)</label>
              <input
                type="text"
                value={local.tax_region || ""}
                onChange={(e) => setLocal({ ...local, tax_region: e.target.value.toUpperCase() })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                placeholder="ON, QC, CA, NY, TX"
              />
              <p className="text-xs text-slate-500 mt-1">Use standard codes like ON, QC, CA, NY, TX.</p>
            </div>
          </div>

          {(local.tax_country || settings?.tax_country) === "CA" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-semibold text-slate-800">Tax regime (Canada)</label>
                <select
                  value={local.tax_regime_ca || ""}
                  onChange={(e) => setLocal({ ...local, tax_regime_ca: (e.target.value || null) as TaxSettings["tax_regime_ca"] })}
                  className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
                >
                  {caRegimes.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500 mt-1">Used for UX and future wiring; does not change calculations yet.</p>
              </div>
              <div />
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-semibold text-slate-800">Filing frequency</label>
              <select
                value={local.tax_filing_frequency || "QUARTERLY"}
                onChange={(e) => setLocal({ ...local, tax_filing_frequency: e.target.value as TaxSettings["tax_filing_frequency"] })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
              >
                {frequencies.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-slate-500 mt-1">Used to compute tax filing due dates in Tax Guardian.</p>
            </div>
            <div>
              <label className="text-sm font-semibold text-slate-800">Filing due day</label>
              <input
                type="number"
                min={1}
                max={31}
                value={local.tax_filing_due_day ?? 30}
                onChange={(e) => setLocal({ ...local, tax_filing_due_day: Number(e.target.value) })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
              />
              <p className="text-xs text-slate-500 mt-1">Day of month when returns are due (e.g., 30 = end of next month).</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-semibold text-slate-800">GST/HST Registration #</label>
              <input
                type="text"
                value={local.gst_hst_number || ""}
                onChange={(e) => setLocal({ ...local, gst_hst_number: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
              />
            </div>
            <div>
              <label className="text-sm font-semibold text-slate-800">QST Registration # (Quebec)</label>
              <input
                type="text"
                value={local.qst_number || ""}
                onChange={(e) => setLocal({ ...local, qst_number: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-semibold text-slate-800">US Sales Tax Permit ID</label>
              <input
                type="text"
                value={local.us_sales_tax_id || ""}
                onChange={(e) => setLocal({ ...local, us_sales_tax_id: e.target.value })}
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
              />
            </div>
            <div>
              <label className="text-sm font-semibold text-slate-800">US Nexus jurisdictions</label>
              <input
                type="text"
                value={nexusText}
                onChange={(e) =>
                  setLocal({
                    ...local,
                    default_nexus_jurisdictions: e.target.value
                      .split(",")
                      .map((v) => v.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="US-CA, US-NY"
                className="mt-1 w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white shadow-sm"
              />
              <p className="text-xs text-slate-500 mt-1">Jurisdiction codes like US-CA, US-NY (comma separated).</p>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white text-sm font-semibold rounded-lg shadow-sm hover:bg-emerald-700 disabled:opacity-60"
            >
              <Save className="w-4 h-4" />
              {saving ? "Saving..." : "Save changes"}
            </button>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
          <h2 className="text-sm font-bold text-slate-900">Product taxability</h2>
          <p className="text-sm text-slate-600 mt-1">
            Manage deterministic rules for EXEMPT/ZERO-RATED/REDUCED products per jurisdiction.
          </p>
          <div className="mt-3">
            <Link
              to="/tax/product-rules"
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
            >
              Manage rules
            </Link>
          </div>
        </div>

        {can("tax.catalog.view") && (
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
            <h2 className="text-sm font-bold text-slate-900">Tax Catalog (staff)</h2>
            <p className="text-sm text-slate-600 mt-1">
              Manage jurisdictions and time-versioned rates that power deterministic tax calculations.
            </p>
            <div className="mt-3">
              <Link
                to="/tax/catalog"
                className="inline-flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg shadow-sm hover:bg-slate-50"
              >
                <Database className="w-4 h-4" />
                Open Tax Catalog
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TaxSettingsPage;
