'use client'

import { useEffect, useState } from 'react'
import MapCanvas from '@components/MapCanvas'
import YearSlider from '@components/YearSlider'
import CountryInfo from '@components/CountryInfo'
import type { ProvinceHistory, RulerHistory } from '@/lib/map-renderer/types'

export default function RomePage() {
  const [year, setYear] = useState(2)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [defaultProvinceHistory, setDefaultProvinceHistory] = useState<ProvinceHistory | null>(null)
  const [defaultRulerHistory, setDefaultRulerHistory] = useState<RulerHistory | null>(null)

  useEffect(() => {
    fetch("/api/rome/provinces")
      .then(res => {
        if (!res.ok) {
          throw new Error(`${res.status}`)
        }
        return res.json()
      })
      .then(data => setDefaultProvinceHistory(data))
      .catch(err => console.error(err))

    fetch("/api/rome/rulers")
      .then(res => {
        if (!res.ok) {
          throw new Error(`${res.status}`)
        }
        return res.json()
      })
      .then(data => setDefaultRulerHistory(data))
      .catch(err => console.error(err))
  }, [])

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      <YearSlider onChange={setYear} initialValue={2} min={2} max={1453} />
      <CountryInfo defaultRulerHistory={defaultRulerHistory} selectedTag={selectedTag} year={year} onTagChange={setSelectedTag} />
      <MapCanvas defaultProvinceHistory={defaultProvinceHistory} year={year} onProvinceSelect={setSelectedTag} />
    </div>
  )
}
