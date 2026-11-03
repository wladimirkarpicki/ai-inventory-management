import { useCallback, useEffect, useState } from "react"
import { DownloadIcon, HeartPulseIcon, TriangleAlertIcon } from "lucide-react"
import { toast } from "sonner"

import { api, getToken, type InventoryHealth } from "@/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { STOCK_STATUSES, StockStatusBadge } from "@/lib/inventoryHealth"

const FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "All" },
  ...STOCK_STATUSES.map((status) => ({ value: status, label: status })),
]

async function downloadHealthCsv() {
  const token = getToken()

  try {
    const response = await fetch("/api/export/inventory-health.csv", {
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
    link.download = "inventory-health.csv"
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    toast.error("Export failed.")
  }
}

export function InventoryHealthPage() {
  const [report, setReport] = useState<InventoryHealth | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState("")
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    const params = new URLSearchParams()
    if (status) params.set("status", status)
    params.set("page", String(page))

    try {
      const data = await api<InventoryHealth>(`/api/inventory-health?${params}`)
      setReport(data)
      setError(null)
    } catch (err) {
      setReport(null)
      setError(err instanceof Error ? err.message : "Failed to load the report.")
    }
  }, [status, page])

  useEffect(() => {
    void load()
  }, [load])

  const summary = report?.summary
  const rows = report?.items ?? []

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory health</h1>
          <p className="text-sm text-muted-foreground">
            Every product compared against its own minimum quantity, most urgent
            first.
          </p>
        </div>
        <Button variant="outline" onClick={() => void downloadHealthCsv()}>
          <DownloadIcon />
          Export CSV
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <TriangleAlertIcon />
          <AlertTitle>Failed to load the report</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {summary && (
        <div
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          aria-live="polite"
        >
          {[
            { label: "Products tracked", value: summary.total },
            { label: "Out of stock", value: summary["OUT OF STOCK"] },
            { label: "Low stock", value: summary["LOW STOCK"] },
            { label: "In stock", value: summary["IN STOCK"] },
          ].map((tile) => (
            <Card key={tile.label}>
              <CardContent className="grid gap-1 pt-6">
                <span className="text-sm text-muted-foreground">{tile.label}</span>
                <span className="text-3xl font-semibold tabular-nums">
                  {tile.value}
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1">
        {FILTERS.map((filter) => (
          <Button
            key={filter.value || "all"}
            aria-pressed={status === filter.value}
            variant={status === filter.value ? "secondary" : "ghost"}
            size="sm"
            onClick={() => {
              setStatus(filter.value)
              setPage(1)
            }}
            title={
              filter.value
                ? `Show only products with status ${filter.value}`
                : "Show every product"
            }
          >
            {filter.label}
          </Button>
        ))}
      </div>

      {!report ? (
        <Skeleton className="h-64 w-full" />
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="grid place-items-center gap-2 py-16 text-center">
            <HeartPulseIcon className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              No products match this filter.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Brand</TableHead>
                  <TableHead className="text-right">Current quantity</TableHead>
                  <TableHead className="text-right">Minimum quantity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Recommended to order</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.product_id}>
                    <TableCell className="tabular-nums">{row.product_id}</TableCell>
                    <TableCell className="font-medium">{row.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{row.brand}</Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.current_quantity}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {row.min_quantity}
                    </TableCell>
                    <TableCell>
                      <StockStatusBadge status={row.stock_status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-medium">
                      {row.recommended_to_order}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
          <div className="flex items-center justify-between border-t px-6 py-4">
            <span className="text-sm text-muted-foreground tabular-nums">
              Page {report.page} of {report.pages} &middot; {report.total.toLocaleString("en-US")} products
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={report.page <= 1}
                onClick={() => setPage(report.page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={report.page >= report.pages}
                onClick={() => setPage(report.page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
