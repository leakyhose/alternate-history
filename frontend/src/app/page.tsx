'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

interface Scenario {
  id: string
  name: string
}

export default function Home() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/scenarios')
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
    <div className="min-h-screen flex flex-col items-center justify-center bg-black text-amber-400">
      <h1 className="text-4xl font-bold mb-8">Historical Scenarios</h1>

      {loading ? (
        <p>Loading scenarios...</p>
      ) : scenarios.length === 0 ? (
        <p>No scenarios available</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {scenarios.map(scenario => (
            <Link
              key={scenario.id}
              href={`/scenario/${scenario.id}`}
              className="block p-6 bg-[#1a1a24] border-2 border-[#2a2a3a] hover:border-amber-400 transition-colors"
            >
              <h2 className="text-2xl font-bold text-center">{scenario.name}</h2>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
