'use client'

import { useEffect, useState } from 'react'
import MapCanvas from '@components/MapCanvas'
import YearSlider from '@components/YearSlider'
import CountryInfo from '@components/CountryInfo'
import type { ProvinceHistory } from '@/lib/map-renderer/types'

export default function RomePage() {
  const [year, setYear] = useState(2)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [history, setHistory] = useState<ProvinceHistory | null>(null)

  useEffect(() => {
    fetch("/api/history/roman")
      .then(res => {
        if (!res.ok) {
          throw new Error(`${res.status}`)
        }
        return res.json()
      })
      .then(data => setHistory(data))
      .catch(err => console.error(err))
  }, [])

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      <YearSlider onChange={setYear} initialValue={2} min={2} max={1453} />
      <CountryInfo selectedTag={selectedTag} year={year} onTagChange={setSelectedTag} />
      <MapCanvas defaultProvinceHistory={history} year={year} onProvinceSelect={setSelectedTag} />
    </div>
  )
}
