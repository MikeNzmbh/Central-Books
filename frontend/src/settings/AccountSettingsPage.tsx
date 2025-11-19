import React, { useMemo, useState } from "react";

type Message = { level: string; message: string };

export type FieldChoice = { value: string; label: string };

export type FieldSpec = {
  name: string;
  id: string;
  label: string;
  value: string;
  errors: string[];
  type: string;
  choices?: FieldChoice[] | null;
  required: boolean;
  help_text?: string;
};

export type FormSpec = {
  form: string;
  fields: FieldSpec[];
  non_field_errors: string[];
} | null;

export type AccountSettingsPayload = {
  csrfToken: string;
  postUrl: string;
  logoutUrl: string;
  profileForm: FormSpec;
  businessForm: FormSpec;
  passwordForm: FormSpec;
  messages?: Message[];
  user?: {
    name?: string;
    email?: string;
  };
  session?: {
    device?: string;
    location?: string;
  };
};

const AlertStack: React.FC<{ messages?: Message[] }> = ({ messages }) => {
  if (!messages || !messages.length) return null;
  return (
    <div className="space-y-2 mb-6">
      {messages.map((msg, idx) => (
        <div
          key={`${msg.message}-${idx}`}
          className={`rounded-2xl border px-3.5 py-2 text-sm ${
            msg.level === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-700"
          }`}
        >
          {msg.message}
        </div>
      ))}
    </div>
  );
};

const FieldErrors: React.FC<{ errors: string[] }> = ({ errors }) => {
  if (!errors.length) return null;
  return (
    <ul className="space-y-1 text-xs text-rose-600">
      {errors.map((err, idx) => (
        <li key={`${err}-${idx}`}>{err}</li>
      ))}
    </ul>
  );
};

const renderField = (field: FieldSpec) => {
  const common =
    "w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/80 focus:ring-offset-1 focus:ring-offset-slate-50";
  const placeholder = field.help_text || field.label;
  if (field.type === "textarea") {
    return (
      <textarea
        id={field.id}
        name={field.name}
        defaultValue={field.value}
        className={`${common} min-h-[96px]`}
        placeholder={placeholder}
        required={field.required}
      />
    );
  }
  if (field.type === "select" && field.choices) {
    return (
      <select
        id={field.id}
        name={field.name}
        defaultValue={field.value}
        required={field.required}
        className={common}
      >
        {field.choices.map((choice) => (
          <option key={choice.value} value={choice.value}>
            {choice.label}
          </option>
        ))}
      </select>
    );
  }
  const inputType = field.type === "password" ? "password" : field.type === "email" ? "email" : "text";
  return (
    <input
      id={field.id}
      name={field.name}
      defaultValue={field.value}
      type={inputType}
      required={field.required}
      className={common}
      placeholder={placeholder}
      autoComplete={field.name}
    />
  );
};

const SettingsCard: React.FC<{ title: string; subtitle?: string; badge?: React.ReactNode; children: React.ReactNode }> = ({
  title,
  subtitle,
  badge,
  children,
}) => (
  <section className="rounded-3xl bg-white border border-slate-200 shadow-sm p-5 sm:p-6 space-y-4">
    <header className="flex items-center justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      {badge}
    </header>
    {children}
  </section>
);

const FormRenderer: React.FC<{
  spec: FormSpec;
  csrfToken: string;
  postUrl: string;
  label: string;
  twoColumn?: boolean;
}> = ({ spec, csrfToken, postUrl, label, twoColumn = true }) => {
  if (!spec) {
    return <p className="text-sm text-slate-500">Complete your business setup to edit {label.toLowerCase()}.</p>;
  }

  const normalizeName = (name: string) => {
    const parts = name.split("-");
    return parts[parts.length - 1];
  };
  const halfWidthFields = new Set(["first_name", "last_name", "currency", "name"]);
  const containerClass = twoColumn ? "grid gap-4 sm:grid-cols-2 text-sm" : "space-y-4 text-sm";

  return (
    <form method="POST" action={postUrl} className="space-y-4">
      <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
      <input type="hidden" name="form" value={spec.form} />
      {spec.non_field_errors.length > 0 && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3.5 py-2 text-sm text-rose-700">
          {spec.non_field_errors.join(" ")}
        </div>
      )}
      <div className={containerClass}>
        {spec.fields.map((field) => {
          const simpleName = normalizeName(field.name);
          const halfWidth = twoColumn && halfWidthFields.has(simpleName);
          const itemClass = `space-y-1.5 ${twoColumn && !halfWidth ? "sm:col-span-2" : ""}`;
          return (
            <div key={field.name} className={itemClass}>
            <label className="block text-slate-700 text-sm font-medium" htmlFor={field.id}>
              {field.label}
            </label>
            {renderField(field)}
            <FieldErrors errors={field.errors} />
          </div>
          );
        })}
      </div>
      <div className="flex justify-end">
        <button
          type="submit"
          className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2.5 text-xs font-semibold text-white hover:bg-slate-800 active:bg-slate-900"
        >
          Save {label.toLowerCase()}
        </button>
      </div>
    </form>
  );
};

const AccountSettingsPage: React.FC<{ data: AccountSettingsPayload }> = ({ data }) => {
  const tabs = useMemo(
    () => [
      { id: "profile", label: "Account" },
      { id: "business", label: "Business" },
      { id: "password", label: "Password" },
      { id: "sessions", label: "Sessions" },
    ],
    []
  );
  const [activeTab, setActiveTab] = useState<string>("profile");
  return (
    <div className="min-h-[calc(100vh-40px)] bg-slate-50 text-slate-900">
      <AlertStack messages={data.messages} />
      <div className="flex flex-col lg:flex-row gap-6">
        <nav className="flex lg:flex-col gap-2 rounded-3xl bg-white border border-slate-200 shadow-sm p-4 lg:w-64">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 lg:flex-none text-sm rounded-2xl px-3 py-2 border transition ${
                activeTab === tab.id
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="flex-1 space-y-6">
          {activeTab === "profile" && (
            <SettingsCard title="Your profile" subtitle="Basics we use on invoices and emails.">
              <FormRenderer
                spec={data.profileForm}
                csrfToken={data.csrfToken}
                postUrl={data.postUrl}
                label="Profile"
                twoColumn
              />
            </SettingsCard>
          )}
          {activeTab === "business" && (
            <SettingsCard
              title="Business details"
              subtitle="How your workspace shows up on invoices and reports."
              badge={
                <span className="inline-flex items-center rounded-full bg-slate-50 px-2.5 py-1 text-[11px] text-slate-600 border border-slate-200">
                  Workspace
                </span>
              }
            >
              <FormRenderer
                spec={data.businessForm}
                csrfToken={data.csrfToken}
                postUrl={data.postUrl}
                label="Business"
                twoColumn
              />
            </SettingsCard>
          )}
          {activeTab === "password" && (
            <SettingsCard
              title="Password"
              subtitle="Update your password to keep your books secure."
              badge={
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700 border border-emerald-100">
                  Recommended
                </span>
              }
            >
              <FormRenderer
                spec={data.passwordForm}
                csrfToken={data.csrfToken}
                postUrl={data.postUrl}
                label="Password"
                twoColumn={false}
              />
            </SettingsCard>
          )}
          {activeTab === "sessions" && (
            <SettingsCard title="Active sessions" subtitle="Devices currently signed in to this account.">
              <div className="space-y-3 text-sm">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-slate-900">{data.session?.device || "This device"}</p>
                    <p className="text-[11px] text-slate-500">
                      {data.session?.location ? `${data.session.location} · ` : ""}
                      Active now
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Current
                  </span>
                </div>
                <div className="flex justify-end">
                  <a
                    href={data.logoutUrl}
                    className="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Sign out of all sessions
                  </a>
                </div>
              </div>
            </SettingsCard>
          )}
        </div>
      </div>
    </div>
  );
};

export default AccountSettingsPage;
