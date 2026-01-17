'use client'

import { useState } from 'react'
import MapCanvas from '@components/MapCanvas'
import YearSlider from '@components/YearSlider'
import CountryInfo from '@components/CountryInfo'

export default function RomePage() {
  const [year, setYear] = useState(2)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      <YearSlider onChange={setYear} initialValue={2} min={2} max={1453} />
      <CountryInfo selectedTag={selectedTag} year={year} onTagChange={setSelectedTag} />
      <MapCanvas year={year} onProvinceSelect={setSelectedTag} />
    </div>
  )
}
