// Static syntax highlighting for lesson snippets, using the same Python grammar
// as the editor but without an editor instance.

import { classHighlighter, highlightCode } from "@lezer/highlight";
import { parser } from "@lezer/python";
import type { JSX } from "preact";

export function Highlighted({ code }: { code: string }) {
  const out: JSX.Element[] = [];
  let line: (string | JSX.Element)[] = [];
  highlightCode(
    code,
    parser.parse(code),
    classHighlighter,
    (text, classes) => line.push(classes ? <span class={classes}>{text}</span> : text),
    () => {
      out.push(<>{line}{"\n"}</>);
      line = [];
    },
  );
  if (line.length) out.push(<>{line}</>);
  return <>{out}</>;
}
