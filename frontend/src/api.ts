const TOKEN_KEY = "ims_token"

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {}
): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()

  if (token) headers["Authorization"] = `Bearer ${token}`
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json"
  }

  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers,
    body:
      options.body instanceof FormData
        ? options.body
        : options.body !== undefined
          ? JSON.stringify(options.body)
          : undefined,
  })

  const data = (await response.json().catch(() => null)) as
    | { detail?: string }
    | null

  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.detail ?? `Request failed (${response.status}).`
    )
  }

  return data as T
}

// ------------------------------------------------------------------ types

export interface User {
  id: number
  username: string
  role: "user" | "admin"
}

export interface UserRow extends User {
  is_you: boolean
}

export interface Brand {
  id: number
  name: string
  product_count?: number
}

export interface Product {
  id: number
  brand_id: number
  brand: string
  name: string
  price: number
  quantity: number
  reorder_point: number
  lead_time_days: number
}

export interface ProductList {
  items: Product[]
  page: number
  pages: number
  total: number
}

export interface Stats {
  products: number
  brands: number
  units_in_stock: number
  inventory_value: number
  low_stock: number
  low_stock_threshold: number
  low_stock_alerts: Array<{product_id: number; name: string; remaining_qty: number}>
}

export interface AuthStatus {
  setup_required: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

// ------------------------------------------------------------------ analytics (P7)

export interface ForecastRow {
  product_id: number
  name: string
  current_qty: number
  days_until_stockout: number | null
  recommended_restock_qty: number
  reorder_point: number
  lead_time_days: number
  ai_refined: boolean
}

export interface ForecastPage {
  forecasts: ForecastRow[]
  total: number
}

export interface RecommendationRow {
  product_id: number
  name: string
  current_qty: number
  recommended_qty: number
  estimated_days_until_empty: number | null
}

export interface RecommendationPage {
  recommendations: RecommendationRow[]
  total: number
}

export interface Movement {
  movement_id: number
  product_id: number
  product_name: string
  in_out: "in" | "out"
  qty_delta: number
  reason: string
  timestamp: string
}

export interface MovementPage {
  items: Movement[]
  total: number
}

// ------------------------------------------------------------------ daily movements (P14)

export interface DailyMovement {
  date: string
  in_qty: number
  out_qty: number
}

export interface DailyMovementList {
  items: DailyMovement[]
  days: number
}

// ------------------------------------------------------------------ csv import (P9)

export interface ImportRowIssue {
  row: number
  reason: string
}

export interface ImportResult {
  imported: number
  skipped: ImportRowIssue[]
  errors: ImportRowIssue[]
}

// ------------------------------------------------------------------ low stock (P19)

export interface LowStockRow {
  product_id: number
  name: string
  remaining_qty: number
  reorder_point: number
}

export interface LowStockPage {
  items: LowStockRow[]
  total: number
}
