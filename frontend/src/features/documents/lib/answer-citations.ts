import type { DocumentAnswer, DocumentAnswerSource } from "./document-answer";

export type AnswerText = { kind: "text"; text: string };
export type AnswerCitation = { kind: "citation"; number: number; source: DocumentAnswerSource };
export type AnswerPart = AnswerText | AnswerCitation;

const chunkMarkerPattern = /\[chunk ([0-9]+)\]/;

function getCitationNumber(numbers: Map<number, number>, chunkIndex: number): number {
  const existingNumber = numbers.get(chunkIndex);
  if (existingNumber !== undefined) return existingNumber;

  const newNumber = numbers.size + 1;
  numbers.set(chunkIndex, newNumber);
  return newNumber;
}

export function splitAnswerIntoParts(answer: DocumentAnswer): AnswerPart[] {
  const pieces = answer.answer.split(chunkMarkerPattern);
  const numbers = new Map<number, number>();
  const parts: AnswerPart[] = [];

  pieces.forEach((piece, position) => {
    const isChunkIndex = position % 2 === 1;

    if (!isChunkIndex) {
      if (piece) parts.push({ kind: "text", text: piece });
      return;
    }

    const chunkIndex = Number(piece);
    const source = answer.sources.find((candidate) => candidate.chunk_index === chunkIndex);
    if (!source) return;

    parts.push({ kind: "citation", number: getCitationNumber(numbers, chunkIndex), source });
  });

  return parts;
}

export function listCitations(parts: AnswerPart[]): AnswerCitation[] {
  const citations: AnswerCitation[] = [];

  for (const part of parts) {
    if (part.kind !== "citation") continue;

    const alreadyListed = citations.some((citation) => citation.number === part.number);
    if (!alreadyListed) citations.push(part);
  }

  return citations;
}
