// Panel — reusable dark-mode card used across the command center.
//
// Provides a consistent bordered surface with an optional header (icon, title,
// subtitle) and an actions slot. Presentational and composable.

import type { ComponentType, ReactNode } from "react";

export interface PanelProps {
  title?: string;
  subtitle?: string;
  /** A lucide-react (or compatible) icon component. */
  icon?: ComponentType<{ className?: string }>;
  /** Content rendered on the right side of the header (buttons, badges). */
  actions?: ReactNode;
  children?: ReactNode;
  /** Accessible label for the region; defaults to `title`. */
  ariaLabel?: string;
  className?: string;
  bodyClassName?: string;
}

/** A bordered dark-mode card with an optional header row. */
export function Panel({
  title,
  subtitle,
  icon: Icon,
  actions,
  children,
  ariaLabel,
  className,
  bodyClassName,
}: PanelProps) {
  const hasHeader = Boolean(title || subtitle || Icon || actions);

  return (
    <section
      aria-label={ariaLabel ?? title}
      className={`flex flex-col rounded-xl border border-surface-700 bg-surface-900/60 ${className ?? ""}`}
    >
      {hasHeader && (
        <div className="flex items-center justify-between gap-3 border-b border-surface-700 px-5 py-3">
          <div className="flex items-center gap-3">
            {Icon && (
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10 text-accent">
                <Icon className="h-4 w-4" />
              </span>
            )}
            <div>
              {title && <h2 className="text-sm font-semibold text-slate-100">{title}</h2>}
              {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={`flex-1 p-5 ${bodyClassName ?? ""}`}>{children}</div>
    </section>
  );
}

export default Panel;
