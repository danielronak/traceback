import { describe, expect, it } from "vitest";
import { advance, FRESH, hintLabel } from "../../src/cards/ladder";

describe("the hint ladder", () => {
  it("climbs one hint at a time, then reaches the fix", () => {
    let state = FRESH;
    expect(hintLabel(state, 2)).toBe("Give me a hint");
    state = advance(state, "hint", 2, true);
    expect(state).toEqual({ hints: 1, fix: false, why: false });
    expect(hintLabel(state, 2)).toBe("Another hint");
    state = advance(state, "hint", 2, true);
    expect(hintLabel(state, 2)).toBeNull();
    state = advance(state, "hint", 2, true);
    expect(state.fix).toBe(true);
  });

  it("never reveals a fix that doesn't exist", () => {
    const state = advance({ hints: 3, fix: false, why: false }, "hint", 3, false);
    expect(state.fix).toBe(false);
  });

  it("toggles the why section", () => {
    const open = advance(FRESH, "why", 0, false);
    expect(open.why).toBe(true);
    expect(advance(open, "why", 0, false).why).toBe(false);
  });
});
