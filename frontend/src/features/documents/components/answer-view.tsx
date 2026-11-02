"use client";

import { useState } from "react";

import Button from "@/components/button";
import { listCitations, splitAnswerIntoParts } from "../lib/answer-citations";
import type { DocumentAnswer } from "../lib/document-answer";
import CitationButton from "./citation-button";
import SourcePassage from "./source-passage";

function getSourcesButtonLabel(sourceCount: number, allSourcesOpen: boolean): string {
  if (allSourcesOpen) return "Hide sources";

  return `Show ${sourceCount} ${sourceCount === 1 ? "source" : "sources"}`;
}

export default function AnswerView({ answer }: { answer: DocumentAnswer }) {
  const parts = splitAnswerIntoParts(answer);
  const citations = listCitations(parts);
  const [openNumbers, setOpenNumbers] = useState<number[]>([]);

  const allSourcesOpen = citations.length > 0 && openNumbers.length === citations.length;
  const openCitations = citations.filter((citation) => openNumbers.includes(citation.number));

  function toggleSource(number: number) {
    setOpenNumbers((currentNumbers) =>
      currentNumbers.includes(number)
        ? currentNumbers.filter((currentNumber) => currentNumber !== number)
        : [...currentNumbers, number],
    );
  }

  function toggleAllSources() {
    setOpenNumbers(allSourcesOpen ? [] : citations.map((citation) => citation.number));
  }

  return (
    <div>
      <p className="text-sm leading-6 wrap-break-word">
        {parts.map((part, index) =>
          part.kind === "text" ? (
            <span key={index}>{part.text}</span>
          ) : (
            <CitationButton
              key={index}
              number={part.number}
              isOpen={openNumbers.includes(part.number)}
              onClick={() => toggleSource(part.number)}
            />
          ),
        )}
      </p>
      {openCitations.map((citation) => (
        <SourcePassage key={citation.number} number={citation.number} source={citation.source} />
      ))}
      {citations.length > 0 && (
        <Button size="sm" className="mt-2" onClick={toggleAllSources}>
          {getSourcesButtonLabel(citations.length, allSourcesOpen)}
        </Button>
      )}
    </div>
  );
}
