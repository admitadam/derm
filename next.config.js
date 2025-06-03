/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Remove basePath when using custom domain
  // basePath: '/derm',
}

module.exports = nextConfig 