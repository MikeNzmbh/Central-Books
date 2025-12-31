import React, { useEffect, useMemo, useRef, useState } from "react";
import { backendUrl } from "../utils/apiClient";
import { motion, AnimatePresence } from "framer-motion";
import {
    ArrowRight,
    Sparkles,
    ShieldCheck,
    Activity,
    LogIn,
    UserPlus,
    Mail,
    Lock,
    Eye,
    EyeOff,
    BadgeCheck,
    CalendarClock,
    Wallet,
    CreditCard,
    BarChart3,
    Menu,
    X,
    ChevronRight,
} from "lucide-react";

// ------------------------------------------------------------
// Clover Books — Auth Pages (Login + Create Account)
// Matches the Welcome / Reception site look:
// - White calm base, JetBrains Mono, spacious grid
// - Same Binary AntiGravity sphere background (subtle)
// - Auth layout: left form card + right "preview" panel
// - Branding: Black, Grey, Orange (#FF7E38)
// ------------------------------------------------------------

function clamp(n: number, a: number, b: number) {
    return Math.max(a, Math.min(b, n));
}
function lerp(a: number, b: number, t: number) {
    return a + (b - a) * t;
}
function classNames(...xs: Array<string | false | null | undefined>) {
    return xs.filter(Boolean).join(" ");
}

function usePrefersReducedMotion() {
    const [reduced, setReduced] = useState(false);
    useEffect(() => {
        const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
        if (!mq) return;
        const onChange = () => setReduced(!!mq.matches);
        onChange();
        mq.addEventListener?.("change", onChange);
        return () => mq.removeEventListener?.("change", onChange);
    }, []);
    return reduced;
}

type BinaryPoint = { theta: number; phi: number; seed: number; digit: 0 | 1 };

function makePoints(count: number): BinaryPoint[] {
    const pts: BinaryPoint[] = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
        const y = 1 - (i / (count - 1)) * 2;
        const radius = Math.sqrt(1 - y * y);
        const a = golden * i;
        const x = Math.cos(a) * radius;
        const z = Math.sin(a) * radius;
        const phi = Math.acos(clamp(y, -1, 1));
        const theta = Math.atan2(z, x);
        pts.push({ theta, phi, seed: (i * 97) % 997, digit: (i % 2) as 0 | 1 });
    }
    return pts;
}

function BinaryWarpSphere({
    targetRef,
    density = 1800,
    intensity = 0.75,
}: {
    targetRef: React.RefObject<HTMLElement | null>;
    density?: number;
    intensity?: number;
}) {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const points = useMemo(() => makePoints(density), [density]);
    const reducedMotion = usePrefersReducedMotion();

    useEffect(() => {
        const canvas = canvasRef.current;
        const target = targetRef.current;
        if (!canvas || !target) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        let raf = 0;
        const mouse = { x: 0, y: 0, active: false };
        const smooth = { x: 0, y: 0 };

        const setFromClient = (clientX: number, clientY: number) => {
            const rect = target.getBoundingClientRect();
            mouse.x = clientX - rect.left;
            mouse.y = clientY - rect.top;
            mouse.active = true;
        };

        const onPointerMove = (e: PointerEvent) => setFromClient(e.clientX, e.clientY);
        const onPointerDown = (e: PointerEvent) => setFromClient(e.clientX, e.clientY);
        const onPointerEnter = (e: PointerEvent) => setFromClient(e.clientX, e.clientY);
        const onPointerLeave = () => {
            const rect = target.getBoundingClientRect();
            mouse.x = rect.width / 2;
            mouse.y = rect.height / 2;
            mouse.active = false;
        };

        target.addEventListener("pointermove", onPointerMove, { passive: true });
        target.addEventListener("pointerdown", onPointerDown, { passive: true });
        target.addEventListener("pointerenter", onPointerEnter, { passive: true });
        target.addEventListener("pointerleave", onPointerLeave);

        const resize = () => {
            const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
            const rect = target.getBoundingClientRect();
            canvas.width = Math.floor(rect.width * dpr);
            canvas.height = Math.floor(rect.height * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

            if (mouse.x === 0 && mouse.y === 0) {
                mouse.x = rect.width / 2;
                mouse.y = rect.height / 2;
                smooth.x = mouse.x;
                smooth.y = mouse.y;
            }

            ctx.textBaseline = "middle";
            ctx.textAlign = "center";
        };

        resize();
        const ro = new ResizeObserver(resize);
        ro.observe(target);

        const draw = () => {
            const rect = target.getBoundingClientRect();
            const w = rect.width;
            const h = rect.height;

            const follow = reducedMotion ? 0.05 : 0.18;
            smooth.x = lerp(smooth.x, mouse.x, follow);
            smooth.y = lerp(smooth.y, mouse.y, follow);

            ctx.fillStyle = `rgba(246, 247, 249, ${0.18 / intensity})`;
            ctx.fillRect(0, 0, w, h);

            const t = (performance.now() || 0) * 0.001;
            const baseR = Math.min(w, h) * 0.52;
            const breath = reducedMotion ? 1 : 1 + 0.05 * Math.sin(t * 1.8);

            const rotY = reducedMotion ? 0.22 : t * 0.32;
            const rotX = reducedMotion ? -0.28 : Math.sin(t * 0.36) * 0.32;

            const cx = w / 2;
            const cy = h / 2;

            const centerPullX = (smooth.x - cx) * (reducedMotion ? 0.08 : 0.22);
            const centerPullY = (smooth.y - cy) * (reducedMotion ? 0.06 : 0.18);

            const mx = (smooth.x - cx) / Math.max(1, w);
            const my = (smooth.y - cy) / Math.max(1, h);
            const fieldX = mx * 200;
            const fieldY = my * 170;

            const buf: {
                x: number;
                y: number;
                z: number;
                a: number;
                s: number;
                d: 0 | 1;
                c: string;
            }[] = [];

            for (let i = 0; i < points.length; i++) {
                const p = points[i];

                const hill = reducedMotion
                    ? 0
                    : Math.sin(p.theta * 3.4 + t * 2.2 + p.seed * 0.01) * 13 +
                    Math.sin(p.phi * 2.8 - t * 1.8 + p.seed * 0.02) * 10;

                const r = baseR * breath + hill;

                const sp = Math.sin(p.phi);
                let x = r * sp * Math.cos(p.theta);
                let y = r * Math.cos(p.phi);
                let z = r * sp * Math.sin(p.theta);

                const cosX = Math.cos(rotX);
                const sinX = Math.sin(rotX);
                const y1 = y * cosX - z * sinX;
                const z1 = y * sinX + z * cosX;
                y = y1;
                z = z1;

                const cosY = Math.cos(rotY);
                const sinY = Math.sin(rotY);
                const x2 = x * cosY + z * sinY;
                const z2 = -x * sinY + z * cosY;
                x = x2;
                z = z2;

                const depth = clamp((z / (baseR * 1.35) + 1) / 2, 0, 1);
                const cursorInfluence = reducedMotion ? 0 : (0.22 + depth * 0.7);
                x += fieldX * cursorInfluence;
                y += fieldY * cursorInfluence;

                const fov = 760;
                const scale = fov / (fov + z + baseR * 1.9);

                const sx = cx + centerPullX + x * scale;
                const sy = cy + centerPullY + y * scale;

                if (sx < -70 || sx > w + 70 || sy < -70 || sy > h + 70) continue;

                // Orange accent for special points, grey for others
                const isAccent = (p.seed % 13 === 0) || (i % 23 === 0);
                const alphaBase = (0.01 + depth * 0.06) * intensity;
                const alpha = clamp(alphaBase * (isAccent ? 1.5 : 1), 0.008, 0.16);
                const size = clamp(lerp(9, 17, depth) * scale * 1.5, 7, 18);

                buf.push({
                    x: sx,
                    y: sy,
                    z,
                    a: alpha,
                    s: size,
                    d: p.digit,
                    c: isAccent ? "rgb(255, 126, 56)" : "rgb(120, 126, 138)", // Orange accent, grey default
                });
            }

            buf.sort((a, b) => a.z - b.z);
            for (const it of buf) {
                ctx.globalAlpha = it.a;
                ctx.font = `${it.s}px "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`;
                ctx.fillStyle = it.c;
                ctx.fillText(String(it.d), it.x, it.y);
            }

            ctx.globalAlpha = 1;
            raf = requestAnimationFrame(draw);
        };

        ctx.fillStyle = "rgb(246, 247, 249)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        raf = requestAnimationFrame(draw);

        return () => {
            cancelAnimationFrame(raf);
            ro.disconnect();
            target.removeEventListener("pointermove", onPointerMove);
            target.removeEventListener("pointerdown", onPointerDown);
            target.removeEventListener("pointerenter", onPointerEnter);
            target.removeEventListener("pointerleave", onPointerLeave);
        };
    }, [points, reducedMotion, targetRef, intensity]);

    return (
        <canvas
            ref={canvasRef}
            className="absolute inset-0 h-full w-full pointer-events-none select-none"
            aria-hidden="true"
        />
    );
}

function LogoMark() {
    return (
        <div className="flex items-center gap-4">
            <div className="relative">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-black/10 bg-white/85">
                    <img
                        src="/static/images/clover-logo.png"
                        alt="Clover Books"
                        className="h-8 w-8 rounded-xl object-cover"
                        onError={(e) => {
                            // Fallback to text if image fails
                            (e.target as HTMLImageElement).style.display = 'none';
                            (e.target as HTMLImageElement).parentElement!.innerHTML = '<span class="text-sm font-semibold tracking-tight text-black/90">CB</span>';
                        }}
                    />
                </div>
                <motion.div
                    className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-500"
                    animate={{ opacity: [0.25, 0.85, 0.25], scale: [1, 1.2, 1] }}
                    transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
                />
            </div>
            <div className="leading-tight">
                <div className="text-[13px] font-semibold tracking-wide text-black/90">Clover Books</div>
                <div className="text-[12px] text-black/55">Quiet confidence for owner-led teams.</div>
            </div>
        </div>
    );
}

function SoftInput({
    label,
    placeholder,
    type = "text",
    name,
    required,
    autoComplete,
    right,
}: {
    label: string;
    placeholder?: string;
    type?: string;
    name?: string;
    required?: boolean;
    autoComplete?: string;
    right?: React.ReactNode;
}) {
    return (
        <div className="grid gap-2">
            <div className="flex items-center justify-between">
                <div className="text-[12px] font-semibold text-black/65">{label}</div>
            </div>
            <div className="relative">
                <input
                    type={type}
                    name={name}
                    placeholder={placeholder}
                    required={required}
                    autoComplete={autoComplete}
                    className={classNames(
                        "w-full rounded-2xl border border-black/10 bg-white px-5 py-4 text-[13px] outline-none",
                        "focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40",
                        right ? "pr-12" : ""
                    )}
                />
                {right ? <div className="absolute right-3 top-1/2 -translate-y-1/2">{right}</div> : null}
            </div>
        </div>
    );
}

function SocialButton({ label, onClick }: { label: string; onClick?: () => void }) {
    return (
        <button
            type="button"
            onClick={onClick}
            className="inline-flex w-full items-center justify-center gap-3 rounded-2xl border border-black/10 bg-white px-5 py-3.5 text-[13px] font-semibold text-black/80 hover:bg-black/[0.02]"
        >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            {label}
        </button>
    );
}

function PrimaryButton({
    icon,
    label,
    onClick,
    type = "button",
}: {
    icon: React.ReactNode;
    label: string;
    onClick?: () => void;
    type?: "button" | "submit";
}) {
    return (
        <button
            type={type}
            onClick={onClick}
            className="group inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-black px-6 py-4 text-[13px] font-semibold text-white shadow-[0_18px_60px_rgba(0,0,0,0.12)] hover:bg-black/90"
        >
            {icon}
            {label}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </button>
    );
}

function PreviewPanel({
    mode,
}: {
    mode: "login" | "signup";
}) {
    // Dark preview panel (right side)
    return (
        <div className="relative overflow-hidden rounded-[34px] border border-black/10 bg-gradient-to-b from-[#1a1a1a] via-[#141414] to-[#0f0f0f] p-6 shadow-[0_40px_120px_rgba(0,0,0,0.14)]">
            <div className="absolute inset-0 opacity-25">
                <div className="absolute -left-40 top-[-120px] h-[520px] w-[520px] rounded-full bg-orange-500/20 blur-3xl" />
                <div className="absolute -right-48 bottom-[-140px] h-[620px] w-[620px] rounded-full bg-white/10 blur-3xl" />
            </div>

            <div className="relative">
                <div className="flex items-center justify-between">
                    <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-orange-400" />
                        <span className="text-[12px] font-medium text-white/75">
                            Live banking sync
                        </span>
                    </div>
                    <div className="text-[12px] text-white/55">Owner view</div>
                </div>

                <div className="mt-5 rounded-3xl bg-white/95 p-6 shadow-[0_20px_70px_rgba(0,0,0,0.20)]">
                    <div className="flex items-start justify-between gap-4">
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.22em] text-black/45">
                                TODAY'S CASH POSITION
                            </div>
                            <div className="mt-2 text-3xl font-semibold text-black/90 font-mono-soft">$124,830</div>
                        </div>
                        <div className="inline-flex items-center gap-2 rounded-full bg-orange-50 px-3 py-1.5 text-[12px] font-semibold text-orange-700">
                            +$8,420
                            <span className="font-medium text-orange-600/80">vs last 30d</span>
                        </div>
                    </div>

                    <div className="mt-5 rounded-3xl border border-black/10 bg-white p-5">
                        <div className="flex items-center justify-between">
                            <div className="text-[12px] font-semibold text-black/55">CASHFLOW</div>
                            <div className="text-[12px] font-semibold text-black/70">Aligned</div>
                        </div>
                        <div className="mt-4 grid grid-cols-5 gap-3">
                            {[
                                { h: 0.35, color: "bg-black/10" },
                                { h: 0.6, color: "bg-black/15" },
                                { h: 0.9, color: "bg-black/20" },
                                { h: 0.55, color: "bg-black/15" },
                                { h: 1, color: "bg-orange-300" }, // Orange accent on highest
                            ].map((bar, i) => (
                                <div
                                    key={i}
                                    className="flex items-end justify-center"
                                >
                                    <div
                                        className={`w-full rounded-2xl ${bar.color}`}
                                        style={{ height: `${Math.round(46 * bar.h) + 18}px` }}
                                    />
                                </div>
                            ))}
                        </div>
                        <div className="mt-4 flex items-center justify-between text-[12px] text-black/50">
                            <div>Invoices reconciled</div>
                            <div>Expenses posted</div>
                        </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-3">
                        <div className="rounded-2xl border border-black/10 bg-white p-4">
                            <div className="flex items-center justify-between">
                                <div className="text-[11px] font-semibold tracking-[0.22em] text-black/45">
                                    RECEIVABLES
                                </div>
                                <div className="inline-flex items-center gap-2 text-[12px] font-semibold text-orange-600">
                                    <span className="h-1.5 w-1.5 rounded-full bg-orange-500" /> Live
                                </div>
                            </div>
                            <div className="mt-2 text-xl font-semibold text-black/90 font-mono-soft">$38,900</div>
                        </div>
                        <div className="rounded-2xl border border-black/10 bg-white p-4">
                            <div className="flex items-center justify-between">
                                <div className="text-[11px] font-semibold tracking-[0.22em] text-black/45">
                                    PAYABLES
                                </div>
                                <div className="inline-flex items-center gap-2 text-[12px] font-semibold text-black/60">
                                    <span className="h-1.5 w-1.5 rounded-full bg-black/50" /> Live
                                </div>
                            </div>
                            <div className="mt-2 text-xl font-semibold text-black/90 font-mono-soft">$26,420</div>
                        </div>
                    </div>
                </div>

                <div className="mt-5 rounded-3xl border border-white/10 bg-white/10 p-6">
                    <div className="text-[11px] font-semibold tracking-[0.22em] text-white/55">
                        SCHEDULE
                    </div>
                    <div className="mt-4 grid gap-3">
                        {["Bank feed review", "Owner update", "Quiet close"].map((t, i) => (
                            <div key={t} className="flex items-center justify-between">
                                <div className="text-[13px] font-semibold text-white/85">{t}</div>
                                <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-[12px] font-semibold text-white/75 font-mono-soft">
                                    {i === 0 ? "9:30 AM" : i === 1 ? "11:00 AM" : "4:00 PM"}
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="mt-5 text-[12px] leading-[1.85] text-white/60">
                        {mode === "login"
                            ? "Sign in once. Clover keeps cash, revenue, and expenses aligned without tab juggling or exports."
                            : "Create an account. We'll guide your first setup so your books start clean — and stay clean."}
                    </div>
                </div>

                <div className="mt-5 grid grid-cols-3 gap-3">
                    {[{ i: <Wallet className="h-4 w-4" />, t: "Cash" }, { i: <CreditCard className="h-4 w-4" />, t: "Bank" }, { i: <BarChart3 className="h-4 w-4" />, t: "Reports" }].map(
                        (x) => (
                            <div
                                key={x.t}
                                className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3"
                            >
                                <div className="text-orange-400">{x.i}</div>
                                <div className="mt-2 text-[12px] font-semibold text-white/75">{x.t}</div>
                            </div>
                        )
                    )}
                </div>
            </div>
        </div>
    );
}

function AuthTopBar({
    mode,
    setMode,
    onBack,
}: {
    mode: "login" | "signup";
    setMode: (m: "login" | "signup") => void;
    onBack: () => void;
}) {
    const [open, setOpen] = useState(false);

    const pill = (
        <div className="flex items-center gap-1.5 rounded-full border border-black/10 bg-white/70 p-1.5 shadow-[0_18px_60px_rgba(0,0,0,0.06)]">
            {[{ k: "login", t: "Sign in" }, { k: "signup", t: "Create" }].map((x) => {
                const is = mode === (x.k as "login" | "signup");
                return (
                    <button
                        key={x.k}
                        onClick={() => setMode(x.k as "login" | "signup")}
                        className={classNames(
                            "relative rounded-full px-4 py-2.5 text-[12px] font-semibold transition",
                            is ? "text-black" : "text-black/55 hover:text-black/75"
                        )}
                    >
                        {x.t}
                        <AnimatePresence>
                            {is ? (
                                <motion.span
                                    layoutId="authDot"
                                    className="absolute -top-1 right-3 h-2 w-2 rounded-full bg-orange-500"
                                    initial={{ opacity: 0, scale: 0.8 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.8 }}
                                    transition={{ duration: 0.22 }}
                                />
                            ) : null}
                        </AnimatePresence>
                    </button>
                );
            })}
        </div>
    );

    return (
        <div className="sticky top-0 z-30 backdrop-blur-xl">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
                <button
                    onClick={onBack}
                    className="inline-flex items-center gap-2 rounded-2xl border border-black/10 bg-white/80 px-4 py-2.5 text-[13px] font-semibold text-black/70 hover:bg-white"
                >
                    <ChevronRight className="h-4 w-4 rotate-180" />
                    Reception
                </button>

                <div className="hidden md:block">{pill}</div>

                <div className="hidden md:flex items-center gap-3">
                    <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-3 py-2">
                        <Sparkles className="h-4 w-4 text-orange-500" />
                        <span className="text-[12px] font-medium text-black/55">Calm auth</span>
                    </div>
                </div>

                <button
                    onClick={() => setOpen(true)}
                    className="md:hidden inline-flex items-center justify-center rounded-2xl border border-black/10 bg-white/80 p-2.5"
                    aria-label="Open auth menu"
                >
                    <Menu className="h-5 w-5 text-black/80" />
                </button>

                <AnimatePresence>
                    {open ? (
                        <motion.div
                            className="fixed inset-0 z-50"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                        >
                            <div className="absolute inset-0 bg-black/25" onClick={() => setOpen(false)} />
                            <motion.div
                                className="absolute right-0 top-0 h-full w-[90%] max-w-[410px] bg-white shadow-[0_40px_120px_rgba(0,0,0,0.22)]"
                                initial={{ x: 28, opacity: 0 }}
                                animate={{ x: 0, opacity: 1 }}
                                exit={{ x: 28, opacity: 0 }}
                                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                            >
                                <div className="flex items-center justify-between border-b border-black/10 px-6 py-5">
                                    <div className="text-[13px] font-semibold text-black/80">Account</div>
                                    <button
                                        onClick={() => setOpen(false)}
                                        className="rounded-2xl border border-black/10 bg-white p-2"
                                        aria-label="Close menu"
                                    >
                                        <X className="h-5 w-5 text-black/70" />
                                    </button>
                                </div>

                                <div className="p-6">
                                    <div className="grid gap-2.5">
                                        <button
                                            onClick={() => {
                                                setMode("login");
                                                setOpen(false);
                                            }}
                                            className={classNames(
                                                "flex items-center justify-between rounded-2xl border px-5 py-4 text-left",
                                                mode === "login"
                                                    ? "border-orange-200 bg-orange-50/50"
                                                    : "border-black/10 bg-white hover:bg-black/[0.02]"
                                            )}
                                        >
                                            <div className="flex items-center gap-3.5">
                                                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-black/10 bg-white">
                                                    <LogIn className="h-4 w-4 text-black/65" />
                                                </div>
                                                <div>
                                                    <div className="text-[13px] font-semibold text-black/85">Sign in</div>
                                                    <div className="text-[12px] text-black/55">Continue to your workspace</div>
                                                </div>
                                            </div>
                                            <ChevronRight className="h-4 w-4 text-black/40" />
                                        </button>

                                        <button
                                            onClick={() => {
                                                setMode("signup");
                                                setOpen(false);
                                            }}
                                            className={classNames(
                                                "flex items-center justify-between rounded-2xl border px-5 py-4 text-left",
                                                mode === "signup"
                                                    ? "border-orange-200 bg-orange-50/50"
                                                    : "border-black/10 bg-white hover:bg-black/[0.02]"
                                            )}
                                        >
                                            <div className="flex items-center gap-3.5">
                                                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-black/10 bg-white">
                                                    <UserPlus className="h-4 w-4 text-black/65" />
                                                </div>
                                                <div>
                                                    <div className="text-[13px] font-semibold text-black/85">Create account</div>
                                                    <div className="text-[12px] text-black/55">Start clean books</div>
                                                </div>
                                            </div>
                                            <ChevronRight className="h-4 w-4 text-black/40" />
                                        </button>
                                    </div>
                                </div>
                            </motion.div>
                        </motion.div>
                    ) : null}
                </AnimatePresence>
            </div>
        </div>
    );
}

interface LoginCardProps {
    onSwitch: () => void;
    csrfToken?: string;
    action?: string;
    nextUrl?: string;
    errors?: string[];
    googleEnabled?: boolean;
    googleLoginUrl?: string;
}

function LoginCard({
    onSwitch,
    csrfToken = "",
    action = "/login/",
    nextUrl,
    errors = [],
    googleEnabled = true,
    googleLoginUrl = backendUrl("/accounts/google/login/")
}: LoginCardProps) {
    const [show, setShow] = useState(false);

    const googleLogin = () => {
        window.location.href = `${googleLoginUrl}?process=login`;
    };

    return (
        <div className="relative overflow-hidden rounded-[34px] border border-black/10 bg-white/80 p-8 shadow-[0_40px_120px_rgba(0,0,0,0.10)]">
            <div className="absolute inset-0 bg-[radial-gradient(900px_500px_at_70%_10%,rgba(255,126,56,0.04),rgba(0,0,0,0.00)_55%)]" />
            <div className="relative">
                <LogoMark />

                <div className="mt-7">
                    <div className="text-3xl font-semibold tracking-tight text-black/90">Sign in</div>
                    <div className="mt-2 text-[13px] leading-[1.9] text-black/55">
                        Use your email or username to unlock cash, ledgers, and banking in one place.
                    </div>
                </div>

                {errors.length > 0 && (
                    <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3">
                        {errors.map((err, i) => (
                            <p key={i} className="text-[13px] text-rose-700">{err}</p>
                        ))}
                    </div>
                )}

                <form method="post" action={action} className="mt-8 grid gap-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    {nextUrl && <input type="hidden" name="next" value={nextUrl} />}

                    <SoftInput
                        label="Email or username"
                        placeholder="you@studio.com"
                        name="username"
                        autoComplete="username"
                        required
                        right={<Mail className="h-4 w-4 text-black/35" />}
                    />

                    <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                            <div className="text-[12px] font-semibold text-black/65">Password</div>
                            <button type="button" className="text-[12px] font-semibold text-black/55 hover:text-black/75">
                                Forgot?
                            </button>
                        </div>
                        <div className="relative">
                            <input
                                type={show ? "text" : "password"}
                                name="password"
                                placeholder="••••••••"
                                required
                                autoComplete="current-password"
                                className="w-full rounded-2xl border border-black/10 bg-white px-5 py-4 text-[13px] outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40 pr-12"
                            />
                            <button
                                type="button"
                                onClick={() => setShow((s) => !s)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center justify-center rounded-xl border border-black/10 bg-white p-2 hover:bg-black/[0.02]"
                                aria-label={show ? "Hide password" : "Show password"}
                            >
                                {show ? (
                                    <EyeOff className="h-4 w-4 text-black/45" />
                                ) : (
                                    <Eye className="h-4 w-4 text-black/45" />
                                )}
                            </button>
                        </div>
                    </div>

                    <div className="flex items-center justify-between pt-1">
                        <label className="inline-flex items-center gap-2 text-[12px] text-black/60">
                            <input type="checkbox" name="remember" className="h-4 w-4 rounded border-black/20 text-orange-500 focus:ring-orange-500/30" />
                            Keep me signed in
                        </label>
                    </div>

                    <PrimaryButton type="submit" icon={<LogIn className="h-4 w-4" />} label="Sign in" />

                    {googleEnabled && (
                        <>
                            <div className="relative py-2">
                                <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-black/10" />
                                <div className="relative mx-auto w-fit rounded-full border border-black/10 bg-white px-4 py-1.5 text-[11px] font-semibold tracking-wide text-black/45">
                                    OR CONTINUE WITH
                                </div>
                            </div>

                            <SocialButton label="Continue with Google" onClick={googleLogin} />
                        </>
                    )}

                    <div className="pt-2 text-center text-[12px] text-black/55">
                        New to Clover Books?{" "}
                        <button type="button" onClick={onSwitch} className="font-semibold text-black/75 hover:text-black">
                            Create one
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

interface SignupCardProps {
    onSwitch: () => void;
    csrfToken?: string;
    action?: string;
    errors?: string[];
    googleEnabled?: boolean;
    googleLoginUrl?: string;
}

function SignupCard({
    onSwitch,
    csrfToken = "",
    action = "/signup/",
    errors = [],
    googleEnabled = true,
    googleLoginUrl = backendUrl("/accounts/google/login/")
}: SignupCardProps) {
    const [show, setShow] = useState(false);
    const [tier, setTier] = useState<"owner" | "accountant">("owner");

    const googleSignup = () => {
        window.location.href = `${googleLoginUrl}?process=signup`;
    };

    return (
        <div className="relative overflow-hidden rounded-[34px] border border-black/10 bg-white/80 p-8 shadow-[0_40px_120px_rgba(0,0,0,0.10)]">
            <div className="absolute inset-0 bg-[radial-gradient(900px_500px_at_70%_10%,rgba(255,126,56,0.04),rgba(0,0,0,0.00)_55%)]" />
            <div className="relative">
                <LogoMark />

                <div className="mt-7">
                    <div className="text-3xl font-semibold tracking-tight text-black/90">Create account</div>
                    <div className="mt-2 text-[13px] leading-[1.9] text-black/55">
                        Start clean. We'll set your workspace up for calm, traceable books.
                    </div>
                </div>

                {errors.length > 0 && (
                    <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3">
                        {errors.map((err, i) => (
                            <p key={i} className="text-[13px] text-rose-700">{err}</p>
                        ))}
                    </div>
                )}

                <form method="post" action={action} className="mt-8 grid gap-4">
                    <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
                    <input type="hidden" name="user_type" value={tier} />

                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <SoftInput label="Full name" placeholder="Your name" name="full_name" required />
                        <SoftInput label="Company" placeholder="Clover Studio" name="company_name" />
                    </div>

                    <SoftInput
                        label="Email"
                        placeholder="you@studio.com"
                        name="email"
                        type="email"
                        autoComplete="email"
                        required
                        right={<Mail className="h-4 w-4 text-black/35" />}
                    />

                    <div className="grid gap-2">
                        <div className="text-[12px] font-semibold text-black/65">Password</div>
                        <div className="relative">
                            <input
                                type={show ? "text" : "password"}
                                name="password"
                                placeholder="At least 8 characters"
                                required
                                autoComplete="new-password"
                                className="w-full rounded-2xl border border-black/10 bg-white px-5 py-4 text-[13px] outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-500/40 pr-12"
                            />
                            <button
                                type="button"
                                onClick={() => setShow((s) => !s)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 inline-flex items-center justify-center rounded-xl border border-black/10 bg-white p-2 hover:bg-black/[0.02]"
                                aria-label={show ? "Hide password" : "Show password"}
                            >
                                {show ? (
                                    <EyeOff className="h-4 w-4 text-black/45" />
                                ) : (
                                    <Eye className="h-4 w-4 text-black/45" />
                                )}
                            </button>
                        </div>
                    </div>

                    <div className="rounded-3xl border border-black/10 bg-white p-5">
                        <div className="text-[12px] font-semibold text-black/65">I'm signing up as</div>
                        <div className="mt-3 grid grid-cols-2 gap-2.5">
                            {[{ k: "owner", t: "Owner" }, { k: "accountant", t: "Accountant" }].map((x) => {
                                const is = tier === (x.k as "owner" | "accountant");
                                return (
                                    <button
                                        key={x.k}
                                        type="button"
                                        onClick={() => setTier(x.k as "owner" | "accountant")}
                                        className={classNames(
                                            "rounded-2xl border px-4 py-3 text-[13px] font-semibold transition",
                                            is
                                                ? "border-orange-300 bg-orange-500 text-white"
                                                : "border-black/10 bg-white text-black/70 hover:bg-black/[0.02]"
                                        )}
                                    >
                                        {x.t}
                                    </button>
                                );
                            })}
                        </div>
                        <div className="mt-3 text-[12px] leading-[1.85] text-black/55">
                            {tier === "owner"
                                ? "Owner setup emphasizes cash clarity and daily tasks."
                                : "Accountant setup emphasizes reviews, permissions, and exports."}
                        </div>
                    </div>

                    <label className="inline-flex items-start gap-2 text-[12px] leading-[1.85] text-black/60">
                        <input type="checkbox" name="terms" required className="mt-0.5 h-4 w-4 rounded border-black/20 text-orange-500 focus:ring-orange-500/30" />
                        <span>
                            I agree to the Terms and acknowledge the Privacy Policy.
                        </span>
                    </label>

                    <PrimaryButton type="submit" icon={<UserPlus className="h-4 w-4" />} label="Create account" />

                    {googleEnabled && (
                        <>
                            <div className="relative py-2">
                                <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-black/10" />
                                <div className="relative mx-auto w-fit rounded-full border border-black/10 bg-white px-4 py-1.5 text-[11px] font-semibold tracking-wide text-black/45">
                                    OR CONTINUE WITH
                                </div>
                            </div>

                            <SocialButton label="Continue with Google" onClick={googleSignup} />
                        </>
                    )}

                    <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
                        <div className="rounded-2xl border border-black/10 bg-white p-4">
                            <div className="flex items-center gap-2 text-[12px] font-semibold text-black/70">
                                <BadgeCheck className="h-4 w-4 text-orange-500" />
                                Audit-friendly trail
                            </div>
                            <div className="mt-2 text-[12px] leading-[1.85] text-black/55">
                                Every change stays explainable.
                            </div>
                        </div>
                        <div className="rounded-2xl border border-black/10 bg-white p-4">
                            <div className="flex items-center gap-2 text-[12px] font-semibold text-black/70">
                                <CalendarClock className="h-4 w-4 text-orange-500" />
                                Quiet close
                            </div>
                            <div className="mt-2 text-[12px] leading-[1.85] text-black/55">
                                Weekly routines, fewer surprises.
                            </div>
                        </div>
                    </div>

                    <div className="pt-2 text-center text-[12px] text-black/55">
                        Already have an account?{" "}
                        <button type="button" onClick={onSwitch} className="font-semibold text-black/75 hover:text-black">
                            Sign in
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

export interface AuthShellProps {
    mode: "login" | "signup";
    setMode: (m: "login" | "signup") => void;
    csrfToken?: string;
    loginAction?: string;
    signupAction?: string;
    nextUrl?: string;
    errors?: string[];
    googleEnabled?: boolean;
    googleLoginUrl?: string;
}

function AuthShell({
    mode,
    setMode,
    csrfToken = "",
    loginAction = "/login/",
    signupAction = "/signup/",
    nextUrl,
    errors = [],
    googleEnabled = true,
    googleLoginUrl = backendUrl("/accounts/google/login/"),
}: AuthShellProps) {
    const wrapRef = useRef<HTMLDivElement | null>(null);

    const go = (path: string) => {
        if (typeof window !== "undefined") window.location.href = path;
    };

    return (
        <div
            ref={wrapRef}
            className="relative min-h-screen overflow-hidden bg-[#F6F7F9] text-black"
        >
            {/* soft ambient */}
            <div className="pointer-events-none absolute inset-0">
                <div className="absolute -top-44 left-1/2 h-[780px] w-[780px] -translate-x-1/2 rounded-full bg-black/5 blur-3xl" />
                <div className="absolute bottom-[-300px] left-[-300px] h-[660px] w-[660px] rounded-full bg-orange-500/10 blur-3xl" />
                <div className="absolute bottom-[-320px] right-[-320px] h-[720px] w-[720px] rounded-full bg-black/4 blur-3xl" />
                <div className="absolute inset-0 bg-[radial-gradient(1200px_700px_at_50%_20%,rgba(255,126,56,0.04),rgba(0,0,0,0.00)_60%)]" />
            </div>

            {/* background animation */}
            <BinaryWarpSphere targetRef={wrapRef} density={1700} intensity={0.75} />

            {/* top bar */}
            <AuthTopBar
                mode={mode}
                setMode={setMode}
                onBack={() => go("/welcome/")}
            />

            {/* content */}
            <div className="mx-auto max-w-6xl px-6 pb-16 pt-8">
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:gap-6">
                    <motion.div
                        key={mode}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                        className="lg:col-span-7"
                    >
                        {mode === "login" ? (
                            <LoginCard
                                onSwitch={() => setMode("signup")}
                                csrfToken={csrfToken}
                                action={loginAction}
                                nextUrl={nextUrl}
                                errors={errors}
                                googleEnabled={googleEnabled}
                                googleLoginUrl={googleLoginUrl}
                            />
                        ) : (
                            <SignupCard
                                onSwitch={() => setMode("login")}
                                csrfToken={csrfToken}
                                action={signupAction}
                                errors={errors}
                                googleEnabled={googleEnabled}
                                googleLoginUrl={googleLoginUrl}
                            />
                        )}

                        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-[12px] text-black/55">
                            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2">
                                <ShieldCheck className="h-4 w-4 text-orange-500" />
                                <span>Secured session</span>
                            </div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2">
                                <Activity className="h-4 w-4 text-black/45" />
                                <span>Fast sign in</span>
                            </div>
                            <div className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2">
                                <Lock className="h-4 w-4 text-black/45" />
                                <span>Audit-friendly</span>
                            </div>
                        </div>
                    </motion.div>

                    <div className="lg:col-span-5">
                        <motion.div
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.7, delay: 0.06, ease: [0.22, 1, 0.36, 1] }}
                            className="lg:sticky lg:top-28"
                        >
                            <PreviewPanel mode={mode} />
                        </motion.div>
                    </div>
                </div>

                <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-black/10 pt-8 text-[12px] text-black/55 md:flex-row">
                    <div>© <span className="font-mono-soft">{new Date().getFullYear()}</span> Clover Books</div>
                    <div className="flex items-center gap-3">
                        <button className="hover:text-black/75">Security</button>
                        <span className="text-black/25">•</span>
                        <button className="hover:text-black/75">Privacy</button>
                        <span className="text-black/25">•</span>
                        <button
                            onClick={() => go("/welcome/")}
                            className="hover:text-black/75"
                        >
                            Reception
                        </button>
                    </div>
                </div>
            </div>

            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-[#F6F7F9] to-transparent" />
        </div>
    );
}

/**
 * Default export (Canvas demo):
 * - In your app, you can split these into routes:
 *   /login -> <AuthShell mode="login" />
 *   /signup -> <AuthShell mode="signup" />
 */
export default function CloverBooksAuthPages() {
    // Canvas-friendly mode switch.
    // In real routing, replace this with pathname-based selection.
    const [mode, setMode] = useState<"login" | "signup">("login");

    // If running under real routes, auto-detect once.
    useEffect(() => {
        try {
            const p = window.location.pathname || "";
            if (p.includes("signup") || p.includes("register")) setMode("signup");
            if (p.includes("login") || p.includes("signin")) setMode("login");
        } catch {
            // ignore
        }
    }, []);

    return <AuthShell mode={mode} setMode={setMode} />;
}

export interface CloverLoginPageProps {
    csrfToken?: string;
    action?: string;
    nextUrl?: string;
    errors?: string[];
    googleEnabled?: boolean;
    googleLoginUrl?: string;
}

export function CloverLoginPage(props: CloverLoginPageProps) {
    const [mode, setMode] = useState<"login" | "signup">("login");

    useEffect(() => {
        // If user switches to signup, redirect
        if (mode === "signup") {
            window.location.href = "/signup/";
        }
    }, [mode]);

    return (
        <AuthShell
            mode="login"
            setMode={setMode}
            csrfToken={props.csrfToken}
            loginAction={props.action}
            nextUrl={props.nextUrl}
            errors={props.errors}
            googleEnabled={props.googleEnabled}
            googleLoginUrl={props.googleLoginUrl}
        />
    );
}

export interface CloverSignupPageProps {
    csrfToken?: string;
    action?: string;
    errors?: string[];
    googleEnabled?: boolean;
    googleLoginUrl?: string;
}

export function CloverSignupPage(props: CloverSignupPageProps) {
    const [mode, setMode] = useState<"login" | "signup">("signup");

    useEffect(() => {
        // If user switches to login, redirect
        if (mode === "login") {
            window.location.href = "/login/";
        }
    }, [mode]);

    return (
        <AuthShell
            mode="signup"
            setMode={setMode}
            csrfToken={props.csrfToken}
            signupAction={props.action}
            errors={props.errors}
            googleEnabled={props.googleEnabled}
            googleLoginUrl={props.googleLoginUrl}
        />
    );
}
