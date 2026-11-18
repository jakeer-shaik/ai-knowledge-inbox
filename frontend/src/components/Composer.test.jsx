import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client.js";
import { Composer } from "./Composer.jsx";

function setup(onSave = vi.fn().mockResolvedValue({})) {
  render(<Composer onSave={onSave} />);
  return { user: userEvent.setup(), onSave };
}

const noteBox = () => screen.getByRole("textbox", { name: "Note" });
const linkBox = () => screen.getByRole("textbox", { name: "Page link" });

describe("Composer", () => {
  it("starts in note mode", () => {
    setup();
    expect(screen.getByRole("radio", { name: "Note" })).toBeChecked();
    expect(noteBox()).toHaveAttribute("placeholder", "Write or paste your note");
    expect(screen.getByRole("button", { name: "Save note" })).toBeEnabled();
  });

  it("shows an error on submit when empty, and never calls the API", async () => {
    const { user, onSave } = setup();
    await user.click(screen.getByRole("button", { name: "Save note" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Write something to save.");
    expect(noteBox()).toHaveAttribute("aria-invalid", "true");
    expect(onSave).not.toHaveBeenCalled();
  });

  it("does not show errors while typing, and clears an error on the first keystroke", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Save note" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await user.type(noteBox(), "a");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(noteBox()).not.toHaveAttribute("aria-invalid");
  });

  it("does not complain when an untouched field loses focus", async () => {
    const { user } = setup();
    await user.click(noteBox());
    await user.tab();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("saves a trimmed note, clears the box and confirms", async () => {
    const { user, onSave } = setup();
    await user.type(noteBox(), "  PgBouncer fixes connection limits  ");
    await user.click(screen.getByRole("button", { name: "Save note" }));

    expect(onSave).toHaveBeenCalledWith({ type: "note", content: "PgBouncer fixes connection limits" });
    expect(noteBox()).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent("Note saved");
  });

  it("switches to link mode with its own field and button", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("radio", { name: "Link" }));

    expect(linkBox()).toHaveAttribute("placeholder", "https://example.com/article");
    expect(screen.getByRole("button", { name: "Save link" })).toBeInTheDocument();
  });

  it("validates links and sends normalized URLs", async () => {
    const { user, onSave } = setup();
    await user.click(screen.getByRole("radio", { name: "Link" }));

    await user.type(linkBox(), "notalink");
    await user.click(screen.getByRole("button", { name: "Save link" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the full link, starting with https://");
    expect(onSave).not.toHaveBeenCalled();

    await user.clear(linkBox());
    await user.type(linkBox(), "www.example.com/post");
    await user.click(screen.getByRole("button", { name: "Save link" }));
    expect(onSave).toHaveBeenCalledWith({ type: "url", url: "https://www.example.com/post" });
  });

  it("keeps each draft when switching modes", async () => {
    const { user } = setup();
    await user.type(noteBox(), "half-written note");
    await user.click(screen.getByRole("radio", { name: "Link" }));
    await user.type(linkBox(), "https://a.com");
    await user.click(screen.getByRole("radio", { name: "Note" }));

    expect(noteBox()).toHaveValue("half-written note");
  });

  it("shows server validation errors on the field", async () => {
    const onSave = vi.fn().mockRejectedValue(
      new ApiError("Request validation failed", {
        status: 422,
        details: [{ field: "url", message: "url must be an absolute http(s) link" }],
      }),
    );
    const { user } = setup(onSave);
    await user.click(screen.getByRole("radio", { name: "Link" }));
    await user.type(linkBox(), "https://example.com");
    await user.click(screen.getByRole("button", { name: "Save link" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("url must be an absolute http(s) link");
  });

  it("shows other server errors without losing the draft", async () => {
    const onSave = vi.fn().mockRejectedValue(new ApiError("Can't reach the server.", { code: "NETWORK_ERROR" }));
    const { user } = setup(onSave);
    await user.type(noteBox(), "keep me");
    await user.click(screen.getByRole("button", { name: "Save note" }));

    expect(await screen.findByText("Couldn't save: Can't reach the server.")).toBeInTheDocument();
    expect(noteBox()).toHaveValue("keep me");
  });
});
