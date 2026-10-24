import { useEffect, useMemo, useState } from "react"
import {
  BanknoteIcon,
  BoxesIcon,
  ClipboardListIcon,
  DownloadIcon,
  HistoryIcon,
  LineChartIcon,
  PackageIcon,
  PlusIcon,
  TagsIcon,
  TriangleAlertIcon,
  TruckIcon,
  BarChart2,
} from "lucide-react"
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { toast } from "sonner"

import {
  api,
  getToken,
  type DailyMovement,
  type ForecastPage,
  type LowStockPage,
  type MovementPage,
  type OrderPage,
  type OrderRow,
  type Product,
  type RecommendationPage,
  type Stats,
  type TopMovers,
} from "@/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableHeader, TableRow, TableCell, TableBody } from "@/components/ui/table"

const PAGE_LIMIT = 15

async function downloadMovementsCsv() {
  const token = getToken()

  try {
    const response = await fetch("/api/export/movements.csv", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })

    if (!response.ok) {
      toast.error(`Export failed (${response.status}).`)
      return
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "movements.csv"
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    toast.error("Export failed.")
  }
}

function money(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  })
}

function compactMoney(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
  if (value >= 10_000) return `$${(value / 1_000).toFixed(1)}K`
  return money(value)
}

function formatDays(days: number | null | undefined): string {
  if (days === undefined || days === null || days === 9999) return "N/A"
  if (days < 0) return "—"
  return `${days} d`
}

function formatQty(value: number): string {
  return value > 0 ? `+${value.toLocaleString("en-US")}` : value.toLocaleString("en-US")
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("en-US")
}

function formatDayTick(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

function Pager({
  offset,
  total,
  onOffsetChange,
}: {
  offset: number
  total: number
  onOffsetChange: (offset: number) => void
}) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + PAGE_LIMIT, total)
  return (
    <div className="mt-2 flex items-center justify-end gap-2">
      <span className="text-xs text-muted-foreground tabular-nums">
        {from}–{to} of {total.toLocaleString("en-US")}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={offset === 0}
        onClick={() => onOffsetChange(Math.max(0, offset - PAGE_LIMIT))}
      >
        Prev
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={to >= total}
        onClick={() => onOffsetChange(offset + PAGE_LIMIT)}
      >
        Next
      </Button>
    </div>
  )
}

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [activeTab, setActiveTab] = useState<"forecast" | "recommendations" | "dynamics" | "movements" | "lowstock" | "orders">("forecast")

  const [forecastPage, setForecastPage] = useState<ForecastPage | null>(null)
  const [forecastOffset, setForecastOffset] = useState(0)

  const [recommendationPage, setRecommendationPage] = useState<RecommendationPage | null>(null)
  const [recommendationOffset, setRecommendationOffset] = useState(0)

  const [movementPage, setMovementPage] = useState<MovementPage | null>(null)
  const [movementOffset, setMovementOffset] = useState(0)

  const [daily, setDaily] = useState<DailyMovement[] | null>(null)
  const [dynamicsDays, setDynamicsDays] = useState(30)
  const [dynamicsView, setDynamicsView] = useState<"flow" | "top" | "daily">("flow")
  const [topMovers, setTopMovers] = useState<TopMovers | null>(null)

  const [lowStockPage, setLowStockPage] = useState<LowStockPage | null>(null)
  const [lowStockOffset, setLowStockOffset] = useState(0)

  const [ordersPage, setOrdersPage] = useState<OrderPage | null>(null)
  const [ordersOffset, setOrdersOffset] = useState(0)
  const [ordersVersion, setOrdersVersion] = useState(0)
  const [orderBusy, setOrderBusy] = useState(false)

  // New-order dialog state: product typeahead + qty.
  const [orderOpen, setOrderOpen] = useState(false)
  const [orderSearch, setOrderSearch] = useState("")
  const [orderResults, setOrderResults] = useState<Product[]>([])
  const [orderProductId, setOrderProductId] = useState<number | null>(null)
  const [orderProductName, setOrderProductName] = useState("")
  const [orderQty, setOrderQty] = useState("10")

  useEffect(() => {
    api<Stats>("/api/dashboard/stats")
      .then(setStats)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load.")
      )
  }, [])

  useEffect(() => {
    if (activeTab !== "forecast") return

    let cancelled = false
    api<ForecastPage>(`/api/forecast?limit=${PAGE_LIMIT}&offset=${forecastOffset}`)
      .then((data) => {
        if (!cancelled) setForecastPage(data)
      })
      .catch((err) => {
        console.error("Forecast error:", err)
        if (!cancelled) setForecastPage(null)
      })
    return () => {
      cancelled = true
    }
  }, [forecastOffset, activeTab])

  useEffect(() => {
    if (activeTab !== "recommendations") return

    let cancelled = false
    api<RecommendationPage>(
      `/api/recommendations?limit=${PAGE_LIMIT}&offset=${recommendationOffset}`
    )
      .then((data) => {
        if (!cancelled) setRecommendationPage(data)
      })
      .catch((err) => {
        console.error("Recommendations error:", err)
        if (!cancelled) setRecommendationPage(null)
      })
    return () => {
      cancelled = true
    }
  }, [recommendationOffset, activeTab])

  useEffect(() => {
    if (activeTab !== "movements") return

    let cancelled = false
    api<MovementPage>(`/api/movements?limit=${PAGE_LIMIT}&offset=${movementOffset}`)
      .then((data) => {
        if (!cancelled) setMovementPage(data)
      })
      .catch((err) => {
        console.error("Movements error:", err)
        if (!cancelled) setMovementPage(null)
      })
    return () => {
      cancelled = true
    }
  }, [movementOffset, activeTab])

  useEffect(() => {
    if (activeTab !== "dynamics") return

    let cancelled = false
    api<{ items: DailyMovement[] }>(`/api/movements/daily?days=${dynamicsDays}`)
      .then((data) => {
        if (!cancelled) setDaily(data.items)
      })
      .catch(() => {
        if (!cancelled) setDaily([])
      })
    return () => {
      cancelled = true
    }
  }, [activeTab, dynamicsDays])

  useEffect(() => {
    if (activeTab !== "dynamics") return

    let cancelled = false
    api<TopMovers>(`/api/movements/top?days=${dynamicsDays}`)
      .then((data) => {
        if (!cancelled) setTopMovers(data)
      })
      .catch((err) => {
        console.error("Top movers error:", err)
        if (!cancelled) setTopMovers(null)
      })
    return () => {
      cancelled = true
    }
  }, [activeTab, dynamicsDays])

  useEffect(() => {
    if (activeTab !== "lowstock") return

    let cancelled = false
    api<LowStockPage>(`/api/low-stock?limit=${PAGE_LIMIT}&offset=${lowStockOffset}`)
      .then((data) => {
        if (!cancelled) setLowStockPage(data)
      })
      .catch((err) => {
        console.error("Low stock error:", err)
        if (!cancelled) setLowStockPage(null)
      })
    return () => {
      cancelled = true
    }
  }, [lowStockOffset, activeTab])

  useEffect(() => {
    if (activeTab !== "orders") return

    let cancelled = false
    api<OrderPage>(`/api/orders?limit=${PAGE_LIMIT}&offset=${ordersOffset}`)
      .then((data) => {
        if (!cancelled) setOrdersPage(data)
      })
      .catch((err) => {
        console.error("Orders error:", err)
        if (!cancelled) setOrdersPage(null)
      })
    return () => {
      cancelled = true
    }
  }, [ordersOffset, ordersVersion, activeTab])

  async function createOrder(productId: number, qty: number, name: string) {
    try {
      await api("/api/orders", {
        method: "POST",
        body: { product_id: productId, qty },
      })
      toast.success(`Order created: ${qty} × ${name}`)
      setOrdersVersion((v) => v + 1)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create order.")
    }
  }

  async function orderAction(order: OrderRow, action: "receive" | "cancel") {
    setOrderBusy(true)
    try {
      await api(`/api/orders/${order.id}/${action}`, { method: "POST" })
      toast.success(
        action === "receive"
          ? `Received ${order.qty} × ${order.product_name} — stock updated`
          : `Order for ${order.product_name} cancelled`
      )
      setOrdersVersion((v) => v + 1)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Action failed.")
    } finally {
      setOrderBusy(false)
    }
  }

  async function searchOrderProducts(term: string) {
    if (!term.trim()) {
      setOrderResults([])
      return
    }
    try {
      const data = await api<{ items: Product[] }>(
        `/api/products?search=${encodeURIComponent(term)}`
      )
      setOrderResults(data.items.slice(0, 5))
    } catch {
      setOrderResults([])
    }
  }

  function resetOrderDraft() {
    setOrderSearch("")
    setOrderResults([])
    setOrderProductId(null)
    setOrderProductName("")
    setOrderQty("10")
  }

  const dynamicsTotalIn = daily?.reduce((sum, d) => sum + d.in_qty, 0) ?? 0
  const dynamicsTotalOut = daily?.reduce((sum, d) => sum + d.out_qty, 0) ?? 0
  const dynamicsNet = dynamicsTotalIn - dynamicsTotalOut
  const dynamicsAvgOut =
    daily && daily.length > 0 ? dynamicsTotalOut / daily.length : 0
  const dynamicsPeak =
    daily && daily.length > 0
      ? daily.reduce((a, b) => (b.out_qty > a.out_qty ? b : a))
      : null

  // Flow view series: a 7-day rolling average of consumption layered on
  // top of the daily in/out bars smooths out the day-to-day noise.
  const flowData = useMemo(() => {
    const source = daily ?? []
    return source.map((d, i) => {
      const window = source.slice(Math.max(0, i - 6), i + 1)
      const avg = window.reduce((s, x) => s + x.out_qty, 0) / window.length
      return { ...d, out_avg7: Math.round(avg * 10) / 10 }
    })
  }, [daily])

  // Daily-detail rows: net flow per day and the running cumulative
  // balance (oldest first, as the API returns it).
  const dailyRows = useMemo(() => {
    let cumulative = 0
    return (daily ?? []).map((d) => {
      cumulative += d.in_qty - d.out_qty
      return { ...d, net: d.in_qty - d.out_qty, cumulative }
    })
  }, [daily])

  if (error) {
    return (
      <Alert variant="destructive">
        <TriangleAlertIcon />
        <AlertTitle>Failed to load dashboard</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!stats) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-36" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <Card key={index}>
              <CardHeader>
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-7 w-16" />
              </CardHeader>
            </Card>
          ))}
        </div>
        <Skeleton className="h-8 w-full my-4" />
        <Skeleton className="h-8 w-full my-4" />
        <Skeleton className="h-8 w-full my-4" />
      </div>
    )
  }

  const cards: {
    title: string
    value: string
    exact?: string
    icon: typeof PackageIcon
    danger: boolean
  }[] = [
    {
      title: "Products",
      value: stats.products.toLocaleString("en-US"),
      icon: PackageIcon,
      danger: false,
    },
    {
      title: "Brands",
      value: stats.brands.toLocaleString("en-US"),
      icon: TagsIcon,
      danger: false,
    },
    {
      title: "Units in stock",
      value: stats.units_in_stock.toLocaleString("en-US"),
      icon: BoxesIcon,
      danger: false,
    },
    {
      title: "Inventory value",
      value: compactMoney(stats.inventory_value),
      exact: money(stats.inventory_value),
      icon: BanknoteIcon,
      danger: false,
    },
    {
      title: `Low stock (< ${stats.low_stock_threshold})`,
      value: stats.low_stock.toLocaleString("en-US"),
      icon: TriangleAlertIcon,
      danger: stats.low_stock > 0,
    },
  ]

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of your inventory at a glance.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {cards.map((card) => (
          <Card key={card.title}>
            <CardHeader>
              <CardDescription>{card.title}</CardDescription>
              <CardTitle
                title={card.exact}
                className={
                  card.danger
                    ? "min-w-0 truncate text-2xl tabular-nums text-destructive"
                    : "min-w-0 truncate text-2xl tabular-nums"
                }
              >
                {card.value}
              </CardTitle>
              <CardAction>
                <span
                  className={
                    card.danger
                      ? "flex size-8 items-center justify-center rounded-md bg-destructive/10"
                      : "flex size-8 items-center justify-center rounded-md bg-muted"
                  }
                >
                  <card.icon
                    className={
                      card.danger
                        ? "size-4 text-destructive"
                        : "size-4 text-muted-foreground"
                    }
                  />
                </span>
              </CardAction>
            </CardHeader>
          </Card>
        ))}
      </div>

      {/* Tab navigation */}
      <div className="mt-6 border-b">
        <nav className="grid grid-cols-2 gap-1 px-4 sm:grid-cols-3 lg:grid-cols-6" role="tablist" aria-label="Dashboard sections">
          <button
            role="tab"
            aria-selected={activeTab === "forecast"}
            onClick={() => setActiveTab("forecast")}
            className={`flex items-center justify-center gap-2 px-2 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === "forecast"
                ? "border-primary text-primary"
                : "text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            <LineChartIcon className="size-4" />
            Forecast
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "recommendations"}
            onClick={() => setActiveTab("recommendations")}
            className={`flex items-center justify-center gap-2 px-2 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === "recommendations"
                ? "border-primary text-primary"
                : "text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            <ClipboardListIcon className="size-4" />
            Recommendations
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "dynamics"}
            onClick={() => setActiveTab("dynamics")}
            className={`flex items-center justify-center gap-2 px-2 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === "dynamics"
                ? "border-primary text-primary"
                : "text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            <BarChart2 className="size-4" />
            Stock dynamics
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "movements"}
            onClick={() => setActiveTab("movements")}
            className={`flex items-center justify-center gap-2 px-2 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === "movements"
                ? "border-primary text-primary"
                : "text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            <HistoryIcon className="size-4" />
            Recent movements
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "lowstock"}
            onClick={() => setActiveTab("lowstock")}
            className={`flex items-center justify-center gap-2 px-2 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === "lowstock"
                ? "border-primary text-primary"
                : "text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            <TriangleAlertIcon className="size-4" />
            Low stock
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "orders"}
            onClick={() => setActiveTab("orders")}
            className={`flex items-center justify-center gap-2 px-2 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === "orders"
                ? "border-primary text-primary"
                : "text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            <TruckIcon className="size-4" />
            Orders
          </button>
        </nav>
      </div>

      {/* Tab panels */}
      {activeTab === "forecast" && forecastPage !== null && (
        <div className="mt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableCell className="text-left product">Product</TableCell>
                <TableCell className="text-right qty">Stock</TableCell>
                <TableCell className="text-center days">Days left</TableCell>
                <TableCell className="text-right restock">Rec. restock</TableCell>
                <TableCell className="text-right rp">Reorder point</TableCell>
                <TableCell className="text-center lt">Lead time</TableCell>
                <TableCell className="text-center ai">AI</TableCell>
              </TableRow>
            </TableHeader>
            <TableBody>
                {forecastPage.forecasts.map((f) => (
                  <TableRow key={f.product_id}>
                    <TableCell className="text-left product">{f.name}</TableCell>
                    <TableCell className="text-right qty">{f.current_qty.toLocaleString("en-US")}</TableCell>
                    <TableCell className="text-center days">
                      {formatDays(f.days_until_stockout)}
                    </TableCell>
                    <TableCell className="text-right restock">
                      {f.recommended_restock_qty.toLocaleString("en-US")}
                    </TableCell>
                    <TableCell className="text-right rp">{f.reorder_point}</TableCell>
                    <TableCell className="text-center lt">{f.lead_time_days} d</TableCell>
                    <TableCell className="text-center ai">
                      {f.ai_refined ? <Badge variant="secondary">AI</Badge> : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {forecastPage.forecasts.length > 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Regression on recent stock movements; "AI" marks rows refined by the LLM
              </p>
            )}
            {forecastPage.total > 0 && (
              <Pager
                offset={forecastOffset}
                total={forecastPage.total}
                onOffsetChange={setForecastOffset}
              />
            )}
          </div>
        )}

      {activeTab === "forecast" && forecastPage === null && (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Forecast unavailable — {"the forecast service could not be reached. Retry in a moment."}
          </p>
        </div>
      )}

      {activeTab === "recommendations" && recommendationPage !== null && (
        <div className="mt-6">
          {recommendationPage.recommendations.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableCell className="text-left product">Product</TableCell>
                    <TableCell className="text-right qty">Current</TableCell>
                    <TableCell className="text-right restock">Rec. qty</TableCell>
                    <TableCell className="text-center days">Days empty</TableCell>
                    <TableCell className="w-20" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recommendationPage.recommendations.map((r) => (
                    <TableRow key={r.product_id}>
                      <TableCell className="text-left product">{r.name}</TableCell>
                      <TableCell className="text-right qty">{r.current_qty.toLocaleString("en-US")}</TableCell>
                      <TableCell className="text-right restock">{r.recommended_qty.toLocaleString("en-US")}</TableCell>
                      <TableCell className="text-center days">
                        {formatDays(r.estimated_days_until_empty)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          title={`Create a purchase order for ${r.recommended_qty} × ${r.name}`}
                          onClick={() =>
                            void createOrder(
                              r.product_id,
                              Math.max(1, r.recommended_qty),
                              r.name
                            )
                          }
                        >
                          <TruckIcon />
                          Order
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {recommendationPage.total > 0 && (
                <Pager
                  offset={recommendationOffset}
                  total={recommendationPage.total}
                  onOffsetChange={setRecommendationOffset}
                />
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No urgent restock needed</p>
          )}
        </div>
      )}

      {activeTab === "recommendations" && recommendationPage === null && (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Recommendations unavailable
          </p>
        </div>
      )}

      {activeTab === "dynamics" && daily !== null && daily.length > 0 && (
        <div className="mt-6">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>
                Units in:{" "}
                <strong className="text-foreground tabular-nums">
                  {dynamicsTotalIn.toLocaleString("en-US")}
                </strong>
              </span>
              <span>
                Units out:{" "}
                <strong className="text-foreground tabular-nums">
                  {dynamicsTotalOut.toLocaleString("en-US")}
                </strong>
              </span>
              <span>
                Net:{" "}
                <strong
                  className={
                    dynamicsNet >= 0
                      ? "text-foreground tabular-nums"
                      : "text-destructive tabular-nums"
                  }
                >
                  {formatQty(dynamicsNet)}
                </strong>
              </span>
              <span>
                Avg daily out:{" "}
                <strong className="text-foreground tabular-nums">
                  {dynamicsAvgOut.toFixed(1)}
                </strong>
              </span>
              {dynamicsPeak && (
                <span>
                  Peak day:{" "}
                  <strong className="text-foreground tabular-nums">
                    {formatDayTick(dynamicsPeak.date)} ({dynamicsPeak.out_qty})
                  </strong>
                </span>
              )}
              <span>
                Active days:{" "}
                <strong className="text-foreground tabular-nums">
                  {daily.length} / {dynamicsDays}
                </strong>
              </span>
            </div>
            <div className="flex items-center gap-1">
              {[30, 90].map((d) => (
                <Button
                  key={d}
                  variant={dynamicsDays === d ? "default" : "outline"}
                  size="sm"
                  onClick={() => setDynamicsDays(d)}
                >
                  {d} days
                </Button>
              ))}
            </div>
          </div>

          {/* Dynamics sub-views */}
          <div className="flex items-center gap-1 mb-3 border-b pb-2">
            <Button
              variant={dynamicsView === "flow" ? "default" : "ghost"}
              size="sm"
              onClick={() => setDynamicsView("flow")}
            >
              Flow
            </Button>
            <Button
              variant={dynamicsView === "top" ? "default" : "ghost"}
              size="sm"
              onClick={() => setDynamicsView("top")}
            >
              Top movers
            </Button>
            <Button
              variant={dynamicsView === "daily" ? "default" : "ghost"}
              size="sm"
              onClick={() => setDynamicsView("daily")}
            >
              Daily detail
            </Button>
          </div>

          {dynamicsView === "flow" && (
            <div className="h-[600px] w-full rounded border bg-card p-2">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={flowData} margin={{ top: 12, right: 12, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    fontSize={11}
                    tickLine={false}
                    interval="preserveStartEnd"
                    tickFormatter={formatDayTick}
                  />
                  <YAxis fontSize={11} width={40} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="in_qty" name="Units in" fill="#22c55e" radius={[3, 3, 0, 0]} maxBarSize={28} />
                  <Bar dataKey="out_qty" name="Units out" fill="#ef4444" radius={[3, 3, 0, 0]} maxBarSize={28} />
                  <Line
                    type="monotone"
                    dataKey="out_avg7"
                    name="7-day avg out"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {dynamicsView === "top" && (
            topMovers !== null ? (
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Top restocks</p>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableCell className="text-left product">Product</TableCell>
                        <TableCell className="text-right qty">Units in</TableCell>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {topMovers.top_in.map((item) => (
                        <TableRow key={item.product_id}>
                          <TableCell className="text-left product">{item.name}</TableCell>
                          <TableCell className="text-right qty">
                            {item.in_qty.toLocaleString("en-US")}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Top consumption</p>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableCell className="text-left product">Product</TableCell>
                        <TableCell className="text-right qty">Units out</TableCell>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {topMovers.top_out.map((item) => (
                        <TableRow key={item.product_id}>
                          <TableCell className="text-left product">{item.name}</TableCell>
                          <TableCell className="text-right qty">
                            {item.out_qty.toLocaleString("en-US")}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Top movers unavailable</p>
            )
          )}

          {dynamicsView === "daily" && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableCell className="text-left">Date</TableCell>
                  <TableCell className="text-right">In</TableCell>
                  <TableCell className="text-right">Out</TableCell>
                  <TableCell className="text-right">Net</TableCell>
                  <TableCell className="text-right">Cumulative net</TableCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {dailyRows.map((row) => (
                  <TableRow key={row.date}>
                    <TableCell className="text-left">{formatDayTick(row.date)}</TableCell>
                    <TableCell className="text-right tabular-nums">{row.in_qty}</TableCell>
                    <TableCell className="text-right tabular-nums">{row.out_qty}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span className={row.net < 0 ? "text-destructive" : ""}>
                        {formatQty(row.net)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <span className={row.cumulative < 0 ? "text-destructive" : ""}>
                        {formatQty(row.cumulative)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      )}

      {activeTab === "dynamics" && daily !== null && daily.length === 0 && (
        <p className="mt-6 text-sm text-muted-foreground">
          No stock movements recorded in the last {dynamicsDays} days
        </p>
      )}

      {activeTab === "movements" && movementPage !== null && (
          <div className="mt-6">
            <div className="flex justify-end mb-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void downloadMovementsCsv()}
              >
                <DownloadIcon />
                Export CSV
              </Button>
            </div>
            {movementPage.items.length > 0 ? (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableCell className="text-left product">Product</TableCell>
                      <TableCell className="text-center in_out">Flow</TableCell>
                      <TableCell className="text-right qty">Qty</TableCell>
                      <TableCell className="text-left reason">Reason</TableCell>
                      <TableCell className="text-right timestamp">When</TableCell>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {movementPage.items.map((m) => (
                      <TableRow key={m.movement_id}>
                        <TableCell className="text-left product">{m.product_name}</TableCell>
                        <TableCell className="text-center in_out">
                          {m.in_out === "in" ? "In" : "Out"}
                        </TableCell>
                        <TableCell className="text-right qty">{formatQty(m.qty_delta)}</TableCell>
                        <TableCell className="text-left reason">{m.reason || "—"}</TableCell>
                        <TableCell className="text-right timestamp">
                          {formatTimestamp(m.timestamp)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {movementPage.total > 0 && (
                  <Pager
                    offset={movementOffset}
                    total={movementPage.total}
                    onOffsetChange={setMovementOffset}
                  />
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No stock movements recorded yet</p>
            )}
          </div>
        )}

        {activeTab === "movements" && movementPage === null && (
          <div className="mt-6 p-4 bg-muted rounded">
            <p className="text-sm">
              <span className="animate-pulse h-4 w-6 rounded mr-2" />
              Recent movements unavailable
            </p>
          </div>
        )}

      {activeTab === "lowstock" && lowStockPage !== null && (
        <div className="mt-6 p-3 bg-muted/50 rounded border">
          <p className="text-xs text-muted-foreground mb-2">
            Below threshold ({stats.low_stock_threshold}) — the most depleted first
          </p>
          {lowStockPage.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableCell className="text-left product">Product</TableCell>
                    <TableCell className="text-right qty">Remaining</TableCell>
                    <TableCell className="text-right restock">Reorder point</TableCell>
                    <TableCell className="w-20" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {lowStockPage.items.map((item) => (
                    <TableRow key={item.product_id}>
                      <TableCell className="text-left product">{item.name}</TableCell>
                      <TableCell className="text-right qty">{item.remaining_qty.toLocaleString("en-US")}</TableCell>
                      <TableCell className="text-right restock">{item.reorder_point.toLocaleString("en-US")}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          title={`Order ${Math.max(1, item.reorder_point - item.remaining_qty)} × ${item.name} (up to the reorder point)`}
                          onClick={() =>
                            void createOrder(
                              item.product_id,
                              Math.max(1, item.reorder_point - item.remaining_qty),
                              item.name
                            )
                          }
                        >
                          <TruckIcon />
                          Order
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {lowStockPage.total > 0 && (
                <Pager
                  offset={lowStockOffset}
                  total={lowStockPage.total}
                  onOffsetChange={setLowStockOffset}
                />
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">All products sufficiently stocked</p>
          )}
        </div>
      )}

      {activeTab === "lowstock" && lowStockPage === null && (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Low stock list unavailable
          </p>
        </div>
      )}

      {activeTab === "orders" && ordersPage !== null && (
        <div className="mt-6">
          <div className="flex justify-end mb-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                resetOrderDraft()
                setOrderOpen(true)
              }}
            >
              <PlusIcon />
              New order
            </Button>
          </div>
          {ordersPage.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableCell className="text-left product">Product</TableCell>
                    <TableCell className="text-right qty">Qty</TableCell>
                    <TableCell className="text-center">Status</TableCell>
                    <TableCell className="text-right">Created</TableCell>
                    <TableCell className="text-right">Expected</TableCell>
                    <TableCell className="w-24" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {ordersPage.items.map((o) => {
                    const overdue =
                      o.status === "ordered" &&
                      new Date(o.expected_at).getTime() < Date.now()
                    return (
                      <TableRow key={o.id}>
                        <TableCell className="text-left product">{o.product_name}</TableCell>
                        <TableCell className="text-right qty tabular-nums">{o.qty}</TableCell>
                        <TableCell className="text-center">
                          {o.status === "received" && (
                            <Badge variant="secondary">received</Badge>
                          )}
                          {o.status === "cancelled" && (
                            <Badge variant="outline">cancelled</Badge>
                          )}
                          {o.status === "ordered" && (
                            <Badge variant={overdue ? "destructive" : "default"}>
                              {overdue ? "overdue" : "ordered"}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right timestamp">
                          {formatTimestamp(o.created_at)}
                        </TableCell>
                        <TableCell className="text-right timestamp">
                          {o.status === "received" && o.received_at
                            ? formatTimestamp(o.received_at)
                            : formatTimestamp(o.expected_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          {o.status === "ordered" && (
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Receive ${o.product_name}`}
                                title="Mark received — adds stock and records a movement"
                                disabled={orderBusy}
                                onClick={() => void orderAction(o, "receive")}
                              >
                                <PackageIcon />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                aria-label={`Cancel ${o.product_name}`}
                                title="Cancel order"
                                disabled={orderBusy}
                                onClick={() => void orderAction(o, "cancel")}
                              >
                                <TriangleAlertIcon />
                              </Button>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              {ordersPage.total > 0 && (
                <Pager
                  offset={ordersOffset}
                  total={ordersPage.total}
                  onOffsetChange={setOrdersOffset}
                />
              )}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No purchase orders yet — create one from the Recommendations or
              Low stock tab, or with the New order button.
            </p>
          )}
        </div>
      )}

      {activeTab === "orders" && ordersPage === null && (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Orders unavailable
          </p>
        </div>
      )}

      <Dialog open={orderOpen} onOpenChange={(open) => { setOrderOpen(open); if (!open) resetOrderDraft() }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New purchase order</DialogTitle>
            <DialogDescription>
              Pick a product and the quantity to order from the supplier.
              The expected arrival is derived from the product's lead time.
            </DialogDescription>
          </DialogHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (orderProductId === null) return
              const qty = Number(orderQty)
              if (!Number.isInteger(qty) || qty < 1) return
              void createOrder(orderProductId, qty, orderProductName).then(() => {
                setOrderOpen(false)
                resetOrderDraft()
              })
            }}
            className="grid gap-4"
          >
            <div className="grid gap-2">
              <Label htmlFor="order-search">Product</Label>
              <Input
                id="order-search"
                value={orderSearch}
                placeholder="Search by product or brand name…"
                onChange={(e) => {
                  setOrderSearch(e.target.value)
                  void searchOrderProducts(e.target.value)
                }}
              />
              {orderResults.length > 0 && (
                <div className="max-h-40 overflow-auto rounded border divide-y">
                  {orderResults.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => {
                        setOrderProductId(p.id)
                        setOrderProductName(p.name)
                        setOrderResults([])
                        setOrderSearch(p.name)
                      }}
                      className={`block w-full px-3 py-1.5 text-left text-sm transition-colors ${
                        orderProductId === p.id
                          ? "bg-accent text-accent-foreground"
                          : "hover:bg-accent/50"
                      }`}
                    >
                      {p.name} <span className="text-muted-foreground">({p.brand})</span>
                    </button>
                  ))}
                </div>
              )}
              {orderProductId !== null && (
                <p className="text-xs text-muted-foreground">
                  Selected: <strong className="text-foreground">{orderProductName}</strong>
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="order-qty">Quantity</Label>
              <Input
                id="order-qty"
                type="number"
                min="1"
                step="1"
                value={orderQty}
                onChange={(e) => setOrderQty(e.target.value)}
                required
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setOrderOpen(false)
                  resetOrderDraft()
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={orderProductId === null}>
                Create order
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}