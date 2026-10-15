import { describe, expect, it } from "vitest";

import { validateDocumentFile } from "./validate-document-file";

describe("PDF metadata validation", () => {
  it("allows an absent MIME type because browsers do not always provide one", () => {
    expect(validateDocumentFile(new File(["content"], "report.pdf"))).toBeNull();
  });

  it("rejects a conflicting MIME type even with a PDF extension", () => {
    const file = new File(["content"], "report.pdf", { type: "text/plain" });
    expect(validateDocumentFile(file)).toBe("The selected file must have a PDF content type.");
  });

  it("accepts the backend filename length boundary and rejects longer names", () => {
    expect(validateDocumentFile(new File(["content"], `${"a".repeat(251)}.pdf`))).toBeNull();
    expect(validateDocumentFile(new File(["content"], `${"a".repeat(252)}.pdf`))).toBe("The filename must not exceed 255 characters.");
  });

  it("counts Unicode code points consistently with backend filename validation", () => {
    expect(validateDocumentFile(new File(["content"], `${"😀".repeat(251)}.pdf`))).toBeNull();
  });
});
