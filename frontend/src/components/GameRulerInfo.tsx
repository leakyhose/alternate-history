'use client'

import { useEffect, useMemo } from 'react'
import type { RulerInfo } from '@/types'

interface GameRulerInfoProps {
  rulers: Record<string, RulerInfo>
  nationTags: Record<string, { name: string; color: string }>
  selectedTag?: string | null
  onTagChange: (tag: string) => void
}

export default function GameRulerInfo({
  rulers,
  nationTags,
  selectedTag,
  onTagChange
}: GameRulerInfoProps) {
  const availableTags = useMemo(() => Object.keys(rulers), [rulers])

  // Auto-select first available tag only when none selected at all
  useEffect(() => {
    if (availableTags.length > 0 && !selectedTag) {
      const firstTag = availableTags[0]
      onTagChange(firstTag)
    }
  }, [selectedTag, availableTags, onTagChange])

  // Use the selected tag if it exists in rulers, otherwise use first available
  // But always show SOMETHING if we have a selectedTag (even if no ruler)
  const displayTag = selectedTag || availableTags[0]
  const displayRuler = displayTag ? rulers[displayTag] : null

  // If no rulers at all, don't show the panel
  if (availableTags.length === 0) {
    return null
  }

  // Get nation name - check nationTags first, then rulers
  const nationName = nationTags[displayTag]?.name || displayTag

  return (
    <div className="absolute bottom-24 left-5 w-96 bg-[#1a1a24] border-2 border-[#2a2a3a] p-4 shadow-[inset_0_0_0_1px_#0a0a10,0_2px_0_#0a0a10] text-amber-400 z-20">
      {/* Country Name */}
      <h2 className="text-3xl font-bold text-center tracking-wide">
        {nationName}
      </h2>

      <div className="border-t border-[#2a2a3a] my-3"></div>

      {/* Ruler */}
      {displayRuler ? (
        <div className="text-center">
          <div className={`font-semibold leading-tight ${displayRuler.name.length > 15 ? 'text-4xl' : 'text-5xl'}`}>
            {displayRuler.name}
          </div>
          <div className="text-amber-600 text-sm mt-1">
            {displayRuler.dynasty ? `${displayRuler.dynasty}` : ''}
            {displayRuler.dynasty && displayRuler.age ? ' · ' : ''}
            {displayRuler.age ? `${displayRuler.age} years old` : ''}
          </div>
          <div className="text-gray-400 text-xs mt-1">
            {displayRuler.title}
          </div>
        </div>
      ) : (
        <div className="text-center text-gray-500 italic">
          <div className="text-lg">No ruler tracked</div>
          <div className="text-xs mt-1">Click a scenario nation to view ruler</div>
        </div>
      )}
    </div>
  )
}
