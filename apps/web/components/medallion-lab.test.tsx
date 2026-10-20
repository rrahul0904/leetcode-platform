import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MedallionLab } from "./medallion-lab";
import { SAMPLE_ORDERS } from "@/lib/medallion-lab";

describe("MedallionLab", () => {
  it("lets a learner fix quarantined data and rerun the pipeline", () => {
    render(<MedallionLab />);
    expect(screen.getByText(/1 quarantined row/i)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: /editable order events/i }), {
      target: { value: SAMPLE_ORDERS.replace("PEN,-1,2.00", "PEN,1,2.00") },
    });
    expect(screen.getByText(/Input changed/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /run pipeline/i }));
    expect(screen.getByText(/Quality gate passed/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "silver" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("arr-04");
    fireEvent.click(screen.getByRole("button", { name: /reset sample/i }));
    expect(screen.getByText(/1 quarantined row/i)).toBeInTheDocument();
  });
});