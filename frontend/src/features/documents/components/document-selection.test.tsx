import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import DocumentSelection from "./document-selection";

function createPdf(name = "report.pdf") {
  return new File(["PDF content"], name, { type: "application/pdf" });
}

describe("document selection", () => {
  it("starts with a labelled file picker and no selected document", () => {
    render(<DocumentSelection />);

    expect(screen.getByLabelText("PDF document")).toHaveAttribute("accept", ".pdf,application/pdf");
    expect(screen.getByRole("status")).toHaveTextContent("No document selected.");
    expect(screen.queryByRole("button", { name: "Remove selection" })).not.toBeInTheDocument();
  });

  it("shows the selected filename and size and allows replacing it", async () => {
    const user = userEvent.setup();
    render(<DocumentSelection />);
    const input = screen.getByLabelText("PDF document");

    await user.upload(input, createPdf());
    expect(screen.getByRole("status")).toHaveTextContent("Selected: report.pdf");
    expect(screen.getByText("11 bytes")).toBeInTheDocument();

    await user.upload(input, createPdf("replacement.PDF"));
    expect(screen.getByRole("status")).toHaveTextContent("Selected: replacement.PDF");
    expect(screen.queryByText("Selected: report.pdf")).not.toBeInTheDocument();
  });

  it("clears the input, restores focus, and allows selecting the same file again", async () => {
    const user = userEvent.setup();
    render(<DocumentSelection />);
    const input = screen.getByLabelText("PDF document");
    const file = createPdf();

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "Remove selection" }));

    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("No document selected.");

    await user.upload(input, file);
    expect(screen.getByRole("status")).toHaveTextContent("Selected: report.pdf");
  });

  it("rejects invalid selections and recovers when a valid PDF is selected", async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(<DocumentSelection />);
    const input = screen.getByLabelText("PDF document");

    await user.upload(input, createPdf());
    await user.upload(input, new File(["text"], "notes.txt", { type: "text/plain" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF document.");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent("No document selected.");

    await user.upload(input, createPdf());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "false");
  });

  it("rejects an empty PDF", async () => {
    const user = userEvent.setup();
    render(<DocumentSelection />);

    await user.upload(screen.getByLabelText("PDF document"), new File([], "empty.pdf", { type: "application/pdf" }));

    expect(screen.getByRole("alert")).toHaveTextContent("The selected document is empty.");
    expect(screen.queryByRole("button", { name: "Remove selection" })).not.toBeInTheDocument();
  });
});
