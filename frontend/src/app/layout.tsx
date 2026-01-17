import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Roman Story',
  description: 'Interactive historical map of Rome',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}
