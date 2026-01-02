// frontend/src/reports/ReportExportButton.tsx
import React from "react";

interface ReportExportButtonProps {
    /** URL to navigate to (opens in new tab for print view) */
    to?: string;
    /** Custom click handler (alternative to 'to') */
    onClick?: () => void;
    /** Button label */
    label?: string;
    /** Additional CSS classes */
    className?: string;
    /** Disabled state */
    disabled?: boolean;
}

/**
 * Reusable "Download PDF" button for reports.
 * Opens print-friendly view in new tab where users can use browser Print → "Save as PDF".
 */
export const ReportExportButton: React.FC<ReportExportButtonProps> = ({
    to,
    onClick,
    label = "Download PDF",
    className = "",
    disabled = false,
}) => {
    const handleClick = () => {
        if (disabled) return;

        if (onClick) {
            onClick();
        } else if (to) {
            // Open print view in new tab
            window.open(to, "_blank", "noopener");
        }
    };

    return (
        <button
            type="button"
            onClick={handleClick}
            disabled={disabled}
            className={`inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${className}`}
        >
            <svg
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
            >
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
                />
            </svg>
            <span>{label}</span>
        </button>
    );
};
