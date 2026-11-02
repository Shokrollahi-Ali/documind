import { expect, it } from "vitest";

import { formatFileSize } from "./format-file-size";

it.each([1, 128, 9_999])("shows %i bytes as under one hundredth of a megabyte", (sizeBytes) => {
  expect(formatFileSize(sizeBytes)).toBe("< 0.01 MB");
});

it.each([
  [10_000, "0.01 MB"],
  [1_200_000, "1.2 MB"],
  [1_234_567, "1.23 MB"],
  [20_971_520, "20.97 MB"],
])("shows %i bytes as %s", (sizeBytes, expected) => {
  expect(formatFileSize(sizeBytes)).toBe(expected);
});
