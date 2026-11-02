import { expect, it } from "vitest";

import { documentsPath, getDocumentAnswerPath, getDocumentPath } from "./document-routes";

const documentId = "fdc6e6a9-4585-477e-b53a-2576edb7a0e1";

it("points to the documents collection", () => {
  expect(documentsPath).toBe("/api/documents");
});

it("builds the path of one document", () => {
  expect(getDocumentPath(documentId)).toBe(`/api/documents/${documentId}`);
});

it("encodes characters that are unsafe in a path", () => {
  expect(getDocumentPath("a/b")).toBe("/api/documents/a%2Fb");
});

it("builds the path for asking a question about one document", () => {
  expect(getDocumentAnswerPath(documentId)).toBe(`/api/documents/${documentId}/answer`);
});
