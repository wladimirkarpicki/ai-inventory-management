import type { ReactNode } from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { AuthProvider, useAuth } from "@/auth"
import { Layout } from "@/components/layout"
import { BrandsPage } from "@/pages/BrandsPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { LoginPage } from "@/pages/LoginPage"
import { PasswordPage } from "@/pages/PasswordPage"
import { ProductsPage } from "@/pages/ProductsPage"
import { SetupPage } from "@/pages/SetupPage"
import { UsersPage } from "@/pages/UsersPage"

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Loading…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <Layout>{children}</Layout>
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  if (user?.role !== "admin") {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupPage />} />

        <Route
          path="/"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/products"
          element={
            <RequireAuth>
              <ProductsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/brands"
          element={
            <RequireAuth>
              <BrandsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/password"
          element={
            <RequireAuth>
              <PasswordPage />
            </RequireAuth>
          }
        />
        <Route
          path="/users"
          element={
            <RequireAuth>
              <RequireAdmin>
                <UsersPage />
              </RequireAdmin>
            </RequireAuth>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
