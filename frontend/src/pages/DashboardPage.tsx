import { useEffect, useState } from "react"
import {
  BanknoteIcon,
  BoxesIcon,
  DownloadIcon,
  PackageIcon,
  TagsIcon,
  TriangleAlertIcon,
} from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
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
  type MovementPage,
  type RecommendationPage,
  type Stats,
} from "@/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableHeader, TableRow, TableCell, TableBody } from "@/components/ui/table"

const PAGE_LIMIT = 10

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

// Stat cards are narrow; a full "$10,388,461.13" is one unbreakable word
// whose min-content width blows out the card grid and shoves the icon
// badges around. Large values collapse to K/M; the exact amount stays
// available as the hover tooltip.
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

// Server-side pagination controls: Prev/Next plus an "X–Y of Z" range
// derived from the endpoint's total.
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

  const [forecastPage, setForecastPage] = useState<ForecastPage | null>(null)
  const [forecastOffset, setForecastOffset] = useState(0)

  const [recommendationPage, setRecommendationPage] = useState<RecommendationPage | null>(null)
  const [recommendationOffset, setRecommendationOffset] = useState(0)

  const [movementPage, setMovementPage] = useState<MovementPage | null>(null)
  const [movementOffset, setMovementOffset] = useState(0)

  const [daily, setDaily] = useState<DailyMovement[] | null>(null)

  useEffect(() => {
    api<Stats>("/api/dashboard/stats")
      .then(setStats)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load.")
      )
  }, [])

  useEffect(() => {
    let cancelled = false
    api<{ items: DailyMovement[] }>("/api/movements/daily")
      .then((data) => {
        if (!cancelled) setDaily(data.items)
      })
      .catch(() => {
        if (!cancelled) setDaily([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
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
  }, [forecastOffset])

  useEffect(() => {
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
  }, [recommendationOffset])

  useEffect(() => {
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
  }, [movementOffset])

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

      {/* Low stock alerts below the cards grid (top-10 from stats) */}
      {stats.low_stock_alerts.length > 0 ? (
        <div className="mt-4 p-3 bg-muted/50 rounded border">
          <h3 className="font-medium text-sm mb-2">Low stock alerts</h3>
          <p className="text-xs text-muted-foreground">
            Below threshold ({stats.low_stock_threshold})
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableCell className="text-left product">Product</TableCell>
                <TableCell className="text-right qty">Remaining</TableCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stats.low_stock_alerts.map((alert) => (
                <TableRow key={alert.product_id}>
                  <TableCell className="text-left product">{alert.name}</TableCell>
                  <TableCell className="text-right qty">{alert.remaining_qty.toLocaleString("en-US")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {stats.low_stock > stats.low_stock_alerts.length && (
            <p className="mt-2 text-xs text-muted-foreground">
              …and {(stats.low_stock - stats.low_stock_alerts.length).toLocaleString("en-US")} more
              below threshold
            </p>
          )}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground" style={{ margin: "0 auto" }}>
          All products sufficiently stocked
        </p>
      )}

      {/* Forecast section */}
      {forecastPage !== null ? (
        <div className="mt-6">
          <h3 className="font-medium text-sm mb-3">Forecast</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableCell className="text-left product">Product</TableCell>
                <TableCell className="text-center days">Days left</TableCell>
                <TableCell className="text-right restock">Rec. restock</TableCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {forecastPage.forecasts.map((f) => (
                <TableRow key={f.product_id}>
                  <TableCell className="text-left product">{f.name}</TableCell>
                  <TableCell className="text-center days">
                    {formatDays(f.days_until_stockout)}
                  </TableCell>
                  <TableCell className="text-right restock">
                    {f.recommended_restock_qty.toLocaleString("en-US")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {forecastPage.forecasts.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              Based on recent stock movement trends (linear regression)
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
      ) : (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Forecast unavailable — {"OpenRouter API down, showing regression-based days_until_stockout only."}
          </p>
        </div>
      )}

      {/* Recommendations section */}
      {recommendationPage !== null ? (
        <div className="mt-6">
          <h3 className="font-medium text-sm mb-3">Recommendations</h3>
          {recommendationPage.recommendations.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableCell className="text-left product">Product</TableCell>
                    <TableCell className="text-right qty">Current</TableCell>
                    <TableCell className="text-right restock">Rec. qty</TableCell>
                    <TableCell className="text-center days">Days empty</TableCell>
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
      ) : (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Recommendations unavailable
          </p>
        </div>
      )}

      {/* Stock dynamics chart (P14) */}
      {daily !== null && daily.length > 0 && (
        <div className="mt-6">
          <h3 className="font-medium text-sm mb-3">Stock dynamics (30 days)</h3>
          <div className="h-64 w-full rounded border bg-card p-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" fontSize={11} tickLine={false} />
                <YAxis fontSize={11} width={32} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="in_qty" name="Units in" fill="#22c55e" radius={[3, 3, 0, 0]} />
                <Bar dataKey="out_qty" name="Units out" fill="#ef4444" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Recent movements section */}
      {movementPage !== null ? (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-sm">Recent movements</h3>
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
      ) : (
        <div className="mt-6 p-4 bg-muted rounded">
          <p className="text-sm">
            <span className="animate-pulse h-4 w-6 rounded mr-2" />
            Recent movements unavailable
          </p>
        </div>
      )}
    </div>
  )
}
