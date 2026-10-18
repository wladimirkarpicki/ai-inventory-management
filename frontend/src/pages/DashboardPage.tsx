import { useEffect, useState } from "react"
import {
  BanknoteIcon,
  BoxesIcon,
  PackageIcon,
  TagsIcon,
  TriangleAlertIcon,
} from "lucide-react"

import { api, type Stats } from "@/api"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

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

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<Stats>("/api/dashboard/stats")
      .then(setStats)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load.")
      )
  }, [])

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
    </div>
  )
}
