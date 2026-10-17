import { FormEvent, useCallback, useEffect, useState } from "react"

import { api, type Brand } from "@/api"
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

export function BrandsPage() {
  const [brands, setBrands] = useState<Brand[]>([])
  const [name, setName] = useState("")
  const [editing, setEditing] = useState<{ id: number; name: string } | null>(
    null
  )
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setBrands(await api<Brand[]>("/api/brands"))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function handleAdd(event: FormEvent) {
    event.preventDefault()
    setError(null)

    try {
      await api("/api/brands", { method: "POST", body: { name } })
      setName("")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.")
    }
  }

  async function handleRename(event: FormEvent) {
    event.preventDefault()

    if (!editing) {
      return
    }

    setError(null)

    try {
      await api(`/api/brands/${editing.id}`, {
        method: "PATCH",
        body: { name: editing.name },
      })
      setEditing(null)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rename failed.")
    }
  }

  async function handleDelete(brand: Brand) {
    if (!window.confirm(`Delete brand "${brand.name}"?`)) {
      return
    }

    setError(null)

    try {
      await api(`/api/brands/${brand.id}`, { method: "DELETE" })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.")
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Brands</h1>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="text-base">Add brand</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="flex gap-2">
            <Input
              placeholder="Brand name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <Button type="submit">Add</Button>
          </form>
        </CardContent>
      </Card>

      <div className="max-w-2xl rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Products</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {brands.map((brand) => (
              <TableRow key={brand.id}>
                <TableCell className="font-medium">
                  {editing?.id === brand.id ? (
                    <form onSubmit={handleRename} className="flex gap-2">
                      <Input
                        value={editing.name}
                        onChange={(e) =>
                          setEditing({ ...editing, name: e.target.value })
                        }
                        required
                      />
                      <Button type="submit" size="sm">
                        Save
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setEditing(null)}
                      >
                        Cancel
                      </Button>
                    </form>
                  ) : (
                    brand.name
                  )}
                </TableCell>
                <TableCell>{brand.product_count ?? 0}</TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={editing?.id === brand.id}
                    onClick={() =>
                      setEditing({ id: brand.id, name: brand.name })
                    }
                  >
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => handleDelete(brand)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {brands.length === 0 && (
              <TableRow>
                <TableCell colSpan={3} className="text-muted-foreground">
                  No brands yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
