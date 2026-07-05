import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WalletAddress } from "../wallet-address";

describe("WalletAddress", () => {
  it("renders truncated address with copy", () => {
    render(<WalletAddress address="0x1234567890abcdef1234567890abcdef12345678" />);
    // slice(0,6)=0x1234 + ... + slice(-4)=5678
    expect(screen.getByText("0x1234...5678")).toBeInTheDocument();
  });

  it("renders link with correct href", () => {
    render(<WalletAddress address="0x1234567890abcdef1234567890abcdef12345678" />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/wallets/0x1234567890abcdef1234567890abcdef12345678");
  });
});
