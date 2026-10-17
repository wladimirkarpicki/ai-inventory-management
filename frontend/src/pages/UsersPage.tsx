import { FormEvent, useCallback, useEffect, useState } from "react"
import { KeyRoundIcon, PlusIcon, Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { api, type UserRow } from "@/api"
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

interface AddFormState {
  username: string
  password: string
  role: string
}

const EMPTY_ADD: AddFormState = { username: "", password: "", role: "user" }

export function UsersPage() {
  const [users, setUsers] = useState<UserRow[] | null>(null)
  const [addForm, setAddForm] = useState<AddFormState>(EMPTY_ADD)
  const [addOpen, setAddOpen] = useState(false)
  const [addSaving, setAddSaving] = useState(false)
  const [resetting, setResetting] = useState<UserRow | null>(null)
  const [resetPassword, setResetPassword] = useState("")
  const [resetSaving, setResetSaving] = useState(false)
  const [toDelete, setToDelete] = useState<UserRow | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    try {
      setUsers(await api<UserRow[]>("/api/users"))
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load.")
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  function closeAdd() {
    setAddOpen(false)
    setAddForm(EMPTY_ADD)
  }

  async function handleAdd(event: FormEvent) {
    event.preventDefault()
    setAddSaving(true)

    try {
      await api("/api/users", {
        method: "POST",
        body: {
          username: addForm.username,
          password: addForm.password,
          role: addForm.role,
        },
      })
      toast.success("User added.")
      closeAdd()
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed.")
    } finally {
      setAddSaving(false)
    }
  }

  async function toggleRole(user: UserRow) {
    try {
      await api(`/api/users/${user.id}`, {
        method: "PATCH",
        body: { role: user.role === "admin" ? "user" : "admin" },
      })
      toast.success(`Role updated for ${user.username}.`)
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Role change failed.")
    }
  }

  async function handleReset(event: FormEvent) {
    event.preventDefault()

    if (!resetting) {
      return
    }

    setResetSaving(true)

    try {
      await api(`/api/users/${resetting.id}/password`, {
        method: "POST",
        body: { password: resetPassword },
      })
      toast.success(`Password reset for ${resetting.username}.`)
      setResetting(null)
      setResetPassword("")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reset failed.")
    } finally {
      setResetSaving(false)
    }
  }

  async function handleDelete() {
    if (!toDelete) return

    setDeleting(true)
    try {
      await api(`/api/users/${toDelete.id}`, { method: "DELETE" })
      toast.success(`Deleted "${toDelete.username}".`)
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
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="text-sm text-muted-foreground">
            Manage who can access the system.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)}>
          <PlusIcon />
          Add user
        </Button>
      </div>

      <Card>
        <CardContent>
          {!users ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : users.length === 0 ? (
            <div className="flex flex-col items-center gap-1 py-10 text-center">
              <p className="text-sm font-medium">No users</p>
              <p className="text-sm text-muted-foreground">
                Add a user to give them access.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead className="w-48" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <span className="font-medium">{user.username}</span>
                      {user.is_you && (
                        <Badge variant="outline" className="ml-2">
                          You
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={user.role === "admin" ? "default" : "secondary"}
                      >
                        {user.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleRole(user)}
                        >
                          {user.role === "admin" ? "Make user" : "Make admin"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Reset password for ${user.username}`}
                          title="Reset password"
                          onClick={() => {
                            setResetting(user)
                            setResetPassword("")
                          }}
                        >
                          <KeyRoundIcon />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="text-destructive hover:text-destructive"
                          aria-label={`Delete ${user.username}`}
                          onClick={() => setToDelete(user)}
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
        open={addOpen}
        onOpenChange={(open) => {
          if (!open) closeAdd()
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add user</DialogTitle>
            <DialogDescription>
              Create a new account with a username, password and role.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleAdd} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="new-username">Username</Label>
              <Input
                id="new-username"
                autoComplete="off"
                value={addForm.username}
                onChange={(e) =>
                  setAddForm((current) => ({
                    ...current,
                    username: e.target.value,
                  }))
                }
                required
                autoFocus
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="new-password">
                Password (at least 8 characters)
              </Label>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={addForm.password}
                onChange={(e) =>
                  setAddForm((current) => ({
                    ...current,
                    password: e.target.value,
                  }))
                }
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="new-role">Role</Label>
              <Select
                value={addForm.role}
                onValueChange={(value) =>
                  setAddForm((current) => ({ ...current, role: value }))
                }
              >
                <SelectTrigger id="new-role" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={closeAdd}
                disabled={addSaving}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={addSaving}>
                {addSaving ? "Adding…" : "Add user"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={resetting !== null}
        onOpenChange={(open) => {
          if (!open) {
            setResetting(null)
            setResetPassword("")
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>
              Set a new password (at least 8 characters) for "
              {resetting?.username}".
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleReset} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="reset-password">New password</Label>
              <Input
                id="reset-password"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                required
                autoFocus
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setResetting(null)
                  setResetPassword("")
                }}
                disabled={resetSaving}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={resetSaving}>
                {resetSaving ? "Saving…" : "Set password"}
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
            <AlertDialogTitle>Delete account</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete "{toDelete?.username}". Their
              sessions stop working immediately.
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
              {deleting ? "Deleting…" : "Delete account"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
