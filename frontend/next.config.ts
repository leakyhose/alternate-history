import type { NextConfig } from 'next'
import path from 'path'

const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, './'),
  // Enable static file serving from public folder
  images: {
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.vercel.app',
      },
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
  // Increase timeout for long-running API requests
  httpAgentOptions: {
    keepAlive: true,
  },
  // Proxy API requests to backend for cors
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
      // Game/workflow endpoints - these go through proxy
      // For long-running requests, frontend will call backend directly
      {
        source: '/start',
        destination: `${backendUrl}/start`,
      },
      {
        source: '/continue/:path*',
        destination: `${backendUrl}/continue/:path*`,
      },
      {
        source: '/game/:path*',
        destination: `${backendUrl}/game/:path*`,
      },
      {
        source: '/games',
        destination: `${backendUrl}/games`,
      },
    ]
  },
}

export default nextConfig
