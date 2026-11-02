const bytesPerMegabyte = 1_000_000;
const smallestShownBytes = 10_000;
const megabyteFormat = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });

export function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < smallestShownBytes) return "< 0.01 MB";

  return `${megabyteFormat.format(sizeBytes / bytesPerMegabyte)} MB`;
}
