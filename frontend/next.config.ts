import type { NextConfig } from "next";

const API_PROXY = process.env.API_PROXY_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_PROXY}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
