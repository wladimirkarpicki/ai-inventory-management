import { FormEvent, useState } from "react"
import { useNavigate } from "react-router-dom"

import { api, setToken, type AuthResponse } from "@/api"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function SetupPage() {
  const navigate = useNavigate()

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (password !== confirm) {
      setError("Passwords do not match.")
      return
    }

    setBusy(true)

    try {
      const data = await api<AuthResponse>("/api/auth/setup", {
        method: "POST",
        body: { username, password },
      })
      setToken(data.access_token)
      navigate("/")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup failed.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">First-time setup</CardTitle>
          <CardDescription>
            Create the initial admin account. This page is only available
            while the installation has no users.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <p className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                autoComplete="username"
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
                autoComplete="new-password"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </div>

            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Creating…" : "Create admin account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
