'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'

// Backend URL for API calls - strip trailing slash to avoid double-slash issues
const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

interface Scenario {
  id: string
  name: string
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
    <div className="min-h-screen flex bg-black">
      {/* Left Side - Large Logo */}
      <div className="w-1/2 flex items-center justify-center p-8">
        <Image
          src="/logo.png"
          alt="Divergence Logo"
          width={600}
          height={600}
          className="max-w-full max-h-[85vh]"
          style={{ imageRendering: 'pixelated' }}
          priority
        />
      </div>

      {/* Right Side - Title and Scenarios */}
      <div className="w-1/2 flex flex-col justify-center p-8">
        {/* Title */}
        <div className="mb-12">
          <h1 
            className="text-9xl font-bold tracking-wider mb-2"
            style={{ color: 'var(--color-pixel-amber)' }}
          >
            DIVERGENCE
          </h1>
          <p className="text-gray-500 text-lg tracking-wide">Select a scenario to begin</p>
        </div>

        {/* Scenarios List */}
        {loading ? (
          <div className="text-amber-400 text-xl animate-pulse">Loading scenarios...</div>
        ) : scenarios.length === 0 ? (
          <p className="text-gray-500 text-lg">No scenarios available</p>
        ) : (
          <div className="flex flex-col gap-4">
            {scenarios.map(scenario => (
              <Link
                key={scenario.id}
                href={`/scenario/${scenario.id}`}
                className="group flex items-center gap-4 p-4 bg-[#0a0a14] border-2 border-[#2a2a3a] 
                           hover:border-amber-400 transition-all duration-200 hover:bg-[#12121c]"
              >
                <div className="w-16 h-16 relative overflow-hidden border-2 border-[#2a2a3a] 
                                group-hover:border-amber-400/50 transition-colors flex-shrink-0">
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
                <h2 
                  className="text-2xl font-bold text-gray-300 group-hover:text-amber-400 
                             transition-colors tracking-wide"
                >
                  {scenario.name}
                </h2>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
