// The code editor: CodeMirror 6 with PyMentor's underlines and line tints.

import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { python } from "@codemirror/lang-python";
import {
  bracketMatching,
  defaultHighlightStyle,
  indentOnInput,
  indentUnit,
  syntaxHighlighting,
} from "@codemirror/language";
import { type Diagnostic as CmDiagnostic, lintGutter, setDiagnostics } from "@codemirror/lint";
import { EditorState, RangeSetBuilder, StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  drawSelection,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { useEffect, useRef } from "preact/hooks";
import type { Finding } from "../engine/types";
import { diagnosticRange } from "./positions";

// One CodeMirror severity per kind of mistake, so each gets its own gutter colour.
const CM_SEVERITY = { syntax: "error", runtime: "warning", logic: "hint", style: "info" } as const;

// Whole-line tints for the errors that stop a program (red and orange).
const setTints = StateEffect.define<{ line: number; severity: string }[]>();
const tints = StateField.define<DecorationSet>({
  create: () => Decoration.none,
  update(value, transaction) {
    value = value.map(transaction.changes);
    for (const effect of transaction.effects) {
      if (!effect.is(setTints)) continue;
      const builder = new RangeSetBuilder<Decoration>();
      const doc = transaction.state.doc;
      for (const { line, severity } of [...effect.value].sort((a, b) => a.line - b.line)) {
        if (line < 1 || line > doc.lines) continue;
        builder.add(doc.line(line).from, doc.line(line).from, Decoration.line({ class: `pm-tint-${severity}` }));
      }
      value = builder.finish();
    }
    return value;
  },
  provide: (field) => EditorView.decorations.from(field),
});

export interface EditorProps {
  /** Replaces the document whenever `version` changes (exercise switch, accepted fix). */
  doc: string;
  version: number;
  findings: Finding[];
  onChange(source: string): void;
  onLineLeave(): void;
  onSelectFinding(index: number): void;
  label: string;
}

export function Editor(props: EditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView>();
  const latest = useRef(props);
  latest.current = props;

  useEffect(() => {
    let lastLine = 1;
    view.current = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: props.doc,
        extensions: [
          lineNumbers(),
          highlightActiveLineGutter(),
          highlightActiveLine(),
          history(),
          drawSelection(),
          indentOnInput(),
          bracketMatching(),
          indentUnit.of("    "),
          EditorState.tabSize.of(4),
          python(),
          syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
          keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
          lintGutter(),
          tints,
          EditorView.contentAttributes.of({ "aria-label": props.label }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) latest.current.onChange(update.state.doc.toString());
            if (update.selectionSet) {
              const head = update.state.selection.main.head;
              const line = update.state.doc.lineAt(head).number;
              if (line !== lastLine) {
                lastLine = line;
                latest.current.onLineLeave();
              }
              const index = latest.current.findings.findIndex((f) => {
                const range = diagnosticRange(update.state.doc, f.diagnostic);
                return range.from <= head && head <= range.to;
              });
              if (index >= 0) latest.current.onSelectFinding(index);
            }
          }),
        ],
      }),
    });
    return () => view.current?.destroy();
  }, []);

  useEffect(() => {
    const v = view.current;
    if (!v || v.state.doc.toString() === props.doc) return;
    v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: props.doc } });
  }, [props.version]);

  useEffect(() => {
    const v = view.current;
    if (!v) return;
    const doc = v.state.doc;
    const diagnostics: CmDiagnostic[] = props.findings.map((f) => ({
      ...diagnosticRange(doc, f.diagnostic),
      severity: CM_SEVERITY[f.diagnostic.severity],
      message: f.card?.title ?? `${f.diagnostic.code}: ${f.diagnostic.message}`,
      markClass: `pm-mark pm-mark-${f.diagnostic.severity}`,
    }));
    const blocking = props.findings
      .filter((f) => f.diagnostic.severity === "syntax" || f.diagnostic.severity === "runtime")
      .map((f) => ({ line: f.diagnostic.line, severity: f.diagnostic.severity }));
    v.dispatch(setDiagnostics(v.state, diagnostics), { effects: setTints.of(blocking) });
  }, [props.findings]);

  return <div class="editor" ref={host} />;
}
