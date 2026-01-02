import React from "react";
import { cn } from "../utils/cn";
import { TelemetryBackdrop } from "../components/TelemetryBackdrop";

export const AppShell: React.FC<
  React.HTMLAttributes<HTMLDivElement> & { withBackdrop?: boolean }
> = ({ className, children, withBackdrop = true, ...props }) => (
  <div className={cn("app-shell relative min-h-screen", className)} {...props}>
    {withBackdrop ? <TelemetryBackdrop /> : null}
    <div className="relative z-10 w-full">{children}</div>
  </div>
);
