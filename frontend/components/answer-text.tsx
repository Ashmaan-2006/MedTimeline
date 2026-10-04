"use client";

import type { ReactNode } from "react";

const CITATION_PATTERN = /(\[G?\d+\])/g;
// "New medications: ..." style labels get emphasis; long sentences with a colon do not.
const LABEL_PATTERN = /^([A-Z][A-Za-z ()/-]{1,40}):\s+(.+)$/;

type Block =
  | { kind: "heading"; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; items: string[] };

export function citationAnchorId(scope: string, label: string) {
  return `${scope}-citation-${label.replace(/[^A-Za-z0-9]/g, "")}`;
}

function revealCitation(scope: string, label: string) {
  const element = document.getElementById(citationAnchorId(scope, label));
  if (element instanceof HTMLDetailsElement) {
    element.open = true;
  }
  element?.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function toBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }
    if (line.startsWith("- ")) {
      const previous = blocks.at(-1);
      if (previous?.kind === "list") {
        previous.items.push(line.slice(2));
      } else {
        blocks.push({ kind: "list", items: [line.slice(2)] });
      }
    } else if (line.endsWith(":") && line.split(" ").length <= 8) {
      blocks.push({ kind: "heading", text: line.slice(0, -1) });
    } else {
      blocks.push({ kind: "paragraph", text: line });
    }
  }
  return blocks;
}

type AnswerTextProps = {
  text: string;
  scope: string;
  citationLabels?: string[];
  className?: string;
};

export function AnswerText({ text, scope, citationLabels = [], className }: AnswerTextProps) {
  const knownLabels = new Set(citationLabels);

  function renderCitations(value: string): ReactNode[] {
    return value.split(CITATION_PATTERN).map((part, index) =>
      knownLabels.has(part) ? (
        <button
          aria-label={`Show source ${part}`}
          className="citation-link"
          key={index}
          onClick={() => revealCitation(scope, part)}
          type="button"
        >
          {part}
        </button>
      ) : (
        part
      ),
    );
  }

  function renderLine(value: string): ReactNode {
    const match = LABEL_PATTERN.exec(value);
    if (match === null) {
      return renderCitations(value);
    }
    return (
      <>
        <strong>{match[1]}:</strong> {renderCitations(match[2])}
      </>
    );
  }

  return (
    <div className={className ? `answer-text ${className}` : "answer-text"}>
      {toBlocks(text).map((block, index) => {
        if (block.kind === "heading") {
          return (
            <p className="answer-heading" key={index}>
              {block.text}
            </p>
          );
        }
        if (block.kind === "list") {
          return (
            <ul className="answer-list" key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderLine(item)}</li>
              ))}
            </ul>
          );
        }
        return <p key={index}>{renderLine(block.text)}</p>;
      })}
    </div>
  );
}
