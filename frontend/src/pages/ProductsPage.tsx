import { FormEvent, useCallback, useEffect, useState } from "react"

import {
  api,
  type Brand,
  type Product,
  type ProductList,
} from "@/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface FormState {
  id: number | null
  brand_id: string
  name: string
  price: string
  quantity: string
}

const EMPTY_FORM: FormState = {
  id: null,
  brand_id: "",
  name: "",
  price: "",
  quantity: "",
}

export function ProductsPage() {
  const [list, setList] = useState<ProductList | null>(null)
  const [brands, setBrands] = useState<Brand[]>([])
  const [search, setSearch] = useState("")
  const [sort, setSort] = useState("name")
  const [direction, setDirection] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        search,
        sort,
        direction,
        page: String(page),
      })
      setList(await api<ProductList>(`/api/products?${params}`))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.")
    }
  }, [search, sort, direction, page])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    api<Brand[]>("/api/brands")
      .then(setBrands)
      .catch(() => undefined)
  }, [])

  function startEdit(product: Product) {
    setForm({
      id: product.id,
      brand_id: String(product.brand_id),
      name: product.name,
      price: String(product.price),
      quantity: String(product.quantity),
    })
    setShowForm(true)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const body = {
      brand_id: Number(form.brand_id),
      name: form.name,
      price: Number(form.price),
      quantity: Number(form.quantity),
    }

    try {
      if (form.id === null) {
        await api("/api/products", { method: "POST", body })
      } else {
        await api(`/api/products/${form.id}`, { method: "PATCH", body })
      }
      setForm(EMPTY_FORM)
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.")
    }
  }

  async function handleDelete(product: Product) {
    if (!window.confirm(`Delete product "${product.name}"?`)) {
      return
    }

    try {
      await api(`/api/products/${product.id}`, { method: "DELETE" })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.")
    }
  }

  function toggleSort(column: string) {
    if (sort === column) {
      setDirection(direction === "asc" ? "desc" : "asc")
    } else {
      setSort(column)
      setDirection("asc")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
        <Button
          onClick={() => {
            setForm(EMPTY_FORM)
            setShowForm((value) => !value)
          }}
        >
          {showForm ? "Close" : "Add product"}
        </Button>
      </div>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {form.id === null ? "Add product" : `Edit product #${form.id}`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="brand">Brand</Label>
                <select
                  id="brand"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                  value={form.brand_id}
                  onChange={(e) =>
                    setForm({ ...form, brand_id: e.target.value })
                  }
                  required
                >
                  <option value="">Select a brand…</option>
                  {brands.map((brand) => (
                    <option key={brand.id} value={brand.id}>
                      {brand.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="price">Price (USD)</Label>
                <Input
                  id="price"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={form.price}
                  onChange={(e) => setForm({ ...form, price: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="quantity">Quantity</Label>
                <Input
                  id="quantity"
                  type="number"
                  min="0"
                  value={form.quantity}
                  onChange={(e) =>
                    setForm({ ...form, quantity: e.target.value })
                  }
                  required
                />
              </div>

              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit">
                  {form.id === null ? "Add product" : "Save changes"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setForm(EMPTY_FORM)
                    setShowForm(false)
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center gap-2">
        <Input
          placeholder="Search by name or brand…"
          className="max-w-xs"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setPage(1)
          }}
        />
        {list && (
          <Badge variant="secondary">
            {list.total} product{list.total === 1 ? "" : "s"}
          </Badge>
        )}
      </div>

      {list && list.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No products match your filters.
        </p>
      ) : (
        list && (
          <>
            <div className="rounded-xl border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="cursor-pointer" onClick={() => toggleSort("id")}>
                      ID {sort === "id" && (direction === "asc" ? "↑" : "↓")}
                    </TableHead>
                    <TableHead className="cursor-pointer" onClick={() => toggleSort("brand")}>
                      Brand {sort === "brand" && (direction === "asc" ? "↑" : "↓")}
                    </TableHead>
                    <TableHead className="cursor-pointer" onClick={() => toggleSort("name")}>
                      Name {sort === "name" && (direction === "asc" ? "↑" : "↓")}
                    </TableHead>
                    <TableHead className="cursor-pointer" onClick={() => toggleSort("price")}>
                      Price {sort === "price" && (direction === "asc" ? "↑" : "↓")}
                    </TableHead>
                    <TableHead className="cursor-pointer" onClick={() => toggleSort("quantity")}>
                      Quantity {sort === "quantity" && (direction === "asc" ? "↑" : "↓")}
                    </TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {list.items.map((product) => (
                    <TableRow key={product.id}>
                      <TableCell>{product.id}</TableCell>
                      <TableCell>{product.brand}</TableCell>
                      <TableCell className="font-medium">{product.name}</TableCell>
                      <TableCell>${product.price.toFixed(2)}</TableCell>
                      <TableCell>
                        {product.quantity < 5 ? (
                          <Badge variant="destructive">{product.quantity}</Badge>
                        ) : (
                          product.quantity
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => startEdit(product)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => handleDelete(product)}
                        >
                          Delete
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Page {list.page} of {list.pages}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={list.page <= 1}
                  onClick={() => setPage(list.page - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={list.page >= list.pages}
                  onClick={() => setPage(list.page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )
      )}
    </div>
  )
}
