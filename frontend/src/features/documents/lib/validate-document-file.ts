export function validateDocumentFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    return "Choose a PDF document.";
  }

  if (Array.from(file.name).length > 255) {
    return "The filename must not exceed 255 characters.";
  }

  if (file.type && file.type !== "application/pdf") {
    return "The selected file must have a PDF content type.";
  }

  if (file.size === 0) {
    return "The selected document is empty. Choose a PDF with content.";
  }

  return null;
}
