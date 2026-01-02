import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight,
  Sparkles,
  ShieldCheck,
  Activity,
  LogIn,
  UserPlus,
  Menu,
  X,
  ChevronRight,
  Check,
  Lock,
  Globe,
  Zap,
  Layers,
  FileText,
  HelpCircle,
  Mail,
} from "lucide-react";

// ------------------------------------------------------------
// Clover Books — Reception / Welcome Website (WHITE)
// - Better navigator (sticky top + active section indicator + mobile drawer)
// - Binary AntiGravity sphere background (bigger, faster, some orange digits)
// - JetBrains Mono for numbers, SF Pro for text
// ------------------------------------------------------------

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

type BinaryPoint = {
  theta: number;
  phi: number;
  seed: number;
  digit: 0 | 1;
};

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

    pts.push({
      theta,
      phi,
      seed: (i * 97) % 997,
      digit: (i % 2) as 0 | 1,
    });
  }
  return pts;
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

function BinaryWarpSphere({
  density = 2600,
}: {
  density?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const points = useMemo(() => makePoints(density), [density]);
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;

    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2, active: false };
    const smooth = { x: window.innerWidth / 2, y: window.innerHeight / 2 };

    // Track cursor globally across entire window
    const onPointerMove = (e: PointerEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY + window.scrollY; // Account for scroll
      mouse.active = true;
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });

    // Extra width to extend beyond viewport
    const OVERFLOW = 300; // px on each side

    const resize = () => {
      const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
      // Canvas is wider than viewport to extend beyond edges
      const w = window.innerWidth + OVERFLOW * 2;
      const h = Math.max(document.documentElement.scrollHeight, window.innerHeight);
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.textBaseline = "middle";
      ctx.textAlign = "center";
    };

    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      const w = window.innerWidth + OVERFLOW * 2;
      const h = Math.max(document.documentElement.scrollHeight, window.innerHeight);

      // TIGHTER cursor follow (was 0.22, now 0.45 for snappier response)
      const follow = reducedMotion ? 0.08 : 0.45;
      smooth.x = lerp(smooth.x, mouse.x, follow);
      smooth.y = lerp(smooth.y, mouse.y, follow);

      // less fade = more motion/trails
      ctx.fillStyle = "rgba(246, 247, 249, 0.14)";
      ctx.fillRect(0, 0, w, h);

      const t = (performance.now() || 0) * 0.001;

      // BIG sphere
      const baseR = Math.min(w, h) * 0.56;

      // EVEN FASTER breathing (was 4.5, now 7.0)
      const breath = reducedMotion ? 1 : 1 + 0.10 * Math.sin(t * 7.0);

      // EVEN FASTER rotation (was 0.95, now 1.4)
      const rotY = reducedMotion ? 0.28 : t * 1.4;
      const rotX = reducedMotion ? -0.32 : Math.sin(t * 1.6) * 0.48;

      const cx = w / 2;
      const cy = h / 2;

      // STRONGER center pull toward cursor (was 0.5/0.4, now 0.6/0.5)
      const centerPullX = (smooth.x - cx) * (reducedMotion ? 0.12 : 0.6);
      const centerPullY = (smooth.y - cy) * (reducedMotion ? 0.10 : 0.5);

      // STRONGER warp field (was 320/280, now 400/350)
      const mx = (smooth.x - cx) / Math.max(1, w);
      const my = (smooth.y - cy) / Math.max(1, h);
      const fieldX = mx * 400;
      const fieldY = my * 350;

      const buf: { x: number; y: number; z: number; a: number; s: number; d: 0 | 1; c: string }[] = [];

      for (let i = 0; i < points.length; i++) {
        const p = points[i];

        // EVEN FASTER hills (was 6.5/5.5, now 10/8.5)
        const hill = reducedMotion
          ? 0
          : Math.sin(p.theta * 3.6 + t * 10 + p.seed * 0.01) * 20 +
          Math.sin(p.phi * 3.0 - t * 8.5 + p.seed * 0.02) * 16;

        const r = baseR * breath + hill;

        const sp = Math.sin(p.phi);
        let x = r * sp * Math.cos(p.theta);
        let y = r * Math.cos(p.phi);
        let z = r * sp * Math.sin(p.theta);

        // rotate X
        const cosX = Math.cos(rotX);
        const sinX = Math.sin(rotX);
        const y1 = y * cosX - z * sinX;
        const z1 = y * sinX + z * cosX;
        y = y1;
        z = z1;

        // rotate Y
        const cosY = Math.cos(rotY);
        const sinY = Math.sin(rotY);
        const x2 = x * cosY + z * sinY;
        const z2 = -x * sinY + z * cosY;
        x = x2;
        z = z2;

        const depth = clamp((z / (baseR * 1.35) + 1) / 2, 0, 1);

        const cursorInfluence = reducedMotion ? 0.0 : (0.28 + depth * 0.9);
        x += fieldX * cursorInfluence;
        y += fieldY * cursorInfluence;

        const fov = 760;
        const scale = fov / (fov + z + baseR * 1.95);

        const sx = cx + centerPullX + x * scale;
        const sy = cy + centerPullY + y * scale;

        if (sx < -70 || sx > w + 70 || sy < -70 || sy > h + 70) continue;

        // More orange digits, still tasteful
        const isAccent = (p.seed % 11 === 0) || (i % 17 === 0);

        const alphaBase = (0.011 + depth * 0.085) * (reducedMotion ? 0.85 : 1);
        const alpha = clamp(alphaBase * (isAccent ? 1.55 : 1), 0.01, 0.2);
        const size = clamp(lerp(9, 18, depth) * scale * 1.72, 7, 20);

        buf.push({
          x: sx,
          y: sy,
          z,
          a: alpha,
          s: size,
          d: p.digit,
          c: isAccent ? "rgb(255, 126, 56)" : "rgb(120, 126, 138)",
        });
      }

      buf.sort((a, b) => a.z - b.z);

      for (const it of buf) {
        ctx.globalAlpha = it.a;
        ctx.font = `${it.s}px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`;
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
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onPointerMove);
    };
  }, [points, reducedMotion]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed top-0 h-full pointer-events-none select-none"
      style={{
        left: '-300px',  // Offset to center the extended canvas
        width: 'calc(100vw + 600px)',
        minHeight: '100vh'
      }}
      aria-hidden="true"
    />
  );
}

function classNames(...xs: Array<string | false | null | undefined>) {
  return xs.filter(Boolean).join(" ");
}

function scrollToId(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  // Use window.scrollTo with offset to prevent scroll locking
  const y = el.getBoundingClientRect().top + window.scrollY - 100;
  window.scrollTo({ top: y, behavior: "smooth" });
}

function useActiveSection(sectionIds: string[]) {
  const [active, setActive] = useState(sectionIds[0] ?? "hero");

  useEffect(() => {
    const els = sectionIds
      .map((id) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];

    if (!els.length) return;

    const io = new IntersectionObserver(
      (entries) => {
        // Only update if user is not actively scrolling via nav click
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => (b.intersectionRatio ?? 0) - (a.intersectionRatio ?? 0));
        if (visible[0]?.target?.id) setActive(visible[0].target.id);
      },
      {
        root: null,
        // Reduced thresholds for faster detection
        threshold: [0.1, 0.25, 0.4],
        // Lighter margins so sections activate more naturally
        rootMargin: "-10% 0px -60% 0px",
      }
    );

    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [sectionIds.join("|")]);

  return active;
}

function TopNav({
  active,
  sections,
  onSignIn,
  onCreate,
}: {
  active: string;
  sections: Array<{ id: string; label: string; icon: React.ReactNode }>;
  onSignIn: () => void;
  onCreate: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 6);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const navPill = (
    <div className="relative">
      <div className="flex items-center gap-1 rounded-full border border-black/10 bg-white/70 p-1 shadow-[0_18px_60px_rgba(0,0,0,0.06)]">
        {sections.map((s) => {
          const is = active === s.id;
          return (
            <button
              key={s.id}
              onClick={() => {
                setOpen(false);
                scrollToId(s.id);
              }}
              className={classNames(
                "relative flex items-center gap-2 rounded-full px-3 py-2 text-[12.5px] font-medium transition",
                is
                  ? "text-black"
                  : "text-black/55 hover:text-black/75"
              )}
            >
              <span className="hidden lg:inline-flex">{s.label}</span>
              <span className="lg:hidden">{s.icon}</span>

              {/* active dot */}
              <AnimatePresence>
                {is ? (
                  <motion.span
                    layoutId="navDot"
                    className="absolute -top-1 right-2 h-2 w-2 rounded-full bg-black/70"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.12, ease: "easeOut" }}
                  />
                ) : null}
              </AnimatePresence>
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <>
      {/* Static header with logo - NOT sticky */}
      <div className="relative z-20 bg-transparent">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-black/10 bg-white/80">
                <span className="text-sm font-semibold tracking-tight text-black/90">
                  CB
                </span>
              </div>
              <motion.div
                className="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-black/70"
                animate={{ opacity: [0.25, 0.85, 0.25], scale: [1, 1.2, 1] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
              />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-wide text-black/90">
                Clover Books
              </div>
              <div className="text-[12px] text-black/55">
                Calm accounting, real data.
              </div>
            </div>
          </div>

          {/* Right actions - static */}
          <div className="hidden items-center gap-2 md:flex">
            <button
              onClick={onSignIn}
              className="rounded-2xl border border-black/10 bg-white/80 px-4 py-2 text-[13px] text-black/80 hover:bg-white"
            >
              Sign in
            </button>
            <button
              onClick={onCreate}
              className="rounded-2xl border border-black/10 bg-black px-4 py-2 text-[13px] text-white hover:bg-black/90"
            >
              Create account
            </button>
          </div>

          {/* Mobile menu button */}
          <button
            onClick={() => setOpen(true)}
            className="md:hidden inline-flex items-center justify-center rounded-2xl border border-black/10 bg-white/80 p-2"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5 text-black/80" />
          </button>
        </div>
      </div>

      {/* Floating nav pill - ONLY this is sticky with frosted glass */}
      <div
        className={classNames(
          "fixed top-4 left-1/2 -translate-x-1/2 z-50 hidden md:block",
          "transition-all duration-300 ease-out",
          scrolled
            ? "bg-white/75 backdrop-blur-2xl backdrop-saturate-150 rounded-full shadow-[0_4px_20px_rgba(0,0,0,0.08),0_1px_3px_rgba(0,0,0,0.05)]"
            : ""
        )}
      >
        {navPill}
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {
          open ? (
            <motion.div
              className="fixed inset-0 z-50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div
                className="absolute inset-0 bg-black/25"
                onClick={() => setOpen(false)}
              />
              <motion.div
                className="absolute right-0 top-0 h-full w-[88%] max-w-[380px] bg-white shadow-[0_40px_120px_rgba(0,0,0,0.22)]"
                initial={{ x: 24, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: 24, opacity: 0 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                <div className="flex items-center justify-between border-b border-black/10 px-5 py-4">
                  <div className="text-[13px] font-semibold text-black/80">
                    Navigate
                  </div>
                  <button
                    onClick={() => setOpen(false)}
                    className="rounded-2xl border border-black/10 bg-white p-2"
                    aria-label="Close menu"
                  >
                    <X className="h-5 w-5 text-black/70" />
                  </button>
                </div>

                <div className="p-5">
                  <div className="grid gap-2">
                    {sections.map((s) => {
                      const is = active === s.id;
                      return (
                        <button
                          key={s.id}
                          onClick={() => {
                            setOpen(false);
                            scrollToId(s.id);
                          }}
                          className={classNames(
                            "flex items-center justify-between rounded-2xl border px-4 py-3 text-left",
                            is
                              ? "border-black/15 bg-black/[0.03]"
                              : "border-black/10 bg-white hover:bg-black/[0.02]"
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-2xl border border-black/10 bg-white">
                              {s.icon}
                            </div>
                            <div>
                              <div className="text-[13px] font-semibold text-black/85">
                                {s.label}
                              </div>
                              <div className="text-[12px] text-black/55">
                                Jump to section
                              </div>
                            </div>
                          </div>
                          <ChevronRight className="h-4 w-4 text-black/40" />
                        </button>
                      );
                    })}
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-2">
                    <button
                      onClick={() => {
                        setOpen(false);
                        onSignIn();
                      }}
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-[13px] font-semibold text-black/80"
                    >
                      Sign in
                    </button>
                    <button
                      onClick={() => {
                        setOpen(false);
                        onCreate();
                      }}
                      className="rounded-2xl border border-black/10 bg-black px-4 py-3 text-[13px] font-semibold text-white"
                    >
                      Create
                    </button>
                  </div>
                </div>
              </motion.div>
            </motion.div>
          ) : null
        }
      </AnimatePresence >
    </>
  );
}

function SectionShell({
  id,
  eyebrow,
  title,
  subtitle,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="relative scroll-mt-28 py-16">
      <div className="mx-auto max-w-6xl px-6">
        <div className="max-w-2xl">
          <div className="text-[12px] font-semibold tracking-wide text-black/55 uppercase">
            {eyebrow}
          </div>
          <div className="mt-3 text-3xl font-semibold tracking-tight text-black/90 md:text-4xl">
            {title}
          </div>
          {subtitle ? (
            <div className="mt-3 text-[15px] leading-relaxed text-black/55">
              {subtitle}
            </div>
          ) : null}
        </div>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

function Card({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="group relative overflow-hidden rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
      <div className="absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100">
        <div className="absolute -left-20 top-0 h-72 w-72 rounded-full bg-black/5 blur-3xl" />
        <div className="absolute -right-24 bottom-0 h-72 w-72 rounded-full bg-black/4 blur-3xl" />
      </div>
      <div className="relative flex items-start gap-4">
        <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl border border-black/10 bg-white">
          {icon}
        </div>
        <div>
          <div className="text-[13px] font-semibold tracking-wide text-black/90">
            {title}
          </div>
          <div className="mt-1 text-[13px] leading-relaxed text-black/55">
            {desc}
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureDropdown({
  title,
  description,
  benefit,
}: {
  title: string;
  description: string;
  benefit: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-2xl border border-black/10 bg-white overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between p-4 text-left hover:bg-black/[0.02] transition-colors"
      >
        <div className="text-[13px] font-semibold text-black/80">{title}</div>
        <motion.div
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronRight className="h-4 w-4 text-black/40" />
        </motion.div>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-black/5">
              <div className="pt-3 text-[12px] leading-relaxed text-black/60">
                {description}
              </div>
              <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-orange-50 px-3 py-1.5">
                <Check className="h-3.5 w-3.5 text-orange-600" />
                <span className="text-[11px] font-medium text-orange-700">{benefit}</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function PricingCard({
  name,
  price,
  blurb,
  features,
  highlighted,
  cta,
  onClick,
}: {
  name: string;
  price: string;
  blurb: string;
  features: string[];
  highlighted?: boolean;
  cta: string;
  onClick: () => void;
}) {
  return (
    <div
      className={classNames(
        "relative overflow-hidden rounded-3xl border p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]",
        highlighted
          ? "border-black/15 bg-black text-white"
          : "border-black/10 bg-white/75"
      )}
    >
      {highlighted ? (
        <div className="absolute inset-0 opacity-25">
          <div className="absolute -left-28 top-0 h-80 w-80 rounded-full bg-white/15 blur-3xl" />
          <div className="absolute -right-24 bottom-0 h-80 w-80 rounded-full bg-white/10 blur-3xl" />
        </div>
      ) : null}

      <div className="relative">
        <div className={classNames("text-[13px] font-semibold", highlighted ? "text-white" : "text-black/90")}>
          {name}
        </div>
        {/* JetBrains Mono for pricing numbers */}
        <div className={classNames("mt-3 text-3xl font-semibold font-mono-soft", highlighted ? "text-white" : "text-black/90")}>
          {price}
        </div>
        <div className={classNames("mt-2 text-[13px] leading-relaxed", highlighted ? "text-white/75" : "text-black/55")}>
          {blurb}
        </div>

        <div className="mt-6 space-y-2">
          {features.map((f) => (
            <div key={f} className="flex items-start gap-2">
              <Check className={classNames("mt-0.5 h-4 w-4", highlighted ? "text-white" : "text-black/70")} />
              <div className={classNames("text-[13px]", highlighted ? "text-white/80" : "text-black/60")}>
                {f}
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={onClick}
          className={classNames(
            "mt-7 inline-flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-3 text-[13px] font-semibold transition",
            highlighted
              ? "bg-white text-black hover:bg-white/90"
              : "border border-black/10 bg-black text-white hover:bg-black/90"
          )}
        >
          {cta}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export default function CloverBooksWelcomePage() {
  const wrapRef = useRef<HTMLDivElement | null>(null);

  // If you're using react-router, swap these for `useNavigate()`.
  const go = (path: string) => {
    if (typeof window !== "undefined") window.location.href = path;
  };

  const sections = useMemo(
    () => [
      { id: "hero", label: "Overview", icon: <Sparkles className="h-4 w-4 text-black/65" /> },
      { id: "product", label: "Product", icon: <Layers className="h-4 w-4 text-black/65" /> },
      { id: "how", label: "How it works", icon: <Zap className="h-4 w-4 text-black/65" /> },
      { id: "pricing", label: "Pricing", icon: <FileText className="h-4 w-4 text-black/65" /> },
      { id: "security", label: "Security", icon: <Lock className="h-4 w-4 text-black/65" /> },
      { id: "faq", label: "FAQ", icon: <HelpCircle className="h-4 w-4 text-black/65" /> },
      { id: "contact", label: "Contact", icon: <Mail className="h-4 w-4 text-black/65" /> },
    ],
    []
  );

  const active = useActiveSection(sections.map((s) => s.id));

  return (
    <div ref={wrapRef} className="relative min-h-screen overflow-hidden bg-[#F6F7F9] text-black font-sans">
      {/* subtle grey accents */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-44 left-1/2 h-[720px] w-[720px] -translate-x-1/2 rounded-full bg-black/5 blur-3xl" />
        <div className="absolute bottom-[-280px] left-[-280px] h-[620px] w-[620px] rounded-full bg-black/4 blur-3xl" />
        <div className="absolute bottom-[-300px] right-[-300px] h-[680px] w-[680px] rounded-full bg-black/4 blur-3xl" />
        <div className="absolute inset-0 bg-[radial-gradient(1200px_700px_at_50%_20%,rgba(0,0,0,0.06),rgba(0,0,0,0.00)_60%)]" />
      </div>

      {/* Binary anti-gravity sphere */}
      <BinaryWarpSphere />

      {/* Better Navigator */}
      <TopNav
        active={active}
        sections={sections}
        onSignIn={() => go("/login")}
        onCreate={() => go("/signup")}
      />

      {/* HERO */}
      <section id="hero" className="relative scroll-mt-28">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-6 pb-16 pt-10 md:grid-cols-12 md:gap-8 md:pb-20">
          <div className="md:col-span-7">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              className="inline-flex items-center gap-2 rounded-full border border-black/10 bg-white/75 px-3 py-1"
            >
              <Sparkles className="h-4 w-4 text-black/70" />
              <span className="text-[12px] font-medium text-black/60">
                Reception website — built for first impressions
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.05, ease: [0.22, 1, 0.36, 1] }}
              className="mt-6 text-4xl font-semibold tracking-tight md:text-6xl text-black/90"
            >
              Stop chasing numbers.
              <span className="text-black/55"> Start making decisions.</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
              className="mt-4 max-w-xl text-[15px] leading-relaxed text-black/55"
            >
              Clover Books turns your messy finances into clear, actionable insights.
              Bank sync, AI categorization, and one-click reports — all in a workspace
              that's actually designed for humans. Join 2,000+ businesses who closed their books 80% faster.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
              className="mt-8 flex flex-col gap-3 sm:flex-row"
            >
              <button
                onClick={() => go("/signup")}
                className="group inline-flex items-center justify-center gap-2 rounded-2xl bg-black px-5 py-3 text-[13px] font-semibold text-white shadow-[0_18px_60px_rgba(0,0,0,0.12)] hover:shadow-[0_18px_70px_rgba(0,0,0,0.16)]"
              >
                Start Free — No Credit Card
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </button>

              <button
                onClick={() => scrollToId("how")}
                className="group inline-flex items-center justify-center gap-2 rounded-2xl border border-black/10 bg-white/75 px-5 py-3 text-[13px] font-semibold text-black/80 hover:bg-white"
              >
                See How It Works
                <ChevronRight className="h-4 w-4" />
              </button>
            </motion.div>

            {/* Quick value props - compact horizontal layout */}
            <div className="mt-10 flex flex-wrap gap-3">
              <div className="inline-flex items-center gap-3 rounded-2xl border border-black/10 bg-white/80 px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-black/5">
                  <Activity className="h-4 w-4 text-black/70" />
                </div>
                <div>
                  <div className="text-[12px] font-semibold text-black/85">Real-time visibility</div>
                  <div className="text-[11px] text-black/50">Cash, receivables, spending</div>
                </div>
              </div>
              <div className="inline-flex items-center gap-3 rounded-2xl border border-black/10 bg-white/80 px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-black/5">
                  <ShieldCheck className="h-4 w-4 text-black/70" />
                </div>
                <div>
                  <div className="text-[12px] font-semibold text-black/85">Audit-ready books</div>
                  <div className="text-[11px] text-black/50">Receipts attached, changes logged</div>
                </div>
              </div>
              <div className="inline-flex items-center gap-3 rounded-2xl border border-black/10 bg-white/80 px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-black/5">
                  <Globe className="h-4 w-4 text-black/70" />
                </div>
                <div>
                  <div className="text-[12px] font-semibold text-black/85">Team collaboration</div>
                  <div className="text-[11px] text-black/50">Invite accountants & partners</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Feature showcase with expandable dropdowns */}
          <div className="md:col-span-5">
            <motion.div
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="relative overflow-hidden rounded-[28px] border border-black/10 bg-white/75 p-5 shadow-[0_40px_120px_rgba(0,0,0,0.10)]"
            >
              <div className="absolute inset-0 bg-[radial-gradient(900px_500px_at_70%_10%,rgba(0,0,0,0.06),rgba(0,0,0,0.00)_55%)]" />
              <div className="relative">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-[13px] font-semibold text-black/85">
                      Why teams switch to Clover
                    </div>
                    <div className="mt-1 text-[12px] text-black/55">
                      Click to learn what makes us different
                    </div>
                  </div>
                  <motion.div
                    className="h-2 w-2 rounded-full bg-orange-500"
                    animate={{ opacity: [0.4, 1, 0.4], scale: [1, 1.15, 1] }}
                    transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                  />
                </div>

                <div className="mt-5 grid gap-2">
                  <FeatureDropdown
                    title="Real-Time Financial Visibility"
                    description="Know your cash position, outstanding invoices, and spending patterns at a glance. No more logging into three different tools."
                    benefit="Make better decisions, faster."
                  />
                  <FeatureDropdown
                    title="AI-Powered Automation"
                    description="Transactions categorized in seconds. Receipts matched automatically. Learn from your corrections so you never repeat yourself."
                    benefit="Cut bookkeeping time by 80%."
                  />
                  <FeatureDropdown
                    title="One-Click Bank Reconciliation"
                    description="Connect your bank once. We pull transactions daily, match them to your records, and flag anything that needs attention."
                    benefit="Month-end close in 15 minutes."
                  />
                  <FeatureDropdown
                    title="Audit-Ready Documentation"
                    description="Every transaction gets a receipt. Every change gets logged. Generate professional reports for accountants, investors, or tax authorities."
                    benefit="Sleep well during tax season."
                  />
                  <FeatureDropdown
                    title="Team Collaboration Built In"
                    description="Invite your accountant, bookkeeper, or co-founder. Role-based permissions mean everyone sees exactly what they need."
                    benefit="End the spreadsheet email chains."
                  />
                </div>

                <div className="mt-4 rounded-2xl bg-gradient-to-r from-black to-black/90 p-4">
                  <div className="text-[12px] font-medium text-white/80">Join 2,000+ businesses</div>
                  <div className="mt-1 text-[13px] text-white/60">
                    Set up in 10 minutes. No credit card required.
                  </div>
                  <button
                    onClick={() => go("/signup")}
                    className="mt-3 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-[12px] font-semibold text-black hover:bg-white/90"
                  >
                    Start Your Free Trial
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* PRODUCT */}
      <SectionShell
        id="product"
        eyebrow="THE PROBLEM WE SOLVE"
        title="Bookkeeping shouldn't feel like a second job"
        subtitle="You started a business to build something great — not to drown in spreadsheets. Clover Books handles the busywork so you can focus on what matters."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card
            icon={<Layers className="h-5 w-5 text-black/65" />}
            title="One Dashboard, Zero Guesswork"
            desc="Cash balance, who owes you, what you owe — everything you need to make decisions, on one screen."
          />
          <Card
            icon={<Zap className="h-5 w-5 text-black/65" />}
            title="AI That Works 24/7"
            desc="Transactions categorized automatically. Receipts matched to expenses. Rules that learn from your corrections."
          />
          <Card
            icon={<ShieldCheck className="h-5 w-5 text-black/65" />}
            title="Built for When the Tax Man Calls"
            desc="Every change logged. Every receipt attached. Generate audit-ready reports in seconds, not hours."
          />
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
            <div className="text-[13px] font-semibold text-black/85">What You Get</div>
            <div className="mt-3 grid gap-2 text-[13px] text-black/65">
              {[
                "Real-time cash flow & P&L dashboard",
                "Automatic bank sync (100+ banks)",
                "AI-powered transaction categorization",
                "Receipt capture with OCR",
                "One-click bank reconciliation",
                "Professional reports for tax time",
              ].map((x) => (
                <div key={x} className="flex items-start gap-2">
                  <Check className="mt-0.5 h-4 w-4 text-black/60" />
                  <span>{x}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
            <div className="text-[13px] font-semibold text-black/85">What Our Users Say</div>
            <div className="mt-3 text-[13px] leading-relaxed text-black/60">
              "I used to spend every Sunday doing books. Now it takes 15 minutes on Friday afternoon.
              Clover paid for itself the first month."
            </div>
            <div className="mt-2 text-[12px] text-black/45">— Marcus T., Consulting Firm Owner</div>
            <div className="mt-6 grid gap-2">
              {["Saves 5+ hours/week", "80% faster close", "Zero missed deductions", "Accountant-approved"].map(
                (x) => (
                  <div
                    key={x}
                    className="inline-flex w-fit items-center gap-2 rounded-full border border-black/10 bg-white px-3 py-1 text-[12px] font-medium text-black/70"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                    {x}
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      </SectionShell>

      {/* HOW IT WORKS */}
      <SectionShell
        id="how"
        eyebrow="GET STARTED IN MINUTES"
        title="From signup to synced books in under 10 minutes"
        subtitle="No complicated setup. No accountant required. Just connect, review, and go."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[
            {
              t: "Connect Your Bank",
              d: "Link your bank accounts in 60 seconds. We support 100+ banks with bank-level encryption.",
            },
            { t: "Watch the Magic", d: "Our AI instantly categorizes transactions and matches receipts. You just review." },
            { t: "Approve with a Click", d: "One-click approvals. Bulk actions. Everything stays in your control." },
            { t: "Export When Ready", d: "Professional reports for your accountant, the tax office, or yourself." },
          ].map((s, idx) => (
            <div
              key={s.t}
              className="relative overflow-hidden rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]"
            >
              {/* JetBrains Mono for step numbers */}
              <div className="absolute right-5 top-5 text-[12px] font-semibold text-black/35 font-mono-soft">
                0{idx + 1}
              </div>
              <div className="text-[13px] font-semibold text-black/85">{s.t}</div>
              <div className="mt-2 text-[13px] leading-relaxed text-black/55">
                {s.d}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
          <div className="text-[13px] font-semibold text-black/85">
            No learning curve. No onboarding call. No kidding.
          </div>
          <div className="mt-2 text-[13px] leading-relaxed text-black/60">
            Most users are fully set up and running their first reconciliation within 15 minutes.
            That's not a typo. When you make software simple, people actually use it.
          </div>
        </div>
      </SectionShell>

      {/* PRICING */}
      <SectionShell
        id="pricing"
        eyebrow="TRANSPARENT PRICING"
        title="Plans that grow with your business"
        subtitle="Start free. Upgrade when you're ready. No hidden fees. No surprise charges. Cancel anytime."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <PricingCard
            name="Free"
            price="$0"
            blurb="Perfect for freelancers and side projects. No credit card required."
            features={["Up to 100 transactions/mo", "Bank sync (1 account)", "Receipt capture", "Basic reports"]}
            cta="Start Free"
            onClick={() => go("/signup")}
          />
          <PricingCard
            name="Growth"
            price="$49"
            blurb="For businesses ready to save serious time. Most popular choice."
            features={["Unlimited transactions", "Unlimited bank accounts", "AI categorization", "Full reconciliation", "Team access (3 seats)", "Priority email support"]}
            highlighted
            cta="Start 14-Day Trial"
            onClick={() => go("/signup")}
          />
          <PricingCard
            name="Firm"
            price="Custom"
            blurb="For accountants and firms with multiple clients. Volume discounts available."
            features={["Multi-workspace", "Client management", "Custom workflows", "Dedicated success manager", "API access"]}
            cta="Book a Demo"
            onClick={() => scrollToId("contact")}
          />
        </div>
      </SectionShell>

      {/* SECURITY */}
      <SectionShell
        id="security"
        eyebrow="YOUR DATA, PROTECTED"
        title="Bank-level security. Zero compromises."
        subtitle="Your financial data is sensitive. We treat it that way. SOC 2 compliant. 256-bit encryption. Always."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Card
            icon={<Lock className="h-5 w-5 text-black/65" />}
            title="Role-Based Permissions"
            desc="Owner, bookkeeper, accountant, viewer — everyone gets exactly the access they need. Nothing more."
          />
          <Card
            icon={<ShieldCheck className="h-5 w-5 text-black/65" />}
            title="Complete Audit Trail"
            desc="Every change is timestamped and logged. Who modified what, when, and why — no mysteries."
          />
          <Card
            icon={<FileText className="h-5 w-5 text-black/65" />}
            title="Proof on Every Transaction"
            desc="Receipts, invoices, and documents attached directly. When auditors ask, you'll have answers."
          />
        </div>

        <div className="mt-6 rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
          <div className="text-[13px] font-semibold text-black/85">We never sell your data. Ever.</div>
          <div className="mt-2 text-[13px] leading-relaxed text-black/60">
            Your books are yours. We use end-to-end encryption, host on secure infrastructure,
            and never monetize your financial information. You're the customer, not the product.
          </div>
        </div>
      </SectionShell>

      {/* FAQ */}
      <SectionShell
        id="faq"
        eyebrow="GOT QUESTIONS?"
        title="Answers to what you're probably wondering"
        subtitle="The stuff people actually ask us. Straight answers, no fluff."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {[
            {
              q: "Can this replace QuickBooks / Xero?",
              a: "For most small businesses, yes. We built Clover Books for people who found traditional accounting software confusing and slow. If you want simpler, faster, and smarter — you're in the right place.",
            },
            {
              q: "What if I already have an accountant?",
              a: "Great! Invite them. Many accountants love Clover because the books arrive pre-organized, and they can review everything in one place. You'll save them time (and maybe save yourself some fees).",
            },
            {
              q: "Is my data safe?",
              a: "Absolutely. 256-bit encryption, SOC 2 compliance, and bank-level security. We use the same security standards as major financial institutions.",
            },
            {
              q: "What happens if I want to leave?",
              a: "Export everything anytime. Your data is yours. We provide complete exports in standard formats. No lock-in, no hostage situations.",
            },
          ].map((x) => (
            <div
              key={x.q}
              className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]"
            >
              <div className="text-[13px] font-semibold text-black/85">{x.q}</div>
              <div className="mt-2 text-[13px] leading-relaxed text-black/60">{x.a}</div>
            </div>
          ))}
        </div>
      </SectionShell>

      {/* CONTACT */}
      <SectionShell
        id="contact"
        eyebrow="LET'S TALK"
        title="Ready to simplify your books?"
        subtitle="Questions? Curious about enterprise plans? Want a personalized demo? We're here."
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="md:col-span-2 rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
            <div className="text-[13px] font-semibold text-black/85">Send us a message</div>
            <div className="mt-2 text-[13px] text-black/55">
              We typically respond within 2 hours during business hours.
            </div>
            <div className="mt-5 grid gap-3">
              <input
                placeholder="Your name"
                className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-[13px] outline-none focus:ring-2 focus:ring-black/10"
              />
              <input
                placeholder="Work email"
                className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-[13px] outline-none focus:ring-2 focus:ring-black/10"
              />
              <textarea
                placeholder="What can we help you with?"
                rows={4}
                className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-[13px] outline-none focus:ring-2 focus:ring-black/10"
              />
              <button className="inline-flex items-center justify-center gap-2 rounded-2xl bg-black px-5 py-3 text-[13px] font-semibold text-white hover:bg-black/90">
                Send Message
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_30px_90px_rgba(0,0,0,0.07)]">
            <div className="text-[13px] font-semibold text-black/85">Shortcuts</div>
            <div className="mt-4 grid gap-2">
              <button
                onClick={() => go("/login")}
                className="inline-flex items-center justify-between rounded-2xl border border-black/10 bg-white px-4 py-3 text-[13px] font-semibold text-black/80 hover:bg-black/[0.02]"
              >
                Sign in
                <LogIn className="h-4 w-4 text-black/50" />
              </button>
              <button
                onClick={() => go("/signup")}
                className="inline-flex items-center justify-between rounded-2xl border border-black/10 bg-black px-4 py-3 text-[13px] font-semibold text-white hover:bg-black/90"
              >
                Create account
                <UserPlus className="h-4 w-4 text-white/80" />
              </button>
              <div className="mt-3 rounded-2xl border border-black/10 bg-white p-4">
                <div className="text-[12px] text-black/55">Email</div>
                <div className="mt-1 text-[13px] font-semibold text-black/80">
                  hello@cloverbooks.app
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-black/10 pt-8 text-[12px] text-black/55 md:flex-row">
          {/* JetBrains Mono for year */}
          <div>© <span className="font-mono-soft">{new Date().getFullYear()}</span> Clover Books</div>
          <div className="flex items-center gap-3">
            <button onClick={() => scrollToId("security")} className="hover:text-black/75">
              Security
            </button>
            <span className="text-black/25">•</span>
            <button onClick={() => scrollToId("faq")} className="hover:text-black/75">
              FAQ
            </button>
            <span className="text-black/25">•</span>
            <button onClick={() => go("/login")} className="hover:text-black/75">
              Sign in
            </button>
          </div>
        </div>
      </SectionShell>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-[#F6F7F9] to-transparent" />
    </div>
  );
}
