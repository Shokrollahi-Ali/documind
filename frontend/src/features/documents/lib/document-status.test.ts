import { expect, it } from "vitest";

import {
  documentStageLabels,
  documentStatuses,
  getDocumentStage,
  isDocumentStatus,
} from "./document-status";

it.each(["uploaded", "processing", "extracted", "chunked"] as const)(
  "treats %s as still preparing",
  (status) => {
    expect(getDocumentStage(status)).toBe("preparing");
  },
);

it("treats ready and failed as final stages", () => {
  expect(getDocumentStage("ready")).toBe("ready");
  expect(getDocumentStage("failed")).toBe("failed");
});

it("recognises every status the backend can report", () => {
  expect(documentStatuses.every(isDocumentStatus)).toBe(true);
});

it.each(["done", "", null, 3])("rejects the unknown status %s", (value) => {
  expect(isDocumentStatus(value)).toBe(false);
});

it("labels every stage in plain language", () => {
  expect(documentStageLabels).toEqual({
    preparing: "Preparing…",
    ready: "Ready to ask",
    failed: "Couldn’t process",
  });
});
