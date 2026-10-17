import { FormEvent, useCallback, useEffect, useState } from "react"

import { api, type UserRow } from "@/api"
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

export function UsersPage() {
  const [users, setUsers] = useState<UserRow[]>([])
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState("user")
  const [resetting, setResetting] = useState<UserRow | null>(null)
  const [resetPassword, setResetPassword] = useState("")
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setUsers(await api<UserRow[]>("/api/users"))
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
      await api("/api/users", {
        method: "POST",
        body: { username, password, role },
      })
      setUsername("")
      setPassword("")
      setRole("user")
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed.")
    }
  }

  async function toggleRole(user: UserRow) {
    setError(null)

    try {
      await api(`/api/users/${user.id}`, {
        method: "PATCH",
        body: { role: user.role === "admin" ? "user" : "admin" },
      })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Role change failed.")
    }
  }

  async function handleReset(event: FormEvent) {
    event.preventDefault()

    if (!resetting) {
      return
    }

    setError(null)

    try {
      await api(`/api/users/${resetting.id}/password`, {
        method: "POST",
        body: { password: resetPassword },
      })
      setResetting(null)
      setResetPassword("")
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.")
    }
  }

  async function handleDelete(user: UserRow) {
    if (
      !window.confirm(
        `Delete account "${user.username}"? Their sessions stop working immediately.`
      )
    ) {
      return
    }

    setError(null)

    try {
      await api(`/api/users/${user.id}`, { method: "DELETE" })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.")
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Users</h1>

      {error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <Card className="max-w-md">
        <CardHeader>
          <CardTitle className="text-base">Add user</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password (at least 8 characters)</Label>
              <Input
                id="password"
                type="password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <select
                id="role"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>

            <Button type="submit">Add user</Button>
          </form>
        </CardContent>
      </Card>

      {resetting && (
        <Card className="max-w-md border-amber-300">
          <CardHeader>
            <CardTitle className="text-base">
              Reset password for {resetting.username}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleReset} className="flex gap-2">
              <Input
                type="password"
                placeholder="New password (min 8 characters)"
                minLength={8}
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                required
              />
              <Button type="submit">Set</Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setResetting(null)}
              >
                Cancel
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="max-w-3xl rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Username</TableHead>
              <TableHead>Role</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">
                  {user.username}
                  {user.is_you && (
                    <span className="ml-2 text-xs text-muted-foreground">
                      (you)
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={user.role === "admin" ? "default" : "secondary"}>
                    {user.role}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleRole(user)}
                  >
                    {user.role === "admin" ? "Make user" : "Make admin"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setResetting(user)}
                  >
                    Password
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    onClick={() => handleDelete(user)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
