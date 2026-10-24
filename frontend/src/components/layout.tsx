import type { ReactNode } from "react"
import { Link, NavLink, useNavigate } from "react-router-dom"
import {
  ChevronDownIcon,
  KeyRoundIcon,
  LogOutIcon,
  PackageIcon,
} from "lucide-react"

import { useAuth } from "@/auth"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  "inline-flex shrink-0 items-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
  (isActive
    ? "bg-accent text-accent-foreground"
    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground")

function initials(username: string | undefined): string {
  if (!username) return "?"
  return username.slice(0, 2).toUpperCase()
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  function handleSignOut() {
    signOut()
    navigate("/login")
  }

  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-10 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4">
          <Link
            to="/"
            className="flex shrink-0 items-center gap-2 rounded-md px-1.5 py-1 text-sm font-semibold tracking-tight"
          >
            <PackageIcon className="size-4" />
            Inventory
          </Link>

          <nav className="flex flex-wrap items-center gap-1">
            <NavLink to="/" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/brands" className={navLinkClass}>
              Brands
            </NavLink>
            <NavLink to="/products" className={navLinkClass}>
              Products
            </NavLink>
            {user?.role === "admin" && (
              <NavLink to="/users" className={navLinkClass}>
                Users
              </NavLink>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-2 px-1.5">
                  <span className="flex size-6 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
                    {initials(user?.username)}
                  </span>
                  <span className="hidden max-w-40 truncate sm:inline">
                    {user?.username}
                  </span>
                  <ChevronDownIcon className="size-3.5 opacity-50" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuLabel className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">
                    {user?.username}
                  </span>
                  {user?.role === "admin" && (
                    <Badge variant="secondary">admin</Badge>
                  )}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/password")}>
                  <KeyRoundIcon />
                  Change password
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={handleSignOut}
                >
                  <LogOutIcon />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  )
}
