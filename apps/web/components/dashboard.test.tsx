import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Dashboard } from "./dashboard";
import { QueryProvider } from "./query-provider";
import { AuthProvider } from "@/lib/auth";

describe("Dashboard", () => {
  it("separates hosted publication from unbounded growth", () => {
    render(
      <QueryProvider>
        <AuthProvider>
          <Dashboard />
        </AuthProvider>
      </QueryProvider>,
    );
    expect(screen.getByText("PUBLISHED HOSTED QUESTIONS")).toBeInTheDocument();
    expect(
      screen.getByText(/no final question-count ceiling/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /hosted questions and external references are counted separately/i,
      ),
    ).toBeInTheDocument();
  });
});
