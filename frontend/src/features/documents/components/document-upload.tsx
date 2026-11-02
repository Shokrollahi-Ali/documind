"use client";

import { useRef, useState } from "react";
import type { ChangeEvent } from "react";

import Button from "@/components/button";
import { UploadIcon } from "@/components/icons";
import { SessionExpiredError } from "@/lib/client/session-expired";
import { uploadDocument } from "../api/upload-document";
import { validateDocumentFile } from "../lib/validate-document-file";

const pdfFileTypes = ".pdf,application/pdf";

export default function DocumentUpload({ onUploaded, onSessionExpired }: {
  onUploaded?: () => void;
  onSessionExpired?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function openFilePicker() {
    inputRef.current?.click();
  }

  async function sendFile(file: File) {
    setIsUploading(true);
    try {
      await uploadDocument(file);
      onUploaded?.();
    } catch (uploadError) {
      if (uploadError instanceof SessionExpiredError) onSessionExpired?.();
      setError(uploadError instanceof Error ? uploadError.message : "The upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;

    setError(null);
    const validationError = validateDocumentFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    await sendFile(file);
  }

  return (
    <div className="mt-6">
      <input
        ref={inputRef}
        type="file"
        accept={pdfFileTypes}
        aria-label="PDF document"
        onChange={handleFileChange}
        disabled={isUploading}
        hidden
      />
      <Button variant="primary" onClick={openFilePicker} disabled={isUploading}>
        <UploadIcon />
        {isUploading ? "Uploading…" : "Upload"}
      </Button>
      {isUploading && <p role="status" className="sr-only">Uploading your document…</p>}
      {error && <p role="alert" className="mt-2 text-xs text-red-700 dark:text-red-400">{error}</p>}
    </div>
  );
}
