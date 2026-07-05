import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable } from "../data-table";
import type { Column } from "../data-table";

interface TestRow {
  id: string;
  name: string;
  value: number;
}

const columns: Column<TestRow>[] = [
  { key: "name", label: "Name", render: (r) => r.name },
  { key: "value", label: "Value", align: "right", sortable: true, render: (r) => r.value },
];

const data: TestRow[] = [
  { id: "1", name: "Alpha", value: 100 },
  { id: "2", name: "Beta", value: 200 },
];

describe("DataTable", () => {
  it("renders column headers", () => {
    render(<DataTable columns={columns} data={data} keyExtractor={(r) => r.id} />);
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
  });

  it("renders data rows", () => {
    render(<DataTable columns={columns} data={data} keyExtractor={(r) => r.id} />);
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("shows empty state when no data", () => {
    render(<DataTable columns={columns} data={[]} keyExtractor={(r) => r.id} />);
    expect(screen.getByText("No data")).toBeInTheDocument();
  });

  it("shows loading skeleton when loading", () => {
    const { container } = render(
      <DataTable columns={columns} data={[]} loading keyExtractor={(r) => r.id} />,
    );
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders pagination when total > limit and onOffsetChange provided", () => {
    render(
      <DataTable
        columns={columns}
        data={data}
        total={50}
        limit={10}
        offset={0}
        onOffsetChange={() => {}}
        keyExtractor={(r) => r.id}
      />,
    );
    expect(screen.getByText("Prev")).toBeInTheDocument();
    expect(screen.getByText("Next")).toBeInTheDocument();
    expect(screen.getByText(/1.*10.*of.*50/)).toBeInTheDocument();
  });
});
