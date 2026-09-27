import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HISTORY_KEY } from "@/lib/code-typing/history";
import { snippetsFor } from "@/lib/code-typing/snippets";
import { CodeTypingPractice } from "./code-typing-practice";

beforeEach(() => {
  vi.useFakeTimers();
  window.localStorage.clear();
});
afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.useRealTimers();
});

describe("CodeTypingPractice DOM/browser integration", () => {
  it("shows a guest-only static snippet with accessible setup, switching, shuffle and restart", () => {
    render(<CodeTypingPractice />);
    expect(screen.getByRole("heading", { name: /Build fluency/ })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Language" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Type the displayed snippet" })).toHaveValue("");
    expect(screen.getByLabelText("Snippet to type")).toHaveTextContent("indexed_total");
    expect(screen.getByLabelText("Time remaining")).toHaveTextContent("01:00");
    fireEvent.click(screen.getByRole("button", { name: "SQL" }));
    expect(screen.getByLabelText("Snippet to type")).toHaveTextContent("WITH grouped");
    fireEvent.click(screen.getByRole("button", { name: "30s" }));
    expect(screen.getByLabelText("Time remaining")).toHaveTextContent("00:30");
    fireEvent.click(screen.getByRole("button", { name: "Shuffle example" }));
    expect(screen.getByLabelText("Snippet to type")).toHaveTextContent("demo_inventory");
    fireEvent.change(screen.getByRole("textbox", { name: "Type the displayed snippet" }), { target: { value: "S" } });
    expect(screen.getByText("active")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restart" }));
    expect(screen.getByRole("textbox", { name: "Type the displayed snippet" })).toHaveValue("");
    expect(screen.getByText("idle")).toBeInTheDocument();
    expect(screen.getByLabelText("Time remaining")).toHaveTextContent("00:30");
  });

  it("handles Tab indentation, keyboard focus escape via Shift+Tab, and blocks paste/drop", () => {
    render(<CodeTypingPractice />);
    const editor = screen.getByRole("textbox", { name: "Type the displayed snippet" }) as HTMLTextAreaElement;
    editor.focus();
    fireEvent.keyDown(editor, { key: "Tab" });
    expect(editor).toHaveValue("    ");
    fireEvent.keyDown(editor, { key: "Tab", shiftKey: true });
    expect(editor).toHaveValue("    ");
    const paste = new Event("paste", { bubbles: true, cancelable: true });
    const drop = new Event("drop", { bubbles: true, cancelable: true });
    fireEvent(editor, paste);
    fireEvent(editor, drop);
    expect(paste.defaultPrevented).toBe(true);
    expect(drop.defaultPrevented).toBe(true);
  });

  it("starts on first change, persists a single real completion, survives remount, and clears guest history", () => {
    const view = render(<CodeTypingPractice />);
    const editor = screen.getByRole("textbox", { name: "Type the displayed snippet" }) as HTMLTextAreaElement;
    const expected = snippetsFor("python")[0].expectedText;
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    fireEvent.change(editor, { target: { value: expected.slice(0, 1) } });
    act(() => vi.advanceTimersByTime(1000));
    for (let index = 1; index < expected.length; index++) {
      fireEvent.change(editor, { target: { value: expected.slice(0, index + 1) } });
    }
    expect(screen.getByText(/Snippet completed/)).toBeInTheDocument();
    expect(Number(screen.getByLabelText("Net CPM").textContent)).toBeGreaterThan(0);
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(JSON.parse(window.localStorage.getItem(HISTORY_KEY) ?? "{}").entries).toHaveLength(1);
    act(() => vi.advanceTimersByTime(2000));
    expect(JSON.parse(window.localStorage.getItem(HISTORY_KEY) ?? "{}").entries).toHaveLength(1);
    view.unmount();
    render(<CodeTypingPractice />);
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Clear history" }));
    expect(window.localStorage.getItem(HISTORY_KEY)).toBeNull();
    expect(screen.getByText("No finished attempts saved in this browser.")).toBeInTheDocument();
  });

  it("expires unfinished attempts and keeps editor read-only after the deadline", () => {
    render(<CodeTypingPractice />);
    fireEvent.click(screen.getByRole("button", { name: "30s" }));
    const editor = screen.getByRole("textbox", { name: "Type the displayed snippet" }) as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: "d" } });
    act(() => vi.advanceTimersByTime(30_100));
    expect(screen.getByText("Time expired")).toBeInTheDocument();
    expect(editor).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Time remaining")).toHaveTextContent("00:00");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(JSON.parse(window.localStorage.getItem(HISTORY_KEY) ?? "{}").entries[0].status).toBe("timed-out");
  });
});
