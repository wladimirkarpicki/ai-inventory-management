import { FormEvent, useCallback, useEffect, useState } from "react"
import { PencilIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { api, type Brand } from "@/api"
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
import { Skeleton } from "@/components/ui/skeleton"
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
  name: string
}

const EMPTY_FORM: FormState = { id: null, name: "" }

export function BrandsPage() {
  const [brands, setBrands] = useState<Brand[] | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toDelete, setToDelete] = useState<Brand | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      setBrands(await api<Brand[]>("/api/brands"))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load.")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  function startAdd() {
    setForm(EMPTY_FORM)
    setFormOpen(true)
  }

  function startEdit(brand: Brand) {
    setForm({ id: brand.id, name: brand.name })
    setFormOpen(true)
  }

  function closeForm() {
    setFormOpen(false)
    setForm(EMPTY_FORM)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)

    try {
      if (form.id === null) {
        await api("/api/brands", { method: "POST", body: { name: form.name } })
        toast.success("Brand added.")
      } else {
        await api(`/api/brands/${form.id}`, {
          method: "PATCH",
          body: { name: form.name },
        })
        toast.success("Brand renamed.")
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
      await api(`/api/brands/${toDelete.id}`, { method: "DELETE" })
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
          <h1 className="text-2xl font-semibold tracking-tight">Brands</h1>
          <p className="text-sm text-muted-foreground">
            Organize products by brand.
          </p>
        </div>
        <Button onClick={startAdd}>
          <PlusIcon />
          Add brand
        </Button>
      </div>

      <Card>
        <CardContent>
          {!brands ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : brands.length === 0 ? (
            <div className="flex flex-col items-center gap-1 py-10 text-center">
              <p className="text-sm font-medium">No brands yet</p>
              <p className="text-sm text-muted-foreground">
                Add your first brand to group products together.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Products</TableHead>
                  <TableHead className="w-24" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {brands.map((brand) => (
                  <TableRow key={brand.id}>
                    <TableCell className="font-medium">{brand.name}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {brand.product_count ?? 0}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Rename ${brand.name}`}
                          onClick={() => startEdit(brand)}
                        >
                          <PencilIcon />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="text-destructive hover:text-destructive"
                          aria-label={`Delete ${brand.name}`}
                          onClick={() => setToDelete(brand)}
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
      </Card>

      <Dialog
        open={formOpen}
        onOpenChange={(open) => {
          if (!open) closeForm()
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {form.id === null ? "Add brand" : "Rename brand"}
            </DialogTitle>
            <DialogDescription>
              {form.id === null
                ? "Create a new brand for your products."
                : "Choose a new name for this brand."}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="brand-name">Name</Label>
              <Input
                id="brand-name"
                value={form.name}
                onChange={(e) =>
                  setForm((current) => ({ ...current, name: e.target.value }))
                }
                placeholder="e.g. Acme"
                required
                autoFocus
              />
            </div>

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
                {saving ? "Saving…" : "Save brand"}
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
            <AlertDialogTitle>Delete brand</AlertDialogTitle>
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
              {deleting ? "Deleting…" : "Delete brand"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
