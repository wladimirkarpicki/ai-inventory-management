import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { ThemeProvider, useTheme } from "./theme"

function Probe() {
  const { theme, toggleTheme } = useTheme()

  return (
    <button type="button" onClick={toggleTheme}>
      {theme}
    </button>
  )
}

describe("ThemeProvider", () => {
  it("defaults to light and toggles the dark class on <html>", async () => {
    window.localStorage.removeItem("ims_theme")
    document.documentElement.classList.remove("dark")

    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    )

    expect(screen.getByRole("button")).toHaveTextContent("light")
    expect(document.documentElement).not.toHaveClass("dark")

    await userEvent.click(screen.getByRole("button"))

    expect(screen.getByRole("button")).toHaveTextContent("dark")
    expect(document.documentElement).toHaveClass("dark")
    expect(window.localStorage.getItem("ims_theme")).toBe("dark")
  })
})
