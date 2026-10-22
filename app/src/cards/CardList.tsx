// The correction cards: one per finding, the selected one open.

import type { Finding } from "../engine/types";
import { findingKey } from "../editor/positions";
import { type CardAction, type CardState, FRESH, SEVERITY_LABEL, advance, answerQuiz, hintLabel } from "./ladder";
import { Code } from "./Code";

interface Props {
  findings: Finding[];
  selected: number;
  states: Record<string, CardState>;
  onSelect(index: number): void;
  onState(key: string, state: CardState): void;
  onAcceptFix(finding: Finding): void;
  acceptLabel?: string;
  emptyMessage: string;
  /** Repetition becomes practice: ask the card's quiz before helping. */
  practiceDue?(cardId: string): boolean;
  onPractised?(cardId: string): void;
}

export function CardList(props: Props) {
  if (props.findings.length === 0) {
    return <p class="cards-empty">{props.emptyMessage}</p>;
  }
  return (
    <ol class="cards" aria-label="Problems found">
      {props.findings.map((finding, index) => {
        const key = findingKey(finding.diagnostic);
        return (
          <li key={key}>
            <CardView
              finding={finding}
              open={index === props.selected}
              state={props.states[key] ?? FRESH}
              onOpen={() => props.onSelect(index)}
              onAction={(action) =>
                props.onState(
                  key,
                  advance(props.states[key] ?? FRESH, action, finding.card?.hints.length ?? 0, !!finding.fix),
                )
              }
              onAcceptFix={() => props.onAcceptFix(finding)}
              acceptLabel={props.acceptLabel ?? "Accept fix"}
              quizzing={!!finding.card?.quiz && !!props.practiceDue?.(finding.card.id)}
              onAnswer={(choice) => {
                const quiz = finding.card!.quiz!;
                const next = answerQuiz(props.states[key] ?? FRESH, choice, quiz.answer);
                props.onState(key, next);
                if (next.answered) props.onPractised?.(finding.card!.id);
              }}
            />
          </li>
        );
      })}
    </ol>
  );
}

interface CardProps {
  finding: Finding;
  open: boolean;
  state: CardState;
  onOpen(): void;
  onAction(action: CardAction): void;
  onAcceptFix(): void;
  acceptLabel: string;
  quizzing: boolean;
  onAnswer(choice: number): void;
}

function CardView(props: CardProps) {
  const { finding, open, state, onOpen, onAction, onAcceptFix, acceptLabel, onAnswer } = props;
  const quizzing = props.quizzing && !state.answered;
  const { diagnostic: d, card, fix } = finding;
  const title = card?.title ?? `${d.code}: ${d.message}`;
  const hintCount = card?.hints.length ?? 0;
  const nextHint = hintLabel(state, hintCount);
  return (
    <article class={`card card-${d.severity}${open ? " open" : ""}`}>
      <button type="button" class="card-head" aria-expanded={open} onClick={onOpen}>
        <span class={`badge badge-${d.severity}`}>{SEVERITY_LABEL[d.severity]}</span>
        <span class="card-title">
          <Code text={title} />
        </span>
        <span class="card-line">line {d.line}</span>
      </button>
      {open && quizzing && card?.quiz && (
        <div class="card-body quiz">
          <p class="quiz-intro">You've run into this one a few times. A quick question first:</p>
          <p class="quiz-question">
            <Code text={card.quiz.question} />
          </p>
          <div class="quiz-choices" role="group" aria-label="Choose an answer">
            {card.quiz.choices.map((choice, i) => (
              <button key={choice} type="button" disabled={state.wrong.includes(i)} onClick={() => onAnswer(i)}>
                <Code text={choice} />
              </button>
            ))}
          </div>
          {state.wrong.length > 0 && (
            <p class="quiz-feedback" role="status">
              Not quite. Have another go.
            </p>
          )}
        </div>
      )}
      {open && !quizzing && (
        <div class="card-body">
          {state.answered && card?.quiz && (
            <p class="quiz-right" role="status">
              Right! <Code text={card.quiz.explain} />
            </p>
          )}
          {card ? (
            <p class="card-rule">
              <Code text={card.rule} />
            </p>
          ) : (
            <p class="card-rule">
              PyMentor doesn't have a lesson for this one yet, so here is Python's own message:{" "}
              <code>{d.message}</code>
            </p>
          )}
          {state.hints > 0 && (
            <ol class="hints" aria-label="Hints">
              {card!.hints.slice(0, state.hints).map((hint) => (
                <li key={hint}>
                  <Code text={hint} />
                </li>
              ))}
            </ol>
          )}
          {state.fix && fix && (
            <div class="fix" aria-label="Suggested fix">
              {fix.before && <pre class="fix-before">{fix.before}</pre>}
              <pre class="fix-after">{fix.after}</pre>
              <p class="fix-note">Checked: this change removes the error.</p>
            </div>
          )}
          {state.why && card && (
            <div class="why">
              <p>
                <Code text={card.why} />
              </p>
              {card.exceptions && (
                <p class="exceptions">
                  <Code text={card.exceptions} />
                </p>
              )}
            </div>
          )}
          <div class="card-actions">
            {state.fix && fix ? (
              <button type="button" class="primary" onClick={onAcceptFix}>
                {acceptLabel}
              </button>
            ) : (
              nextHint && (
                <button type="button" class="primary" onClick={() => onAction("hint")}>
                  {nextHint}
                </button>
              )
            )}
            {fix && !state.fix && (
              <button type="button" onClick={() => onAction("fix")}>
                Show the fix
              </button>
            )}
            {card && (
              <button type="button" aria-pressed={state.why} onClick={() => onAction("why")}>
                Why does Python work this way?
              </button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
