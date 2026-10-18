import { describe, expect, it } from "vitest";

import { maxDocumentSizeBytes, validateDocumentFile } from "./validate-document-file";

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

  it("accepts the backend size limit and rejects larger files", () => {
    const fileOfSize = (size: number) => {
      const file = new File(["content"], "report.pdf", { type: "application/pdf" });
      Object.defineProperty(file, "size", { value: size });
      return file;
    };
    expect(validateDocumentFile(fileOfSize(maxDocumentSizeBytes))).toBeNull();
    expect(validateDocumentFile(fileOfSize(maxDocumentSizeBytes + 1))).toBe("The PDF must be 20 MB or smaller.");
  });
});
