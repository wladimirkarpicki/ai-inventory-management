import { describe, expect, it } from "vitest"

import { cn } from "./utils"

describe("cn", () => {
  it("joins conditional class names", () => {
    expect(cn("px-2", true && "py-1", false && "p-4")).toBe("px-2 py-1")
  })

  it("resolves tailwind conflicts keeping the last class", () => {
    expect(cn("px-2", "px-4")).toBe("px-4")
  })
})
