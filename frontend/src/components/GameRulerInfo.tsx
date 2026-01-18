'use client'

import type { RulerInfo } from '@/types'

interface GameRulerInfoProps {
  rulers: Record<string, RulerInfo>
  nationTags: Record<string, { name: string; color: string }>
  selectedTag?: string | null
}

export default function GameRulerInfo({
  rulers,
  nationTags,
  selectedTag
}: GameRulerInfoProps) {
  // If a tag is selected, show that ruler first
  const orderedTags = Object.keys(rulers).sort((a, b) => {
    if (a === selectedTag) return -1
    if (b === selectedTag) return 1
    return 0
  })

  // Show only the selected ruler or first ruler if none selected
  const displayTag = selectedTag && rulers[selectedTag] ? selectedTag : orderedTags[0]
  const displayRuler = displayTag ? rulers[displayTag] : null

  if (!displayRuler) {
    return null
  }

  const nationName = nationTags[displayTag]?.name || displayTag

  return (
    <div className="absolute bottom-5 left-5 min-w-60 max-w-64 bg-[#1a1a24] border-2 border-[#2a2a3a] p-4 shadow-[inset_0_0_0_1px_#0a0a10,0_2px_0_#0a0a10] text-amber-400 z-20">
      {/* Country Name */}
      <h2 className="text-3xl font-bold text-center tracking-wide">
        {nationName}
      </h2>

      <div className="border-t border-[#2a2a3a] my-3"></div>

      {/* Ruler */}
      <div className="text-center">
        <div className={`font-semibold leading-tight ${displayRuler.name.length > 15 ? 'text-4xl' : 'text-5xl'}`}>
          {displayRuler.name}
        </div>
        <div className="text-amber-600 text-sm mt-1">
          {displayRuler.dynasty} dynasty · {displayRuler.age} years old
        </div>
        <div className="text-gray-400 text-xs mt-1">
          {displayRuler.title}
        </div>
      </div>

      {/* Show count of other rulers if multiple */}
      {orderedTags.length > 1 && (
        <div className="border-t border-[#2a2a3a] mt-3 pt-2 text-center">
          <span className="text-gray-500 text-xs">
            +{orderedTags.length - 1} other {orderedTags.length - 1 === 1 ? 'ruler' : 'rulers'}
          </span>
        </div>
      )}
    </div>
  )
}
