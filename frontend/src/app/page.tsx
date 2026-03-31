'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'

// Backend URL for API calls - strip trailing slash to avoid double-slash issues
const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

interface Scenario {
  id: string
  name: string
  period?: { start: number; end: number }
}

export default function Home() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const url = `${BACKEND_URL}/scenarios`
    console.log('📋 Fetching scenarios from:', url)
    fetch(url)
      .then(res => res.json())
      .then(data => {
        setScenarios(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to load scenarios:', err)
        setLoading(false)
      })
  }, [])

  return (
    <div className="scanlines h-screen flex flex-col items-center justify-center bg-black px-8 py-6 overflow-hidden select-none">
      {/* Hero Section */}
      <div className="flex flex-col items-center mb-6 shrink-0">
        <Image
          src="/logo.png"
          alt="Divergence Logo"
          width={140}
          height={140}
          className="mb-3"
          style={{ imageRendering: 'pixelated' }}
          priority
        />
        <h1
          className="text-7xl lg:text-9xl font-bold tracking-wider"
          style={{
            color: 'var(--color-pixel-amber)',
            textShadow: '0 0 40px rgba(244, 160, 32, 0.3)',
          }}
        >
          DIVERGENCE
        </h1>
        <p className="text-amber-400/50 text-lg tracking-[0.3em] uppercase mt-2">
          Alternate History Simulator
        </p>
        <div className="text-gray-600 text-sm tracking-wide mt-1">v0.1.0</div>
      </div>

      {/* Divider */}
      <div className="w-full max-w-2xl mx-auto mb-6 flex items-center gap-4 shrink-0">
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-amber-400/30 to-transparent" />
        <div className="text-amber-400/40 text-xs tracking-[0.5em] uppercase">Select Scenario</div>
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-amber-400/30 to-transparent" />
      </div>

      {/* Scenarios List */}
      {loading ? (
        <div className="flex items-center gap-3 text-amber-400/60">
          <div className="w-2 h-2 bg-amber-400/60 animate-pulse" />
          <span className="text-lg tracking-wide">Loading scenarios...</span>
        </div>
      ) : scenarios.length === 0 ? (
        <p className="text-gray-500 text-lg">No scenarios available</p>
      ) : (
        <div className="max-w-2xl w-full grid grid-cols-1 gap-3 min-h-0 overflow-hidden">
          {scenarios.map(scenario => (
            <Link
              key={scenario.id}
              href={`/scenario/${scenario.id}`}
              className="group relative flex items-center gap-5 p-4
                         bg-[#0a0a14] border border-amber-400/20
                         hover:border-amber-400/80 hover:bg-[#0f0f1a]
                         transition-all duration-300
                         hover:shadow-[0_0_20px_rgba(244,160,32,0.1)]"
            >
              <div className="w-16 h-16 relative overflow-hidden border border-amber-400/20
                              group-hover:border-amber-400/40 transition-colors flex-shrink-0">
                <Image
                  src={`${BACKEND_URL}/scenarios/${scenario.id}/logo`}
                  alt={`${scenario.name} logo`}
                  fill
                  className="object-contain p-1"
                  style={{ imageRendering: 'pixelated' }}
                  onError={(e) => {
                    const target = e.target as HTMLImageElement
                    target.style.display = 'none'
                  }}
                />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <h2
                    className="text-2xl font-bold text-gray-300 group-hover:text-amber-400
                               transition-colors tracking-wide"
                  >
                    {scenario.name}
                  </h2>
                  {scenario.id === 'currentday' && (
                    <span className="px-2 py-0.5 text-xs tracking-wider uppercase
                                     border border-amber-400/60 text-amber-400/80
                                     bg-amber-400/5 animate-pulse">
                      Experimental
                    </span>
                  )}
                </div>
                {scenario.period && (
                  <p className="text-gray-600 text-sm mt-1 tracking-wide">
                    {scenario.period.start} &mdash; {scenario.period.end}
                  </p>
                )}
              </div>
              <div className="text-gray-700 group-hover:text-amber-400/60 transition-colors text-2xl">
                &#8250;
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
