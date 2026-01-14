import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { OnboardingProvider, useOnboarding, FAST_PATH_STEPS, GUIDED_PATH_STEPS } from "./OnboardingContext";
import { Sparkles, ArrowRight, Check, Building2, Target, Briefcase, Calendar, Database, Bot } from "lucide-react";
import "./onboarding.css";

// =============================================================================
// Step Components
// =============================================================================

const WelcomeStep: React.FC = () => {
    const { setStep, logEvent, setFastPath } = useOnboarding();

    useEffect(() => {
        logEvent("Onboarding_Started", {});
    }, [logEvent]);

    return (
        <div className="onboarding-step">
            <div className="onboarding-card text-center">
                {/* Animated hero icon */}
                <div className="onboarding-hero-icon">
                    <Sparkles className="w-10 h-10 text-white" />
                </div>

                <div className="space-y-4 mb-8">
                    <h1 className="onboarding-title">
                        Welcome to <span className="onboarding-title-gradient">Clover Books</span>
                    </h1>
                    <p className="onboarding-subtitle">
                        We'll only ask what we need. You can skip almost anything.
                    </p>
                </div>

                <div className="space-y-3">
                    <button
                        onClick={() => { setFastPath(true); setStep("intent"); }}
                        className="w-full onboarding-btn-primary group"
                    >
                        <span>Quick setup</span>
                        <span className="text-sm opacity-60">~2 min</span>
                        <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                    </button>
                    <button
                        onClick={() => { setFastPath(false); setStep("intent"); }}
                        className="w-full onboarding-btn-secondary group"
                    >
                        <span>Guided setup</span>
                        <span className="text-sm opacity-60">~5 min</span>
                        <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                    </button>
                </div>

                <p className="text-xs text-slate-400 mt-6">
                    You can always change your answers later in Settings.
                </p>
            </div>
        </div>
    );
};

const IntentStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const options = [
        { value: "track_expenses", label: "Track expenses", icon: Briefcase },
        { value: "invoice_customers", label: "Invoice customers", icon: Target },
        { value: "manage_inventory", label: "Manage inventory", icon: Database },
        { value: "all", label: "All of the above", icon: Check },
    ];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ intent: selected });
            logEvent("Onboarding_Step_Completed", { step: "intent", value: selected });
        }
        setStep("business_basics");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 1</p>
                <h2 className="text-2xl font-bold text-slate-900">What's your main goal?</h2>
                <p className="text-slate-600">This helps us customize your experience.</p>
            </div>

            <div className="grid gap-3">
                {options.map((opt) => (
                    <button
                        key={opt.value}
                        onClick={() => setSelected(opt.value)}
                        className={`flex items-center gap-4 rounded-2xl border px-4 py-4 text-left transition ${selected === opt.value
                            ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                    >
                        <opt.icon className="w-5 h-5" />
                        <span className="font-medium">{opt.label}</span>
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const BusinessBasicsStep: React.FC = () => {
    const { profile, updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [name, setName] = React.useState(profile.business_name || "");

    const handleNext = async () => {
        if (name.trim()) {
            await updateProfile({ business_name: name.trim() });
            logEvent("Onboarding_Step_Completed", { step: "business_basics" });
        }
        setStep("industry");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 2</p>
                <h2 className="text-2xl font-bold text-slate-900">What's your business called?</h2>
            </div>

            <div>
                <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full rounded-xl border border-slate-200 px-4 py-3 text-lg focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100 outline-none transition"
                    autoFocus
                />
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const IndustryStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, fastPath, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const industries = [
        "Retail", "Professional Services", "Restaurant/Food", "Construction",
        "Healthcare", "Technology", "Real Estate", "Other"
    ];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ industry: selected });
            logEvent("Onboarding_Step_Completed", { step: "industry", value: selected });
        }
        setStep(fastPath ? "team_size" : "entity");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 3</p>
                <h2 className="text-2xl font-bold text-slate-900">What industry are you in?</h2>
            </div>

            <div className="grid grid-cols-2 gap-3">
                {industries.map((ind) => (
                    <button
                        key={ind}
                        onClick={() => setSelected(ind)}
                        className={`rounded-xl border px-4 py-3 text-sm font-medium transition ${selected === ind
                            ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                    >
                        {ind}
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const EntityStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const entities = ["Sole Proprietor", "LLC", "S-Corp", "C-Corp", "Partnership", "Non-profit"];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ entity_type: selected });
            logEvent("Onboarding_Step_Completed", { step: "entity", value: selected });
        }
        setStep("fiscal_pulse");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 4</p>
                <h2 className="text-2xl font-bold text-slate-900">What type of entity?</h2>
                <p className="text-slate-600">This helps with tax categorization.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
                {entities.map((ent) => (
                    <button
                        key={ent}
                        onClick={() => setSelected(ent)}
                        className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium transition ${selected === ent
                            ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                    >
                        <Building2 className="w-4 h-4" />
                        {ent}
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const FiscalPulseStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const months = ["January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ fiscal_year_end: selected });
            logEvent("Onboarding_Step_Completed", { step: "fiscal_pulse", value: selected });
        }
        setStep("team_size");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 5</p>
                <h2 className="text-2xl font-bold text-slate-900">When does your fiscal year end?</h2>
            </div>

            <div className="grid grid-cols-3 gap-2">
                {months.map((month) => (
                    <button
                        key={month}
                        onClick={() => setSelected(month)}
                        className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition ${selected === month
                            ? "border-emerald-500 bg-emerald-50 text-emerald-900"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                    >
                        <Calendar className="w-3.5 h-3.5" />
                        {month}
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

// =============================================================================
// New Steps for Enhanced AI Companion Context
// =============================================================================

const TeamSizeStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, fastPath, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const sizes = [
        { value: "solo", label: "Just me", desc: "Solo operator" },
        { value: "2-5", label: "2-5 people", desc: "Small team" },
        { value: "6-20", label: "6-20 people", desc: "Growing team" },
        { value: "21-50", label: "21-50 people", desc: "Mid-size" },
        { value: "50+", label: "50+ people", desc: "Large organization" },
    ];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ employee_count: selected });
            logEvent("Onboarding_Step_Completed", { step: "team_size", value: selected });
        }
        setStep(fastPath ? "done" : "business_age");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-emerald-600 uppercase tracking-wide">Team</p>
                <h2 className="text-2xl font-bold text-slate-900">How big is your team?</h2>
                <p className="text-slate-600">This helps your AI Companion understand your scale.</p>
            </div>

            <div className="space-y-3">
                {sizes.map((size) => (
                    <button
                        key={size.value}
                        onClick={() => setSelected(size.value)}
                        className={`w-full flex items-center justify-between rounded-2xl border px-5 py-4 text-left transition ${selected === size.value
                            ? "border-emerald-500 bg-emerald-50 shadow-md"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                    >
                        <span className="font-medium text-slate-900">{size.label}</span>
                        <span className="text-sm text-slate-500">{size.desc}</span>
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const BusinessAgeStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const ages = [
        { value: "new", label: "Just starting", desc: "Haven't launched yet" },
        { value: "<1", label: "Less than 1 year", desc: "Recently launched" },
        { value: "1-3", label: "1-3 years", desc: "Established" },
        { value: "3-10", label: "3-10 years", desc: "Mature" },
        { value: "10+", label: "10+ years", desc: "Well established" },
    ];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ business_age: selected });
            logEvent("Onboarding_Step_Completed", { step: "business_age", value: selected });
        }
        setStep("challenges");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-emerald-600 uppercase tracking-wide">Experience</p>
                <h2 className="text-2xl font-bold text-slate-900">How long have you been in business?</h2>
            </div>

            <div className="space-y-3">
                {ages.map((age) => (
                    <button
                        key={age.value}
                        onClick={() => setSelected(age.value)}
                        className={`w-full flex items-center justify-between rounded-2xl border px-5 py-4 text-left transition ${selected === age.value
                            ? "border-emerald-500 bg-emerald-50 shadow-md"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                    >
                        <span className="font-medium text-slate-900">{age.label}</span>
                        <span className="text-sm text-slate-500">{age.desc}</span>
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const ChallengesStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string[]>([]);

    const challenges = [
        "Tracking cash flow",
        "Managing invoices",
        "Tax preparation",
        "Expense categorization",
        "Bank reconciliation",
        "Financial reporting",
        "Staying organized",
        "Saving time",
    ];

    const toggleChallenge = (challenge: string) => {
        setSelected(prev =>
            prev.includes(challenge)
                ? prev.filter(c => c !== challenge)
                : [...prev, challenge]
        );
    };

    const handleNext = async () => {
        if (selected.length > 0) {
            await updateProfile({ biggest_challenges: selected });
            logEvent("Onboarding_Step_Completed", { step: "challenges", value: selected });
        }
        setStep("current_tools");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-emerald-600 uppercase tracking-wide">Pain Points</p>
                <h2 className="text-2xl font-bold text-slate-900">What are your biggest challenges?</h2>
                <p className="text-slate-600">Select all that apply — this helps us focus your AI Companion.</p>
            </div>

            <div className="flex flex-wrap gap-2">
                {challenges.map((challenge) => (
                    <button
                        key={challenge}
                        onClick={() => toggleChallenge(challenge)}
                        className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition ${selected.includes(challenge)
                            ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            }`}
                    >
                        {selected.includes(challenge) && <Check className="w-3.5 h-3.5" />}
                        {challenge}
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const CurrentToolsStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const tools = [
        { value: "spreadsheets", label: "Spreadsheets", desc: "Excel, Google Sheets" },
        { value: "quickbooks", label: "QuickBooks", desc: "Desktop or Online" },
        { value: "xero", label: "Xero", desc: "Cloud accounting" },
        { value: "wave", label: "Wave", desc: "Free accounting" },
        { value: "freshbooks", label: "FreshBooks", desc: "Invoicing focus" },
        { value: "nothing", label: "Starting fresh", desc: "No existing system" },
    ];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ current_tools: selected });
            logEvent("Onboarding_Step_Completed", { step: "current_tools", value: selected });
        }
        setStep("transaction_volume");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-emerald-600 uppercase tracking-wide">Migration</p>
                <h2 className="text-2xl font-bold text-slate-900">What are you using today?</h2>
                <p className="text-slate-600">This helps us guide your data import.</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
                {tools.map((tool) => (
                    <button
                        key={tool.value}
                        onClick={() => setSelected(tool.value)}
                        className={`flex flex-col items-start gap-1 rounded-2xl border px-4 py-3 text-left transition ${selected === tool.value
                            ? "border-emerald-500 bg-emerald-50"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                    >
                        <span className="font-medium text-slate-900">{tool.label}</span>
                        <span className="text-xs text-slate-500">{tool.desc}</span>
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const TransactionVolumeStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [transactions, setTransactions] = React.useState<string | null>(null);
    const [accounts, setAccounts] = React.useState<string | null>(null);

    const txnVolumes = ["<50", "50-200", "200-500", "500-1000", "1000+"];
    const accountCounts = ["1", "2-3", "4-5", "6+"];

    const handleNext = async () => {
        const updates: { monthly_transactions?: string; bank_accounts_count?: string } = {};
        if (transactions) updates.monthly_transactions = transactions;
        if (accounts) updates.bank_accounts_count = accounts;
        if (Object.keys(updates).length > 0) {
            await updateProfile(updates);
            logEvent("Onboarding_Step_Completed", { step: "transaction_volume", ...updates });
        }
        setStep("accounting_habits");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-emerald-600 uppercase tracking-wide">Volume</p>
                <h2 className="text-2xl font-bold text-slate-900">How busy is your business?</h2>
            </div>

            <div className="space-y-6">
                <div>
                    <p className="text-sm font-medium text-slate-700 mb-3">Monthly transactions</p>
                    <div className="flex flex-wrap gap-2">
                        {txnVolumes.map((vol) => (
                            <button
                                key={vol}
                                onClick={() => setTransactions(vol)}
                                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${transactions === vol
                                    ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                                    }`}
                            >
                                {vol}
                            </button>
                        ))}
                    </div>
                </div>
                <div>
                    <p className="text-sm font-medium text-slate-700 mb-3">Bank accounts</p>
                    <div className="flex flex-wrap gap-2">
                        {accountCounts.map((count) => (
                            <button
                                key={count}
                                onClick={() => setAccounts(count)}
                                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${accounts === count
                                    ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                                    }`}
                            >
                                {count}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const AccountingHabitsStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [hasAccountant, setHasAccountant] = React.useState<boolean | null>(null);
    const [frequency, setFrequency] = React.useState<string | null>(null);

    const frequencies = [
        { value: "daily", label: "Daily" },
        { value: "weekly", label: "Weekly" },
        { value: "monthly", label: "Monthly" },
        { value: "quarterly", label: "Quarterly" },
        { value: "rarely", label: "Rarely / tax time only" },
    ];

    const handleNext = async () => {
        const updates: { has_accountant?: boolean; accounting_frequency?: string } = {};
        if (hasAccountant !== null) updates.has_accountant = hasAccountant;
        if (frequency) updates.accounting_frequency = frequency;
        if (Object.keys(updates).length > 0) {
            await updateProfile(updates);
            logEvent("Onboarding_Step_Completed", { step: "accounting_habits", ...updates });
        }
        setStep("data_source");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-emerald-600 uppercase tracking-wide">Habits</p>
                <h2 className="text-2xl font-bold text-slate-900">How do you handle your books?</h2>
            </div>

            <div className="space-y-6">
                <div>
                    <p className="text-sm font-medium text-slate-700 mb-3">Do you work with an accountant?</p>
                    <div className="flex gap-3">
                        <button
                            onClick={() => setHasAccountant(true)}
                            className={`flex-1 rounded-2xl border px-4 py-3 text-sm font-medium transition ${hasAccountant === true
                                ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                                }`}
                        >
                            Yes, I have one
                        </button>
                        <button
                            onClick={() => setHasAccountant(false)}
                            className={`flex-1 rounded-2xl border px-4 py-3 text-sm font-medium transition ${hasAccountant === false
                                ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                                }`}
                        >
                            No, I handle it myself
                        </button>
                    </div>
                </div>
                <div>
                    <p className="text-sm font-medium text-slate-700 mb-3">How often do you review finances?</p>
                    <div className="flex flex-wrap gap-2">
                        {frequencies.map((freq) => (
                            <button
                                key={freq.value}
                                onClick={() => setFrequency(freq.value)}
                                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${frequency === freq.value
                                    ? "border-emerald-500 bg-emerald-50 text-emerald-800"
                                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                                    }`}
                            >
                                {freq.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const DataSourceStep: React.FC = () => {
    const { updateProfile, setStep, skipStep, logEvent } = useOnboarding();
    const [selected, setSelected] = React.useState<string | null>(null);

    const sources = [
        { value: "bank_connect", label: "Connect my bank", desc: "Read-only access — we can't move money." },
        { value: "csv_import", label: "Import CSV/Excel", desc: "Upload historical transactions" },
        { value: "manual", label: "Enter manually", desc: "Start fresh with manual entry" },
    ];

    const handleNext = async () => {
        if (selected) {
            await updateProfile({ data_source: selected });
            logEvent("Onboarding_Step_Completed", { step: "data_source", value: selected });
        }
        setStep("ai_handshake");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 6</p>
                <h2 className="text-2xl font-bold text-slate-900">How do you want to get started?</h2>
            </div>

            <div className="space-y-3">
                {sources.map((src) => (
                    <button
                        key={src.value}
                        onClick={() => setSelected(src.value)}
                        className={`w-full flex flex-col items-start gap-1 rounded-2xl border px-5 py-4 text-left transition ${selected === src.value
                            ? "border-emerald-500 bg-emerald-50"
                            : "border-slate-200 bg-white hover:bg-slate-50"
                            }`}
                    >
                        <span className="font-medium text-slate-900">{src.label}</span>
                        <span className="text-sm text-slate-500">{src.desc}</span>
                    </button>
                ))}
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleNext}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Continue <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const AIHandshakeStep: React.FC = () => {
    const { setStep, skipStep, logEvent } = useOnboarding();

    const handleComplete = () => {
        logEvent("Onboarding_Step_Completed", { step: "ai_handshake" });
        setStep("done");
    };

    return (
        <div className="space-y-8 max-w-xl mx-auto">
            <div className="space-y-2">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wide">Step 7</p>
                <h2 className="text-2xl font-bold text-slate-900">Teach Clover in 30 seconds</h2>
                <p className="text-slate-600">
                    After you import transactions, we'll show you a few and ask simple questions to learn your categories.
                </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-center space-y-4">
                <Bot className="w-12 h-12 mx-auto text-slate-400" />
                <p className="text-slate-600">
                    Once you connect a bank or import data, we'll show you 3–5 sample transactions
                    and ask questions like "Is this usually for gas?"
                </p>
                <p className="text-sm text-slate-500">
                    Your answers help the AI categorize future transactions automatically.
                </p>
            </div>

            <div className="flex justify-between items-center pt-4">
                <button onClick={skipStep} className="text-sm text-slate-500 hover:text-slate-700">
                    Skip for now
                </button>
                <button
                    onClick={handleComplete}
                    className="rounded-xl bg-slate-900 px-6 py-2.5 text-white font-medium hover:bg-slate-800 transition flex items-center gap-2"
                >
                    Got it <ArrowRight className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

const DoneStep: React.FC = () => {
    const { profile, completeOnboarding } = useOnboarding();
    const navigate = useNavigate();

    const handleFinish = async () => {
        await completeOnboarding();
        navigate("/dashboard");
    };

    return (
        <div className="onboarding-step">
            <div className="onboarding-card text-center">
                {/* Animated completion icon */}
                <div className="onboarding-complete-icon">
                    <Check className="w-12 h-12 text-emerald-600" strokeWidth={3} />
                </div>

                <div className="space-y-3 mb-8">
                    <h2 className="onboarding-title">You're all set!</h2>
                    <p className="onboarding-subtitle">
                        {profile.business_name ? `Welcome, ${profile.business_name}` : "Welcome to Clover Books"}
                    </p>
                </div>

                <button
                    onClick={handleFinish}
                    className="w-full max-w-xs mx-auto onboarding-btn-primary group bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-600"
                    style={{ background: 'linear-gradient(135deg, #059669, #10b981)' }}
                >
                    Go to Dashboard <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </button>
            </div>
        </div>
    );
};

// =============================================================================
// Step Router
// =============================================================================

const StepRouter: React.FC = () => {
    const { currentStep, loading, fastPath } = useOnboarding();

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-pulse text-slate-400">Loading...</div>
            </div>
        );
    }

    const steps = fastPath ? FAST_PATH_STEPS : GUIDED_PATH_STEPS;
    const currentIndex = steps.indexOf(currentStep);
    const progress = currentIndex >= 0 ? ((currentIndex) / (steps.length - 1)) * 100 : 0;

    const renderStep = () => {
        switch (currentStep) {
            case "welcome": return <WelcomeStep />;
            case "intent": return <IntentStep />;
            case "business_basics": return <BusinessBasicsStep />;
            case "industry": return <IndustryStep />;
            case "entity": return <EntityStep />;
            case "fiscal_pulse": return <FiscalPulseStep />;
            // New enhanced AI context steps
            case "team_size": return <TeamSizeStep />;
            case "business_age": return <BusinessAgeStep />;
            case "challenges": return <ChallengesStep />;
            case "current_tools": return <CurrentToolsStep />;
            case "transaction_volume": return <TransactionVolumeStep />;
            case "accounting_habits": return <AccountingHabitsStep />;
            case "data_source": return <DataSourceStep />;
            case "ai_handshake": return <AIHandshakeStep />;
            case "done": return <DoneStep />;
            default: return <WelcomeStep />;
        }
    };

    return (
        <div className="onboarding-page onboarding-root">
            {/* Animated progress bar */}
            {currentStep !== "welcome" && currentStep !== "done" && (
                <div className="onboarding-progress">
                    <div
                        className="onboarding-progress-bar"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            )}

            <div className="onboarding-step-container">
                {renderStep()}
            </div>

            {/* Save indicator */}
            <SaveIndicator />
        </div>
    );
};

const SaveIndicator: React.FC = () => {
    const { syncStatus, error, resetError, retrySync } = useOnboarding();

    if (syncStatus === "synced" && !error) return null;

    return (
        <div className="fixed bottom-6 right-6 z-50">
            {syncStatus === "syncing" && (
                <div className="flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Saving...
                </div>
            )}
            {syncStatus === "offline" && !error && (
                <button
                    onClick={retrySync}
                    className="flex items-center gap-2 rounded-full bg-amber-500 px-4 py-2 text-sm text-white shadow-lg hover:bg-amber-600"
                >
                    <div className="w-2 h-2 rounded-full bg-white animate-pulse" />
                    Offline — tap to retry
                </button>
            )}
            {syncStatus === "synced" && (
                <div className="flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 text-sm text-white shadow-lg">
                    <div className="w-2 h-2 rounded-full bg-white" />
                    Saved ✓
                </div>
            )}
            {error && (
                <button
                    onClick={resetError}
                    className="flex items-center gap-2 rounded-full bg-rose-500 px-4 py-2 text-sm text-white shadow-lg hover:bg-rose-600"
                >
                    {error} — tap to dismiss
                </button>
            )}
        </div>
    );
};


// =============================================================================
// Main Page Component
// =============================================================================

const OnboardingPage: React.FC = () => {
    return (
        <OnboardingProvider>
            <StepRouter />
        </OnboardingProvider>
    );
};

export default OnboardingPage;
