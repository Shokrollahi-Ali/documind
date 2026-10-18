"use client";

import { useId, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import Button from "@/components/button";
import { uploadDocument } from "../api/upload-document";
import { validateDocumentFile } from "../lib/validate-document-file";

export default function DocumentUpload({ onUploaded }: { onUploaded?: () => void }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const uploadInProgress = useRef(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSucceeded, setUploadSucceeded] = useState(false);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;

    setUploadSucceeded(false);
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || uploadInProgress.current) return;

    uploadInProgress.current = true;
    setIsUploading(true);
    setError(null);
    setUploadSucceeded(false);
    try {
      await uploadDocument(selectedFile);

      setUploadSucceeded(true);
      onUploaded?.();
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "The upload failed.");
    } finally {
      uploadInProgress.current = false;
      setIsUploading(false);
    }
  }

  let statusMessage = "No document selected.";
  if (isUploading) {
    statusMessage = "Uploading your document…";
  } else if (uploadSucceeded) {
    statusMessage = "Your document was uploaded successfully.";
  } else if (selectedFile) {
    statusMessage = `Selected: ${selectedFile.name}`;
  }

  return (
    <>
      <section
        aria-labelledby={`${inputId}-heading`}
        className="mt-8 rounded-xl border border-zinc-200 p-6 sm:p-8 dark:border-zinc-800"
      >
        <h2 id={`${inputId}-heading`} className="text-xl font-semibold">
          Upload a document
        </h2>
        <p id={`${inputId}-help`} className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Choose one PDF up to 20 MB. Password-protected PDFs are not supported.
        </p>

        <form onSubmit={handleSubmit} aria-busy={isUploading}>
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
            disabled={isUploading}
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
            {statusMessage}
          </p>

          {selectedFile && (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-lg bg-zinc-100 p-4 dark:bg-zinc-900">
              <dl className="text-sm">
                <dt className="text-zinc-600 dark:text-zinc-400">File size</dt>
                <dd className="mt-1 font-medium">
                  {new Intl.NumberFormat("en").format(selectedFile.size)} bytes
                </dd>
              </dl>
              <Button onClick={removeSelectedFile} disabled={isUploading}>
                Remove selection
              </Button>
            </div>
          )}
          <Button type="submit" variant="primary" disabled={!selectedFile || isUploading} className="mt-6">
            {isUploading ? "Uploading…" : "Upload document"}
          </Button>
        </form>
      </section>
    </>
  );
}
