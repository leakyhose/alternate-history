'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import MapCanvas from '@components/MapCanvas'
import YearSlider from '@components/YearSlider'
import CountryInfo from '@components/CountryInfo'
import type { ProvinceHistory, RulerHistory, ScenarioMetadata } from '@/types'

function PixelLoader() {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame(f => (f + 1) % 4)
    }, 300)
    return () => clearInterval(interval)
  }, [])

  const dots = '.'.repeat(frame + 1)

  return (
    <div className="absolute inset-0 bg-black flex items-center justify-center z-50">
      <div className="text-center">
        <div className="text-pixel-amber text-2xl font-bold tracking-wide">
          Loading{dots}
        </div>
      </div>
    </div>
  )
}

export default function ScenarioPage() {
  const params = useParams()
  const scenarioId = params.id as string

  const [year, setYear] = useState<number | null>(null)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [defaultProvinceHistory, setDefaultProvinceHistory] = useState<ProvinceHistory | null>(null)
  const [defaultRulerHistory, setDefaultRulerHistory] = useState<RulerHistory | null>(null)
  const [scenarioMetadata, setScenarioMetadata] = useState<ScenarioMetadata | null>(null)
  const [yearRange, setYearRange] = useState<{ min: number; max: number } | null>(null)
  const [dataLoaded, setDataLoaded] = useState(false)
  const [mapReady, setMapReady] = useState(false)

  useEffect(() => {
    if (!scenarioId) return

    Promise.all([
      fetch(`/api/scenarios/${scenarioId}/provinces`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch(`/api/scenarios/${scenarioId}/rulers`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch(`/api/scenarios/${scenarioId}/metadata`, { cache: 'no-store' })
        .then(res => res.json())
        .catch(() => ({ name: scenarioId, tags: {} }))
    ])
      .then(([provinces, rulers, metadata]) => {
        setDefaultProvinceHistory(provinces)
        setDefaultRulerHistory(rulers)
        setScenarioMetadata(metadata)

        // Calculate year range from provinces data
        // Find years where at least one province is owned by a scenario tag
        const scenarioTags = new Set(Object.keys(metadata.tags || {}))
        const years = Object.keys(provinces).map(Number).filter(n => !isNaN(n)).sort((a, b) => a - b)

        if (years.length > 0) {
          const minYear = years[0]

          // Find the last year where any scenario tag owns at least one province
          let lastActiveYear = minYear
          for (const yr of years) {
            const yearData = provinces[String(yr)]
            if (yearData && Array.isArray(yearData)) {
              const hasScenarioProvince = yearData.some(
                (p: { OWNER?: string }) => p.OWNER && scenarioTags.has(p.OWNER)
              )
              if (hasScenarioProvince) {
                lastActiveYear = yr
              }
            }
          }

          // +1 for "empty map" end year showing the scenario has ended
          const maxYear = lastActiveYear + 1
          setYearRange({ min: minYear, max: maxYear })
          setYear(minYear) // Start at first year with data
        }

        setDataLoaded(true)
      })
      .catch(err => {
        console.error(err)
        setDataLoaded(true)
      })
  }, [scenarioId])

  const isLoading = !dataLoaded || !mapReady || year === null

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      {isLoading && <PixelLoader />}
      {dataLoaded && yearRange && year !== null && (
        <>
          <YearSlider
            onChange={setYear}
            initialValue={year}
            min={yearRange.min}
            max={yearRange.max}
          />
          <CountryInfo
            defaultRulerHistory={defaultRulerHistory}
            scenarioMetadata={scenarioMetadata}
            selectedTag={selectedTag}
            year={year}
            onTagChange={setSelectedTag}
          />
          <MapCanvas
            defaultProvinceHistory={defaultProvinceHistory}
            scenarioMetadata={scenarioMetadata}
            year={year}
            onProvinceSelect={setSelectedTag}
            onReady={() => setMapReady(true)}
          />
        </>
      )}
    </div>
  )
}
