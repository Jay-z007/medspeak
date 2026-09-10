import type { NextConfig } from "next";

const rawBackendUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const backendUrl = rawBackendUrl.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
