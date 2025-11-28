import React, { useMemo, useState } from "react";

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

export interface AccountSettingsProps {
  csrfToken: string;
  profileForm: SerializedForm;
  businessForm: SerializedForm;
  passwordForm: SerializedForm;
  sessions: { current_ip?: string; user_agent?: string };
  postUrls: { profile: string; business: string; password: string; logoutAll: string };
  messages?: { level: string; message: string }[];
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
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-400">CERN Books</p>
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
  { id: "security", label: "Security" },
  { id: "sessions", label: "Sessions" },
];

const AccountSettingsPage: React.FC<AccountSettingsProps> = ({ csrfToken, profileForm, businessForm, passwordForm, sessions, postUrls, messages }) => {
  const [activeTab, setActiveTab] = useState<string>("profile");

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
      case "sessions":
        return (
          <Card title="Sessions" subtitle="Devices currently signed in to CERN Books.">
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
  }, [activeTab, profileForm, businessForm, passwordForm, sessions, csrfToken, postUrls]);

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
              {TABS.map((tab) => (
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
