import React, { ReactElement } from "react";
import { render, RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "../contexts/ToastContext";

/**
 * Custom render function that wraps components with necessary providers
 * for testing (MemoryRouter for Link/routing support, ToastProvider for toasts)
 */
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
    initialRoute?: string;
}

function AllTheProviders({ children, initialRoute = "/" }: { children: React.ReactNode; initialRoute?: string }) {
    return (
        <MemoryRouter initialEntries={[initialRoute]}>
            <ToastProvider>
                {children}
            </ToastProvider>
        </MemoryRouter>
    );
}

export function renderWithRouter(
    ui: ReactElement,
    options: CustomRenderOptions = {}
) {
    const { initialRoute, ...renderOptions } = options;
    return render(ui, {
        wrapper: ({ children }) => (
            <AllTheProviders initialRoute={initialRoute}>{children}</AllTheProviders>
        ),
        ...renderOptions,
    });
}

// Re-export everything from testing-library
export * from "@testing-library/react";

// Override render with our custom render
export { renderWithRouter as render };
