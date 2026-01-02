import React from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "../utils/cn";

const TELEMETRY_LINES = [
  "0101 1100 0110 1001 1001 0010 1110 1000",
  "0011 0101 1001 0100 0010 1111 0101 1001",
  "0110 1010 0011 0100 1100 1001 0110 0101",
  "1001 0101 0011 1100 0110 1010 1110 0011",
  "0100 1110 0110 1011 0011 1000 0101 1001",
];

export const TelemetryBackdrop: React.FC<{ className?: string }> = ({ className }) => {
  const reduceMotion = useReducedMotion();

  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 z-0 overflow-hidden",
        className
      )}
    >
      <div className="absolute -top-32 right-[-12rem] h-80 w-80 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(56,189,248,0.28),transparent_65%)] blur-3xl" />
      <div className="absolute -bottom-36 left-[-8rem] h-96 w-96 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(167,139,250,0.22),transparent_70%)] blur-3xl" />

      {TELEMETRY_LINES.map((line, index) => (
        <motion.div
          key={line}
          className="absolute select-none font-mono text-[10px] tracking-[0.48em] text-slate-700/30"
          style={{
            left: `${12 + index * 12}%`,
            top: `${18 + (index % 3) * 24}%`,
          }}
          animate={
            reduceMotion
              ? undefined
              : {
                  y: [0, -8, 0],
                  opacity: [0.12, 0.18, 0.12],
                }
          }
          transition={
            reduceMotion
              ? undefined
              : { duration: 9 + index * 0.8, repeat: Infinity, ease: "easeInOut" }
          }
        >
          {line}
        </motion.div>
      ))}

      <div className="absolute inset-0 opacity-40">
        <div className="absolute inset-0 bg-[radial-gradient(circle,rgba(15,23,42,0.08)_1px,transparent_1px)] [background-size:26px_26px]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle,rgba(148,163,184,0.08)_1px,transparent_1px)] [background-size:60px_60px]" />
      </div>
    </div>
  );
};

export default TelemetryBackdrop;
