import { useState } from 'react'
import MapCanvas from '@src/components/MapCanvas'
import YearSlider from '@src/components/YearSlider'
import CountryInfo from '@src/components/CountryInfo'

export default function Rome() {
  const [year, setYear] = useState(2)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      <YearSlider onChange={setYear} initialValue={2} min={2} max={1453} />
      <CountryInfo selectedTag={selectedTag} year={year} />
      <MapCanvas year={year} />
    </div>
  )
}
