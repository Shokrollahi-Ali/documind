import { afterEach, expect, it, vi } from "vitest";

import { getAnswerTimeoutMs, getApiTimeoutMs } from "./api-configuration";

afterEach(() => vi.unstubAllEnvs());

it("uses a longer default timeout for answers than for other requests", () => {
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", undefined);
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", undefined);

  expect(getApiTimeoutMs()).toBe(10000);
  expect(getAnswerTimeoutMs()).toBe(100000);
});

it("reads each timeout from its own setting", () => {
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", "2000");
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", "90000");

  expect(getApiTimeoutMs()).toBe(2000);
  expect(getAnswerTimeoutMs()).toBe(90000);
});

it.each(["0", "NaN", "1.5", "2147483648"])("rejects the invalid answer timeout %s", (timeout) => {
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", timeout);

  expect(() => getAnswerTimeoutMs()).toThrow("Invalid DOCUMIND_ANSWER_TIMEOUT_MS");
});
