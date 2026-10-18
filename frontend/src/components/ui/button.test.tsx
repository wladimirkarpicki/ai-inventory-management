import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { Button } from "./button"

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Save changes</Button>)

    expect(
      screen.getByRole("button", { name: "Save changes" })
    ).toBeInTheDocument()
  })

  it("fires onClick when clicked", async () => {
    const onClick = vi.fn()

    render(<Button onClick={onClick}>Click me</Button>)

    await userEvent.click(screen.getByRole("button", { name: "Click me" }))

    expect(onClick).toHaveBeenCalledOnce()
  })

  it("does not fire onClick while disabled", async () => {
    const onClick = vi.fn()

    render(
      <Button disabled onClick={onClick}>
        Nope
      </Button>
    )

    expect(screen.getByRole("button", { name: "Nope" })).toBeDisabled()

    await userEvent.click(screen.getByRole("button", { name: "Nope" }))

    expect(onClick).not.toHaveBeenCalled()
  })
})
