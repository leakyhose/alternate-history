'use client'

import { useEffect, useState } from 'react'
import MapCanvas from '@components/MapCanvas'
import YearSlider from '@components/YearSlider'
import CountryInfo from '@components/CountryInfo'
import type { ProvinceHistory, RulerHistory } from '@/types'

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

export default function RomePage() {
  const [year, setYear] = useState(2)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [defaultProvinceHistory, setDefaultProvinceHistory] = useState<ProvinceHistory | null>(null)
  const [defaultRulerHistory, setDefaultRulerHistory] = useState<RulerHistory | null>(null)
  const [dataLoaded, setDataLoaded] = useState(false)
  const [mapReady, setMapReady] = useState(false)

  useEffect(() => {
    Promise.all([
      fetch("/api/rome/provinces", { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch("/api/rome/rulers", { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        })
    ])
      .then(([provinces, rulers]) => {
        setDefaultProvinceHistory(provinces)
        setDefaultRulerHistory(rulers)
        setDataLoaded(true)
      })
      .catch(err => {
        console.error(err)
        setDataLoaded(true)
      })
  }, [])

  const isLoading = !dataLoaded || !mapReady

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      {isLoading && <PixelLoader />}
      {dataLoaded && (
        <>
          <YearSlider onChange={setYear} initialValue={2} min={2} max={1453} />
          <CountryInfo defaultRulerHistory={defaultRulerHistory} selectedTag={selectedTag} year={year} onTagChange={setSelectedTag} />
          <MapCanvas
            defaultProvinceHistory={defaultProvinceHistory}
            year={year}
            onProvinceSelect={setSelectedTag}
            onReady={() => setMapReady(true)}
          />
        </>
      )}
    </div>
  )
}
