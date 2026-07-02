"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface WalletAddressProps {
  address: string;
  link?: boolean;
  className?: string;
}

export function WalletAddress({ address, link = true, className }: WalletAddressProps) {
  const [copied, setCopied] = useState(false);

  const truncated = `${address.slice(0, 6)}...${address.slice(-4)}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(address).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const content = (
    <span
      onClick={handleCopy}
      className={cn(
        "font-mono text-sm cursor-pointer text-text-secondary hover:text-accent-amber transition-colors",
        link && "hover:underline underline-offset-2 decoration-accent-amber/50",
        className,
      )}
      title="Click to copy"
    >
      {truncated}
      {copied && <span className="ml-1 text-accent-amber text-xs">copied</span>}
    </span>
  );

  if (link) {
    return <Link href={`/wallets/${address}`}>{content}</Link>;
  }

  return content;
}
