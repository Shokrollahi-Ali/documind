"use client";

import { useId, useRef, useState } from "react";
import type { ChangeEvent } from "react";

import { validateDocumentFile } from "../lib/validate-document-file";

export default function DocumentSelection() {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;

    const validationError = validateDocumentFile(file);
    setError(validationError);
    setSelectedFile(validationError ? null : file);

    if (validationError) {
      event.currentTarget.value = "";
    }
  }

  function removeSelectedFile() {
    setSelectedFile(null);
    setError(null);
    if (inputRef.current) {
      inputRef.current.value = "";
      inputRef.current.focus();
    }
  }

  return (
    <section
      aria-labelledby={`${inputId}-heading`}
      className="mt-8 rounded-xl border border-zinc-200 p-6 sm:p-8 dark:border-zinc-800"
    >
      <h2 id={`${inputId}-heading`} className="text-xl font-semibold">
        Select a document
      </h2>
      <p id={`${inputId}-help`} className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
        Choose one PDF. Your file stays on your device until uploading is available.
      </p>

      <label htmlFor={inputId} className="mt-6 block text-sm font-medium">
        PDF document
      </label>
      <input
        ref={inputRef}
        id={inputId}
        name="file"
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleFileChange}
        aria-invalid={Boolean(error)}
        aria-describedby={`${inputId}-help${error ? ` ${inputId}-error` : ""}`}
        className="mt-2 block w-full rounded-lg border border-zinc-300 p-3 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-zinc-100 file:px-4 file:py-2 file:font-medium file:text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-zinc-700"
      />

      {error && (
        <p id={`${inputId}-error`} role="alert" className="mt-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}

      <p role="status" className="mt-4 break-words text-sm text-zinc-600 dark:text-zinc-400">
        {selectedFile ? `Selected: ${selectedFile.name}` : "No document selected."}
      </p>

      {selectedFile && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-lg bg-zinc-100 p-4 dark:bg-zinc-900">
          <dl className="text-sm">
            <dt className="text-zinc-600 dark:text-zinc-400">File size</dt>
            <dd className="mt-1 font-medium">
              {new Intl.NumberFormat("en").format(selectedFile.size)} bytes
            </dd>
          </dl>
          <button
            type="button"
            onClick={removeSelectedFile}
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            Remove selection
          </button>
        </div>
      )}
    </section>
  );
}
