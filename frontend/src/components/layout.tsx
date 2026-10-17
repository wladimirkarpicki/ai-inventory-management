import type { ReactNode } from "react"
import { Link, NavLink, useNavigate } from "react-router-dom"

import { useAuth } from "@/auth"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  "text-sm font-medium transition-colors hover:text-foreground " +
  (isActive ? "text-foreground" : "text-muted-foreground")

export function Layout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  function handleSignOut() {
    signOut()
    navigate("/login")
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-10 border-b bg-card">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <Link to="/" className="text-sm font-semibold tracking-tight">
            Inventory
          </Link>

          <nav className="flex items-center gap-4">
            <NavLink to="/" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/products" className={navLinkClass}>
              Products
            </NavLink>
            <NavLink to="/brands" className={navLinkClass}>
              Brands
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/users" className={navLinkClass}>
                Users
              </NavLink>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {user?.username}
            </span>
            {user?.role === "admin" && <Badge>admin</Badge>}
            <NavLink to="/password" className={navLinkClass}>
              Password
            </NavLink>
            <Button variant="outline" size="sm" onClick={handleSignOut}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  )
}
