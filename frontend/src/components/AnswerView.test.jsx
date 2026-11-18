import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnswerView } from "./AnswerView.jsx";

const result = {
  answer: "To fix it:\n\n- Put PgBouncer in front of Postgres [1].\n- Keep `max_connections` at **200** [2].\n\nUnsupported claim [9].",
  sources: [
    { item_id: "a", chunk_index: 0, source_type: "note", title: "Pooling note", url: null, snippet: "PgBouncer in transaction mode.", score: 0.82 },
    { item_id: "b", chunk_index: 3, source_type: "url", title: "Guide", url: "https://example.com/guide", snippet: "Cap the pool at 20.", score: 0.61 },
  ],
};

function setup(props = {}) {
  const onActivateSource = vi.fn();
  render(<AnswerView turnId="t1" result={result} activeSource={null} onActivateSource={onActivateSource} {...props} />);
  return { onActivateSource };
}

describe("AnswerView", () => {
  it("renders lists, code, bold and one chip per valid citation", () => {
    setup();
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("max_connections").tagName).toBe("CODE");
    expect(screen.getByText("200").tagName).toBe("STRONG");
    expect(screen.getByRole("link", { name: "Source 1" })).toHaveAttribute("href", "#source-t1-1");
    expect(screen.getByRole("link", { name: "Source 2" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Source 9" })).not.toBeInTheDocument();
    expect(screen.getByText(/Unsupported claim \[9\]/)).toBeInTheDocument();
  });

  it("lists sources with title, origin, score and per-turn anchors", () => {
    const { container } = render(
      <AnswerView turnId="t2" result={result} activeSource={null} onActivateSource={() => {}} />,
    );
    expect(screen.getAllByRole("heading", { name: "2 sources" })).toHaveLength(1);
    expect(container.querySelector("#source-t2-1")).toHaveTextContent("Pooling note");
    expect(screen.getByRole("link", { name: "Guide" })).toHaveAttribute("href", "https://example.com/guide");
    expect(screen.getByText("82% match")).toBeInTheDocument();
  });

  it("activates the matching source on hover and focus", () => {
    const { onActivateSource } = setup();
    const chip = screen.getByRole("link", { name: "Source 2" });
    fireEvent.mouseEnter(chip);
    expect(onActivateSource).toHaveBeenLastCalledWith(2);
    fireEvent.mouseLeave(chip);
    expect(onActivateSource).toHaveBeenLastCalledWith(null);
    fireEvent.focus(chip);
    expect(onActivateSource).toHaveBeenLastCalledWith(2);
  });

  it("highlights the active source passage", () => {
    setup({ activeSource: 1 });
    expect(screen.getByText("PgBouncer in transaction mode.")).toHaveClass("bg-marker");
    expect(screen.getByText("Cap the pool at 20.")).toHaveClass("bg-transparent");
  });

  it("expands a passage on request", async () => {
    setup();
    const [toggle] = screen.getAllByRole("button", { name: "Show full passage" });
    await userEvent.click(toggle);
    expect(toggle).toHaveTextContent("Show less");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("explains when nothing could be cited", () => {
    render(<AnswerView turnId="t3" result={{ answer: "I couldn't find it.", sources: [] }} activeSource={null} onActivateSource={() => {}} />);
    expect(screen.getByText(/No saved passage matched/)).toBeInTheDocument();
  });

  it("shows small talk as a plain reply with no 'no match' note", () => {
    render(
      <AnswerView turnId="t4" result={{ kind: "small_talk", answer: "Hi! Ask me about your notes.", sources: [] }} activeSource={null} onActivateSource={() => {}} />,
    );
    expect(screen.getByText("Hi! Ask me about your notes.")).toBeInTheDocument();
    expect(screen.queryByText(/No saved passage matched/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Try rephrasing/)).not.toBeInTheDocument();
  });

  it("suggests what to do when the library doesn't cover a question", () => {
    render(
      <AnswerView turnId="t5" result={{ kind: "not_found", answer: "Your saved items don't cover that.", sources: [] }} activeSource={null} onActivateSource={() => {}} />,
    );
    expect(screen.getByText("Try rephrasing, or add a note or link about this in the sidebar.")).toBeInTheDocument();
  });
});
