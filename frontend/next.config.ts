import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, './'),
  // Enable static file serving from public folder
  images: {
    unoptimized: true,
  },
}

export default nextConfig
