import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@followville/company-os-core"],
  poweredByHeader: false,
  // The core package uses ESM-style `./module.js` specifiers that resolve to
  // TypeScript sources; webpack needs the alias, and Turbopack needs the
  // matching resolveAlias-free extension handling below.
  webpack: (config) => {
    config.resolve.extensionAlias = {
      ".js": [".ts", ".tsx", ".js"],
    };
    return config;
  },
  turbopack: {
    resolveExtensions: [".tsx", ".ts", ".jsx", ".js", ".mjs", ".json"],
  },
};

export default nextConfig;
