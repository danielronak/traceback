// The teaching state of one card: how far up the hint ladder the learner is.

export interface CardState {
  hints: number; // how many hints are showing
  fix: boolean; // the fix has been revealed
  why: boolean; // "Why does Python work this way?" is open
  wrong: number[]; // quiz choices already tried and wrong
  answered: boolean; // the quiz was answered correctly
}

export const FRESH: CardState = { hints: 0, fix: false, why: false, wrong: [], answered: false };

/** Answer the card's quiz. A wrong choice is remembered so it can be greyed out. */
export function answerQuiz(state: CardState, choice: number, correct: number): CardState {
  if (choice === correct) return { ...state, answered: true };
  return state.wrong.includes(choice) ? state : { ...state, wrong: [...state.wrong, choice] };
}

export type CardAction = "hint" | "fix" | "why";

export function advance(state: CardState, action: CardAction, hintCount: number, hasFix: boolean): CardState {
  switch (action) {
    case "hint":
      // The rung after the last hint is the fix itself (when there is one).
      if (state.hints < hintCount) return { ...state, hints: state.hints + 1 };
      return hasFix ? { ...state, fix: true } : state;
    case "fix":
      return { ...state, fix: true };
    case "why":
      return { ...state, why: !state.why };
  }
}

/** The label for the hint button, or null when the ladder is used up. */
export function hintLabel(state: CardState, hintCount: number): string | null {
  if (state.hints === 0 && hintCount > 0) return "Give me a hint";
  if (state.hints < hintCount) return "Another hint";
  return null;
}

export const SEVERITY_LABEL = {
  syntax: "Won't run",
  runtime: "Crashed",
  style: "Style",
  logic: "Wrong answer",
} as const;
