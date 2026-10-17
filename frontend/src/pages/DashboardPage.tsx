import { useEffect, useState } from "react"

import { api, type Stats } from "@/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

function money(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  })
}

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Stats>("/api/dashboard/stats")
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed."))
  }, [])

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }

  if (!stats) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }

  const cards = [
    { title: "Products", value: String(stats.products) },
    { title: "Brands", value: String(stats.brands) },
    { title: "Units in stock", value: String(stats.units_in_stock) },
    { title: "Inventory value", value: money(stats.inventory_value) },
    {
      title: `Low stock (< ${stats.low_stock_threshold})`,
      value: String(stats.low_stock),
    },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {cards.map((card) => (
          <Card key={card.title}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-semibold">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
