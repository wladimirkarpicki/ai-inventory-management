import { FormEvent, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { api, type AuthStatus } from "@/api"
import { useAuth } from "@/auth"
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

export function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [setupRequired, setSetupRequired] = useState(false)

  useEffect(() => {
    api<AuthStatus>("/api/auth/status")
      .then((status) => setSetupRequired(status.setup_required))
      .catch(() => setError("Cannot reach the server."))
  }, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setBusy(true)

    try {
      await signIn(username, password)
      navigate("/")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">Sign in</CardTitle>
          <CardDescription>
            Inventory Management System
          </CardDescription>
        </CardHeader>
        <CardContent>
          {setupRequired && (
            <p className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              No accounts exist yet.{" "}
              <Link to="/setup" className="font-medium underline">
                Run the first-time setup
              </Link>
              .
            </p>
          )}

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
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
