import { describe, expect, it } from "vitest"

import type { Product } from "@/api"
import { MIN_QUANTITY_DEFAULT, recommendedToOrder, statusOf } from "./inventoryHealth"

function product(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    brand_id: 1,
    brand: "Acme",
    name: "Widget",
    price: 10,
    quantity: 10,
    reorder_point: 10,
    lead_time_days: 7,
    min_quantity: 5,
    ...overrides,
  }
}

describe("statusOf", () => {
  // The three boundaries of the classification rule.
  it("is OUT OF STOCK at exactly zero", () => {
    expect(statusOf(product({ quantity: 0, min_quantity: 5 }))).toBe("OUT OF STOCK")
  })

  it("is LOW STOCK for anything between zero and the minimum", () => {
    expect(statusOf(product({ quantity: 1, min_quantity: 5 }))).toBe("LOW STOCK")
    expect(statusOf(product({ quantity: 4, min_quantity: 5 }))).toBe("LOW STOCK")
  })

  it("is IN STOCK at exactly the minimum", () => {
    expect(statusOf(product({ quantity: 5, min_quantity: 5 }))).toBe("IN STOCK")
    expect(statusOf(product({ quantity: 9, min_quantity: 5 }))).toBe("IN STOCK")
  })

  it("treats a zero minimum as always in stock for positive quantities", () => {
    expect(statusOf(product({ quantity: 1, min_quantity: 0 }))).toBe("IN STOCK")
  })

  it("keeps zero quantity OUT OF STOCK even with a zero minimum", () => {
    expect(statusOf(product({ quantity: 0, min_quantity: 0 }))).toBe("OUT OF STOCK")
  })

  it("falls back to the documented default when the server omitted the field", () => {
    expect(statusOf(product({ quantity: 2, min_quantity: undefined }))).toBe("LOW STOCK")
    expect(statusOf(product({ quantity: 6, min_quantity: undefined }))).toBe("IN STOCK")
  })

  it("reads a null quantity as zero units on hand", () => {
    // quantity is nullable in the database and the API returns it raw.
    expect(statusOf(product({ quantity: null, min_quantity: 5 }))).toBe("OUT OF STOCK")
  })

  it("reads a null quantity as zero units even with a zero minimum", () => {
    expect(statusOf(product({ quantity: null, min_quantity: 0 }))).toBe("OUT OF STOCK")
  })
})

describe("recommendedToOrder", () => {
  it("returns the gap below the minimum", () => {
    expect(recommendedToOrder(product({ quantity: 2, min_quantity: 10 }))).toBe(8)
  })

  it("is zero at or above the minimum", () => {
    expect(recommendedToOrder(product({ quantity: 10, min_quantity: 10 }))).toBe(0)
    expect(recommendedToOrder(product({ quantity: 40, min_quantity: 10 }))).toBe(0)
  })

  it("is the whole minimum when empty", () => {
    expect(recommendedToOrder(product({ quantity: 0, min_quantity: 7 }))).toBe(7)
  })

  it("never goes negative", () => {
    expect(recommendedToOrder(product({ quantity: 99, min_quantity: 1 }))).toBe(0)
  })

  it("orders the whole minimum when the quantity is null", () => {
    expect(recommendedToOrder(product({ quantity: null, min_quantity: 7 }))).toBe(7)
  })

  it("falls back to the documented default when the minimum is missing", () => {
    // Guards the NaN this once returned when the fallback was dropped.
    expect(recommendedToOrder(product({ quantity: 2, min_quantity: undefined }))).toBe(3)
    expect(recommendedToOrder(product({ quantity: 9, min_quantity: undefined }))).toBe(0)
  })
})

describe("MIN_QUANTITY_DEFAULT", () => {
  it("matches the server default", () => {
    expect(MIN_QUANTITY_DEFAULT).toBe(5)
  })
})
