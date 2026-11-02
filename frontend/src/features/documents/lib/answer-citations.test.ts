import { expect, it } from "vitest";

import { listCitations, splitAnswerIntoParts } from "./answer-citations";

function createSource(chunkIndex: number, pageNumber: number) {
  return { chunk_index: chunkIndex, page_number: pageNumber, text: `Passage ${chunkIndex}` };
}

it("replaces each chunk marker with a numbered citation", () => {
  const noticeSource = createSource(3, 4);
  const emailSource = createSource(8, 7);
  const answer = {
    answer: "Give 60 days notice [chunk 3]. Email must be confirmed [chunk 8].",
    sources: [noticeSource, emailSource],
  };

  expect(splitAnswerIntoParts(answer)).toEqual([
    { kind: "text", text: "Give 60 days notice " },
    { kind: "citation", number: 1, source: noticeSource },
    { kind: "text", text: ". Email must be confirmed " },
    { kind: "citation", number: 2, source: emailSource },
    { kind: "text", text: "." },
  ]);
});

it("numbers citations in the order they appear in the answer", () => {
  const firstSource = createSource(3, 4);
  const secondSource = createSource(8, 7);
  const answer = { answer: "A [chunk 8] B [chunk 3].", sources: [firstSource, secondSource] };

  const citations = listCitations(splitAnswerIntoParts(answer));

  expect(citations.map((citation) => [citation.number, citation.source.chunk_index])).toEqual([
    [1, 8],
    [2, 3],
  ]);
});

it("reuses the same number when a chunk is cited twice", () => {
  const source = createSource(2, 5);
  const answer = { answer: "A [chunk 2] B [chunk 2].", sources: [source] };

  const parts = splitAnswerIntoParts(answer);

  expect(parts).toEqual([
    { kind: "text", text: "A " },
    { kind: "citation", number: 1, source },
    { kind: "text", text: " B " },
    { kind: "citation", number: 1, source },
    { kind: "text", text: "." },
  ]);
  expect(listCitations(parts)).toHaveLength(1);
});

it("drops a marker that has no matching source", () => {
  const answer = { answer: "A [chunk 9] B", sources: [] };

  expect(splitAnswerIntoParts(answer)).toEqual([
    { kind: "text", text: "A " },
    { kind: "text", text: " B" },
  ]);
});

it("returns the whole answer as text when it has no markers", () => {
  const answer = { answer: "No sources here.", sources: [] };

  expect(splitAnswerIntoParts(answer)).toEqual([{ kind: "text", text: "No sources here." }]);
});
