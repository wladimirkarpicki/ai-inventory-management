import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))

vi.mock("@/api", () => ({
  api: apiMock,
  getToken: () => "test-token",
}))

// Recharts' ResponsiveContainer needs a ResizeObserver; jsdom has none.
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
)

import { DashboardPage } from "./DashboardPage"

const statsFixture = {
  products: 100,
  brands: 20,
  units_in_stock: 5000,
  inventory_value: 12345.0,
  low_stock: 2,
  low_stock_threshold: 5,
  low_stock_alerts: [],
}

const forecastFixture = {
  forecasts: [
    {
      product_id: 1,
      name: "Plain Widget",
      current_qty: 3,
      days_until_stockout: 4,
      recommended_restock_qty: 12,
      reorder_point: 10,
      lead_time_days: 7,
      ai_refined: false,
    },
    {
      product_id: 2,
      name: "Refined Widget",
      current_qty: 8,
      days_until_stockout: 6,
      recommended_restock_qty: 20,
      reorder_point: 10,
      lead_time_days: 7,
      ai_refined: true,
    },
  ],
  total: 2,
}

const lowStockFixture = {
  items: [
    {
      product_id: 3,
      name: "Depleted Thing",
      remaining_qty: 1,
      reorder_point: 10,
    },
  ],
  total: 30,
}

function pathsCalled(): string[] {
  return apiMock.mock.calls.map(([path]) => path as string)
}

describe("DashboardPage", () => {
  beforeEach(() => {
    apiMock.mockReset()
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/api/dashboard/stats")) return statsFixture
      if (path.startsWith("/api/forecast")) return forecastFixture
      if (path.startsWith("/api/low-stock")) return lowStockFixture
      if (path.startsWith("/api/movements/daily"))
        return { items: [], days: 30 }
      if (path.startsWith("/api/movements")) return { items: [], total: 0 }
      if (path.startsWith("/api/recommendations"))
        return { recommendations: [], total: 0 }
      throw new Error("unexpected api call: " + path)
    })
  })

  it("renders all five tabs with the forecast active by default", async () => {
    render(<DashboardPage />)

    const tabs = await screen.findAllByRole("tab")
    expect(tabs).toHaveLength(5)
    for (const name of [
      "Forecast",
      "Recommendations",
      "Stock dynamics",
      "Recent movements",
      "Low stock",
    ]) {
      expect(
        screen.getByRole("tab", { name: new RegExp(name, "i") })
      ).toBeInTheDocument()
    }

    // Default panel: the forecast table with its rows and the AI badge.
    expect(await screen.findByText("Plain Widget")).toBeInTheDocument()
    expect(screen.getByText("Refined Widget")).toBeInTheDocument()
    // The badge and its wrapping cell both carry the exact text "AI".
    expect(screen.getAllByText("AI").length).toBeGreaterThan(0)
  })

  it("lazy-loads tab data only when the tab is opened", async () => {
    render(<DashboardPage />)

    await screen.findByText("Plain Widget")
    expect(pathsCalled().some((p) => p.startsWith("/api/low-stock"))).toBe(false)

    await userEvent.click(
      screen.getByRole("tab", { name: /low stock/i })
    )

    expect(await screen.findByText("Depleted Thing")).toBeInTheDocument()
    expect(
      pathsCalled().some((p) => p.startsWith("/api/low-stock?limit=15&offset=0"))
    ).toBe(true)
  })

  it("pages the low-stock list through the pager", async () => {
    render(<DashboardPage />)

    await screen.findByText("Plain Widget")
    await userEvent.click(screen.getByRole("tab", { name: /low stock/i }))

    // 30 items over 15-per-page: first page range, Prev disabled.
    expect(await screen.findByText("1–15 of 30")).toBeInTheDocument()
    const prev = screen.getByRole("button", { name: "Prev" })
    expect(prev).toBeDisabled()

    await userEvent.click(screen.getByRole("button", { name: "Next" }))

    expect(await screen.findByText("16–30 of 30")).toBeInTheDocument()
    expect(
      pathsCalled().some((p) => p.startsWith("/api/low-stock?limit=15&offset=15"))
    ).toBe(true)
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Prev" })).toBeEnabled()
  })

  it("shows the low-stock threshold context in the panel", async () => {
    render(<DashboardPage />)

    await screen.findByText("Plain Widget")
    await userEvent.click(screen.getByRole("tab", { name: /low stock/i }))

    const panel = (await screen.findByText("Depleted Thing")).closest("table")
    expect(panel).not.toBeNull()
    const headers = within(panel!).getAllByRole("cell")
    const headerTexts = headers.map((h) => h.textContent)
    expect(headerTexts).toContain("Product")
    expect(headerTexts).toContain("Remaining")
    expect(headerTexts).toContain("Reorder point")
  })
})