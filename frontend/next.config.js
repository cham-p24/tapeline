/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },

  // Production-grade security headers — same set Vercel + Linear ship.
  // CSP is intentionally NOT set yet because TradingView's embed + Cloudflare
  // Turnstile + the API rewrite all need an audit before we can pin hashes.
  // The headers below are safe to ship today and close the easy attack vectors.
  async headers() {
    const securityHeaders = [
      // Force HTTPS for 2 years; opt browsers in to the HSTS preload list.
      { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
      // Block clickjacking — no third party can iframe Tapeline.
      { key: "X-Frame-Options", value: "DENY" },
      // Stop browsers from MIME-sniffing responses into the wrong type.
      { key: "X-Content-Type-Options", value: "nosniff" },
      // Don't leak referrers to other origins.
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      // Disallow access to powerful APIs we don't use.
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
      },
      // Older XSS protection — modern browsers ignore but legacy ones still
      // honour it; cost is zero.
      { key: "X-XSS-Protection", value: "1; mode=block" },
    ];
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

module.exports = nextConfig;
