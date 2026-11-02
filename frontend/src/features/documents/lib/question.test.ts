import { expect, it } from "vitest";

import { countQuestionCharacters, formatQuestionCounter, maxQuestionLength, validateQuestion } from "./question";

it.each(["", "   ", "\n\t"])("asks for a question when the text is empty or only spaces", (question) => {
  expect(validateQuestion(question)).toBe("Enter a question first.");
});

it("accepts an ordinary question", () => {
  expect(validateQuestion("What is the notice period?")).toBeNull();
});

it("accepts a question that is exactly as long as the limit", () => {
  expect(validateQuestion("a".repeat(maxQuestionLength))).toBeNull();
});

it("rejects a question that is one character too long", () => {
  expect(validateQuestion("a".repeat(maxQuestionLength + 1))).toBe(
    "Questions can be at most 2,000 characters.",
  );
});

it("ignores spaces around the question when checking the limit", () => {
  expect(validateQuestion(` ${"a".repeat(maxQuestionLength)} `)).toBeNull();
});

it("counts an emoji as one character, like the backend does", () => {
  expect(countQuestionCharacters("😀")).toBe(1);
  expect(validateQuestion("😀".repeat(maxQuestionLength))).toBeNull();
});

it("shows how much of the limit has been used", () => {
  expect(formatQuestionCounter("")).toBe("0 / 2,000");
  expect(formatQuestionCounter("a".repeat(1234))).toBe("1,234 / 2,000");
});
