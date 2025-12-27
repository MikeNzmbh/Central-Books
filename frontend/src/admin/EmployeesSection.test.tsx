import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { EmployeesSection } from "./EmployeesSection";

vi.mock("./api", () => {
  const activeEmployee = {
    id: 1,
    user_id: 10,
    name: "Jane Doe",
    email: "jane@example.com",
    title: "Ops",
    department: "Operations",
    admin_panel_access: true,
    primary_admin_role: "support",
    is_active_employee: true,
    last_login: "2025-12-01T10:01:00Z",
    workspace_scope: { mode: "all" },
    invite: null,
  };

  const pendingEmployee = {
    id: 2,
    user_id: 11,
    name: "Pending User",
    email: "pending@example.com",
    title: "",
    department: "",
    admin_panel_access: false,
    primary_admin_role: "support",
    is_active_employee: false,
    last_login: null,
    workspace_scope: { mode: "all" },
    invite: {
      id: "inv-1",
      status: "pending",
      invited_at: "2025-12-01T10:01:00Z",
      expires_at: "2025-12-08T10:01:00Z",
      invite_url: "/internal-admin/invite/inv-1",
      email_send_failed: false,
      email_last_error: "",
    },
  };

  return {
    fetchEmployees: vi.fn().mockResolvedValue({ results: [activeEmployee, pendingEmployee], next: null, previous: null }),
    inviteEmployee: vi.fn().mockResolvedValue({
      ...pendingEmployee,
      invite: { ...pendingEmployee.invite, email_send_failed: true },
    }),
    resendInvite: vi.fn().mockResolvedValue(pendingEmployee),
    updateEmployee: vi.fn().mockResolvedValue(activeEmployee),
    suspendEmployee: vi.fn().mockResolvedValue({ ...activeEmployee, admin_panel_access: false, is_active_employee: false }),
    reactivateEmployee: vi.fn().mockResolvedValue(activeEmployee),
    deleteEmployee: vi.fn().mockResolvedValue({ success: true }),
  };
});

describe("EmployeesSection", () => {
  it("renders Not authorized without canManageAdminUsers", async () => {
    render(<EmployeesSection canManageAdminUsers={false} canGrantSuperadmin={false} />);
    expect(screen.getByText(/Not authorized/i)).toBeInTheDocument();
  });

  it("loads and renders employees list", async () => {
    render(<EmployeesSection canManageAdminUsers={true} canGrantSuperadmin={false} />);
    await waitFor(() => expect(screen.getByText(/^Employees$/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getAllByText(/jane@example.com/i).length).toBeGreaterThan(0));
  });

  it("shows pending invite actions and allows copy link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<EmployeesSection canManageAdminUsers={true} canGrantSuperadmin={false} />);
    await waitFor(() => expect(screen.getAllByText(/pending@example.com/i).length).toBeGreaterThan(0));

    expect(screen.getByText(/Pending invite/i)).toBeInTheDocument();
    const copy = screen.getByRole("button", { name: /Copy link/i });
    fireEvent.click(copy);

    await waitFor(() => expect(writeText).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText(/Invite link copied/i)).toBeInTheDocument());
  });

  it("deactivates an employee via confirmation dialog", async () => {
    render(<EmployeesSection canManageAdminUsers={true} canGrantSuperadmin={true} />);
    await waitFor(() => expect(screen.getAllByText(/jane@example.com/i).length).toBeGreaterThan(0));

    const deactivate = screen.getAllByRole("button", { name: /^Deactivate$/i })[0];
    fireEvent.click(deactivate);

    await waitFor(() => expect(screen.getByText(/Deactivate employee/i)).toBeInTheDocument());
    const input = screen.getByLabelText(/Confirm action/i);
    fireEvent.change(input, { target: { value: "DEACTIVATE" } });

    const confirmButtons = screen.getAllByRole("button", { name: /^Deactivate$/i });
    const confirm = confirmButtons[confirmButtons.length - 1];
    fireEvent.click(confirm);

    await waitFor(() => expect(screen.getByText(/Employee deactivated/i)).toBeInTheDocument());
  });

  it("invite modal calls invite API and surfaces email failure notice", async () => {
    render(<EmployeesSection canManageAdminUsers={true} canGrantSuperadmin={false} />);

    const open = screen.getByRole("button", { name: /Invite employee/i });
    fireEvent.click(open);

    await waitFor(() =>
      expect(screen.getByPlaceholderText(/jane@cloverbooks.com/i)).toBeInTheDocument()
    );
    fireEvent.change(screen.getByPlaceholderText(/jane@cloverbooks.com/i), { target: { value: "new@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /^Send invite$/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/Invite created but email failed/i)
      ).toBeInTheDocument()
    );
  });
});
