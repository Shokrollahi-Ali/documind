import { expect, it } from "vitest";

import { jsonError, readJsonBody } from "./json-request";

function jsonRequest(body: BodyInit | null, contentType = "application/json") {
  return new Request("http://localhost/api/example", {
    method: "POST",
    body,
    headers: { "Content-Type": contentType },
  });
}

function statusOf(result: string | Response): number {
  if (typeof result === "string") throw new Error("Expected a rejection response");
  return result.status;
}

it("returns the raw body when it is valid JSON within the limit", async () => {
  const body = '{"question":"What is the notice period?"}';

  expect(await readJsonBody(jsonRequest(body), 1024)).toBe(body);
});

it("accepts a JSON content type that includes a charset", async () => {
  const result = await readJsonBody(jsonRequest("{}", "application/json; charset=utf-8"), 1024);

  expect(result).toBe("{}");
});

it("accepts a body that is exactly as large as the limit", async () => {
  const body = `{"a":"${"x".repeat(92)}"}`;

  expect(body.length).toBe(100);
  expect(await readJsonBody(jsonRequest(body), 100)).toBe(body);
});

it("rejects other content types with 415", async () => {
  const result = await readJsonBody(jsonRequest("a=b", "application/x-www-form-urlencoded"), 1024);

  expect(statusOf(result)).toBe(415);
});

it("rejects a missing body with 400", async () => {
  expect(statusOf(await readJsonBody(jsonRequest(null), 1024))).toBe(400);
});

it("rejects malformed JSON with 400", async () => {
  expect(statusOf(await readJsonBody(jsonRequest("{"), 1024))).toBe(400);
});

it("rejects a body larger than the limit with 413 even without a content length", async () => {
  const request = jsonRequest(JSON.stringify({ text: "x".repeat(2000) }));

  expect(request.headers.has("content-length")).toBe(false);
  expect(statusOf(await readJsonBody(request, 1024))).toBe(413);
});

it("builds uncached error responses with a detail message", async () => {
  const response = jsonError("Something went wrong.", 502);

  expect(response.status).toBe(502);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(await response.json()).toEqual({ detail: "Something went wrong." });
});
