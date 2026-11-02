export type DocumentAnswerSource = {
  chunk_index: number;
  page_number: number;
  text: string;
};

export type DocumentAnswer = {
  answer: string;
  sources: DocumentAnswerSource[];
};

function isDocumentAnswerSource(value: unknown): value is DocumentAnswerSource {
  if (typeof value !== "object" || value === null) return false;

  const source = value as Record<string, unknown>;

  return (
    Number.isInteger(source.chunk_index) &&
    Number.isInteger(source.page_number) &&
    typeof source.text === "string" && source.text.length > 0
  );
}

export function isDocumentAnswer(value: unknown): value is DocumentAnswer {
  if (typeof value !== "object" || value === null) return false;

  const answer = value as Record<string, unknown>;

  return (
    typeof answer.answer === "string" && answer.answer.length > 0 &&
    Array.isArray(answer.sources) && answer.sources.every(isDocumentAnswerSource)
  );
}
