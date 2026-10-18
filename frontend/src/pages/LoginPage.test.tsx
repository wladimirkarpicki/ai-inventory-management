import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { signIn } = vi.hoisted(() => ({ signIn: vi.fn() }))

vi.mock("@/api", () => ({
  api: vi.fn(async () => ({ setup_required: false })),
}))

vi.mock("@/auth", () => ({
  useAuth: () => ({ signIn }),
}))

import { LoginPage } from "./LoginPage"

describe("LoginPage", () => {
  beforeEach(() => {
    signIn.mockReset()
  })

  it("renders the sign-in form", async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    expect(
      screen.getByRole("heading", { name: "Inventory Management System" })
    ).toBeInTheDocument()
    expect(screen.getAllByText("Sign in")).toHaveLength(2)
    expect(screen.getByLabelText("Username")).toBeInTheDocument()
    expect(screen.getByLabelText("Password")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: "Sign in" })
    ).toBeInTheDocument()
  })

  it("shows the error from a rejected sign-in", async () => {
    signIn.mockRejectedValueOnce(new Error("Invalid username or password."))

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    await userEvent.type(screen.getByLabelText("Username"), "nbk")
    await userEvent.type(screen.getByLabelText("Password"), "secret")
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }))

    expect(
      await screen.findByText("Invalid username or password.")
    ).toBeInTheDocument()
    expect(signIn).toHaveBeenCalledExactlyOnceWith("nbk", "secret")
  })
})
