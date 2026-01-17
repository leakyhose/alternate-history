import { useState } from 'react'
import MapCanvas from '@src/components/MapCanvas'
import YearSlider from '@src/components/YearSlider'

export default function Rome() {
  const [year, setYear] = useState(2)

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      <YearSlider onChange={setYear} initialValue={2} min={2} max={2000} />
      <MapCanvas year={year} />
    </div>
  )
}
