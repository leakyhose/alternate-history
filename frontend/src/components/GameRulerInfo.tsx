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

  // Auto-select first available tag when none selected or selected tag has no ruler
  useEffect(() => {
    if (availableTags.length > 0) {
      if (!selectedTag || !rulers[selectedTag]) {
        const firstTag = availableTags[0]
        onTagChange(firstTag)
      }
    }
  }, [selectedTag, rulers, availableTags, onTagChange])

  // Show the selected ruler or first ruler if none selected
  const displayTag = selectedTag && rulers[selectedTag] ? selectedTag : availableTags[0]
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
          {displayRuler.dynasty ? `${displayRuler.dynasty} · ` : ''}{displayRuler.age} years old
        </div>
        <div className="text-gray-400 text-xs mt-1">
          {displayRuler.title}
        </div>
      </div>
    </div>
  )
}
