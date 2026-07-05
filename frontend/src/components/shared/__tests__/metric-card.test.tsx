import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../metric-card";

describe("MetricCard", () => {
  it("renders label and value", () => {
    render(<MetricCard label="ROI" value="12.5%" />);
    expect(screen.getByText("ROI")).toBeInTheDocument();
    expect(screen.getByText("12.5%")).toBeInTheDocument();
  });

  it("shows positive change with sign", () => {
    render(<MetricCard label="PnL" value="$100" change={5.2} trend="up" />);
    expect(screen.getByText("+5.2%")).toBeInTheDocument();
  });

  it("renders loading skeleton when loading", () => {
    const { container } = render(<MetricCard label="ROI" value="-" loading />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders ReactNode value", () => {
    render(<MetricCard label="Balance" value={<span data-testid="custom">$1,000</span>} />);
    expect(screen.getByTestId("custom")).toBeInTheDocument();
  });
});
