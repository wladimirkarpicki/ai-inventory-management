import type { Product, StockStatus } from "@/api"
import { Badge } from "@/components/ui/badge"

export const MIN_QUANTITY_DEFAULT = 5

export const STOCK_STATUSES: StockStatus[] = [
  "OUT OF STOCK",
  "LOW STOCK",
  "IN STOCK",
]

/**
 * Classify stock against the product's own minimum level. Mirrors the
 * server rule in main.py: 0 is OUT OF STOCK, anything between 0 and the
 * minimum is LOW STOCK, at or above the minimum is IN STOCK.
 *
 * `quantity` is nullable in the database and the API returns it raw, so an
 * unknown on-hand is read as 0 units, exactly as the backend report does.
 */
export function statusOf(product: Product): StockStatus {
  const quantity = product.quantity ?? 0
  // min_quantity is always sent by the API, but keep the documented default
  // so a partial object (or an old cached response) still classifies
  // correctly instead of comparing against undefined.
  const min = product.min_quantity ?? MIN_QUANTITY_DEFAULT

  if (quantity <= 0) return "OUT OF STOCK"
  if (quantity < min) return "LOW STOCK"
  return "IN STOCK"
}

/**
 * Units needed to reach the minimum level: max(0, min_quantity - quantity).
 * Never negative, and 0 for anything already at or above the minimum.
 */
export function recommendedToOrder(product: Product): number {
  const quantity = product.quantity ?? 0
  const min = product.min_quantity ?? MIN_QUANTITY_DEFAULT

  return Math.max(0, min - quantity)
}

/**
 * Status pill. Colour carries the severity (destructive for empty,
 * secondary for low, outline for healthy) and the words carry the same
 * information for anyone who cannot see the colour.
 */
export function StockStatusBadge({ status }: { status: StockStatus }) {
  if (status === "OUT OF STOCK") {
    return (
      <Badge variant="destructive" className="whitespace-nowrap">
        Out of stock
      </Badge>
    )
  }

  if (status === "LOW STOCK") {
    return (
      <Badge variant="secondary" className="whitespace-nowrap">
        Low stock
      </Badge>
    )
  }

  return (
    <Badge variant="outline" className="whitespace-nowrap">
      In stock
    </Badge>
  )
}
