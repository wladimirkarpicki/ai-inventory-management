import { FormEvent, useCallback, useEffect, useState } from "react"
import {
  ArrowDownIcon,
  ArrowUpIcon,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react"
import { toast } from "sonner"

import { api, type Brand, type Product, type ProductList } from "@/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"

interface FormState {
  id: number | null
  brand_id: string
  name: string
  price: string
  quantity: string
  reason: string
}

const EMPTY_FORM: FormState = {
  id: null,
  brand_id: "",
  name: "",
  price: "",
  quantity: "",
  reason: "manual_edit",
}

function money(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  })
}

export function ProductsPage() {
  const [list, setList] = useState<ProductList | null>(null)
  const [brands, setBrands] = useState<Brand[]>([])
  const [search, setSearch] = useState("")
  const [sort, setSort] = useState("name")
  const [direction, setDirection] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(1)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toDelete, setToDelete] = useState<Product | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        search,
        sort,
        direction,
        page: String(page),
      })
      setList(await api<ProductList>(`/api/products?${params}`))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load.")
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

  function startAdd() {
    setForm(EMPTY_FORM)
    setFormOpen(true)
  }

  function startEdit(product: Product) {
    setForm({
      id: product.id,
      brand_id: String(product.brand_id),
      name: product.name,
      price: String(product.price),
      quantity: String(product.quantity),
      reason: "manual_edit",
    })
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
    setForm(EMPTY_FORM)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()

    if (!form.brand_id) {
      toast.error("Select a brand first.")
      return
    }

    setSaving(true)

    const body = {
      brand_id: Number(form.brand_id),
      name: form.name,
      price: Number(form.price),
      quantity: Number(form.quantity),
    }

    try {
      if (form.id === null) {
        await api("/api/products", { method: "POST", body })
        toast.success("Product added.")
      } else {
        await api(`/api/products/${form.id}`, {
          method: "PATCH",
          body: { ...body, reason: form.reason },
        })
        toast.success("Product updated.")
      }
      closeForm()
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed.")
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!toDelete) return

    setDeleting(true)
    try {
      await api(`/api/products/${toDelete.id}`, { method: "DELETE" })
      toast.success(`Deleted "${toDelete.name}".`)
      setToDelete(null)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed.")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
          <p className="text-sm text-muted-foreground">
            Manage the products in your inventory.
          </p>
        </div>
        <Button onClick={startAdd}>
          <PlusIcon />
          Add product
        </Button>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-0 flex-1 sm:max-w-xs">
            <SearchIcon className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              placeholder="Search products…"
              className="pl-8"
            />
          </div>

          <Select
            value={sort}
            onValueChange={(value) => {
              setSort(value)
              setPage(1)
            }}
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="name">Sort: Name</SelectItem>
              <SelectItem value="price">Sort: Price</SelectItem>
              <SelectItem value="quantity">Sort: Quantity</SelectItem>
              <SelectItem value="brand">Sort: Brand</SelectItem>
            </SelectContent>
          </Select>

          <Button
            variant="outline"
            size="icon"
            aria-label="Toggle sort direction"
            title={
              direction === "asc" ? "Ascending" : "Descending"
            }
            onClick={() =>
              setDirection((current) => (current === "asc" ? "desc" : "asc"))
            }
          >
            {direction === "asc" ? <ArrowUpIcon /> : <ArrowDownIcon />}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {!list ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : list.items.length === 0 ? (
            <div className="flex flex-col items-center gap-1 py-10 text-center">
              <p className="text-sm font-medium">No products found</p>
              <p className="text-sm text-muted-foreground">
                Try adjusting the search, or add a new product.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Brand</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead className="text-right">Quantity</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.items.map((product) => (
                  <TableRow key={product.id}>
                    <TableCell>
                      <Badge variant="outline">{product.brand}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {product.name}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {money(product.price)}
                    </TableCell>
                    <TableCell className="text-right">
                      <span
                        className={cn(
                          "tabular-nums",
                          product.quantity === 0 && "font-medium text-destructive"
                        )}
                      >
                        {product.quantity}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Edit ${product.name}`}
                          onClick={() => startEdit(product)}
                        >
                          <PencilIcon />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="text-destructive hover:text-destructive"
                          aria-label={`Delete ${product.name}`}
                          onClick={() => setToDelete(product)}
                        >
                          <Trash2Icon />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {list && (
          <div className="flex items-center justify-between border-t px-6 py-4">
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
        )}
      </Card>

      <Dialog
        open={formOpen}
        onOpenChange={(open) => {
          if (!open) closeForm()
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {form.id === null ? "Add product" : "Edit product"}
            </DialogTitle>
            <DialogDescription>
              {form.id === null
                ? "Create a new product in your inventory."
                : "Update the details of this product."}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="brand">Brand</Label>
              <Select
                value={form.brand_id}
                onValueChange={(value) =>
                  setForm((current) => ({ ...current, brand_id: value }))
                }
              >
                <SelectTrigger id="brand" className="w-full">
                  <SelectValue placeholder="Select a brand" />
                </SelectTrigger>
                <SelectContent>
                  {brands.map((brand) => (
                    <SelectItem key={brand.id} value={String(brand.id)}>
                      {brand.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={form.name}
                onChange={(e) =>
                  setForm((current) => ({ ...current, name: e.target.value }))
                }
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="price">Price (USD)</Label>
                <Input
                  id="price"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.price}
                  onChange={(e) =>
                    setForm((current) => ({ ...current, price: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="quantity">Quantity</Label>
                <Input
                  id="quantity"
                  type="number"
                  min="0"
                  step="1"
                  value={form.quantity}
                  onChange={(e) =>
                    setForm((current) => ({
                      ...current,
                      quantity: e.target.value,
                    }))
                  }
                  required
                />
              </div>
            </div>

            {form.id !== null && (
              <div className="grid gap-2">
                <Label htmlFor="reason">Reason for change</Label>
                <Select
                  value={form.reason}
                  onValueChange={(value) =>
                    setForm((current) => ({ ...current, reason: value }))
                  }
                >
                  <SelectTrigger id="reason" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual_edit">Correction</SelectItem>
                    <SelectItem value="restock">Restock</SelectItem>
                    <SelectItem value="sale">Sale</SelectItem>
                    <SelectItem value="write_off">Write-off</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={closeForm}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save product"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete product</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete "{toDelete?.name}". This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault()
                void handleDelete()
              }}
            >
              {deleting ? "Deleting…" : "Delete product"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
