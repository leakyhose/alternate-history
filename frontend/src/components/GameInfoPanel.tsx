'use client'

import { useState, useMemo } from 'react'
import Image from 'next/image'
import type { LogEntry, TimelinePoint, StreamingPhase } from '@/types'

interface GameInfoPanelProps {
  logs: LogEntry[]
  divergences: string[]
  selectedTimelinePoint: TimelinePoint
  merged: boolean
  isProcessing: boolean
  streamingPhase?: StreamingPhase
  nationTags?: Record<string, { name: string; color: string }>
}

export default function GameInfoPanel({
  logs,
  divergences,
  selectedTimelinePoint,
  merged,
  isProcessing,
  streamingPhase = 'idle',
  nationTags = {}
}: GameInfoPanelProps) {
  const [activeTab, setActiveTab] = useState<'logs' | 'divergences'>('logs')
  const [isCollapsed, setIsCollapsed] = useState(false)

  // Check if we're in a streaming loading state
  const isDreaming = streamingPhase === 'dreaming'
  const isQuoting = streamingPhase === 'quoting'
  const isIllustrating = streamingPhase === 'illustrating'
  const isMapping = streamingPhase === 'mapping'
  const isStreaming = isDreaming || isQuoting || isIllustrating || isMapping

  // Get logs up to the selected point
  const visibleLogs = useMemo(() => {
    if (selectedTimelinePoint.timeline === 'main') {
      return logs
    }
    const maxIndex = selectedTimelinePoint.logIndex !== undefined
      ? selectedTimelinePoint.logIndex + 1
      : logs.length
    return logs.slice(0, maxIndex)
  }, [logs, selectedTimelinePoint])

  // Get divergences active at the selected point
  const visibleDivergences = useMemo(() => {
    if (selectedTimelinePoint.timeline === 'main') {
      return []
    }
    if (selectedTimelinePoint.logIndex !== undefined && logs[selectedTimelinePoint.logIndex]) {
      return logs[selectedTimelinePoint.logIndex].divergences || []
    }
    return divergences
  }, [selectedTimelinePoint, logs, divergences])

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute bottom-5 right-5 bg-[#1a1a24] border-2 border-[#2a2a3a] p-3 z-30
                   text-amber-400 hover:bg-[#2a2a3a] transition-colors"
      >
        ◀
      </button>
    )
  }

  return (
    <div className="absolute bottom-5 right-5 w-96 max-h-[60vh] bg-[#1a1a24] border-2 border-[#2a2a3a]
                    flex flex-col z-30 shadow-lg">
      {/* Header with tabs */}
      <div className="flex items-center justify-between border-b border-[#2a2a3a] px-2">
        {/* Compact tabs */}
        <div className="flex gap-1 py-1">
          <button
            onClick={() => setActiveTab('logs')}
            className={`px-3 py-1 text-xs font-medium rounded transition-colors
              ${activeTab === 'logs'
                ? 'text-amber-400 bg-[#2a2a3a]'
                : 'text-gray-500 hover:text-gray-300'}`}
          >
            History ({visibleLogs.length})
          </button>
          <button
            onClick={() => setActiveTab('divergences')}
            className={`px-3 py-1 text-xs font-medium rounded transition-colors
              ${activeTab === 'divergences'
                ? 'text-amber-400 bg-[#2a2a3a]'
                : 'text-gray-500 hover:text-gray-300'}`}
          >
            Divergences ({visibleDivergences.length})
          </button>
        </div>
        <button
          onClick={() => setIsCollapsed(true)}
          className="text-gray-500 hover:text-amber-400 px-2 py-1"
        >
          ▶
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Streaming loading indicator */}
        {isDreaming && (
          <div className="flex flex-col items-center justify-center py-8 mb-4 border-b border-[#2a2a3a]">
            <div className="relative w-12 h-12 mb-4">
              <div className="absolute inset-0 border-4 border-amber-400/20 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-amber-400 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <div className="text-amber-400 text-base font-medium animate-pulse">
              Dreamer is imagining alternate history...
            </div>
            <p className="text-gray-500 text-sm mt-2">
              Crafting narrative and determining outcomes
            </p>
          </div>
        )}

        {isQuoting && (
          <div className="flex flex-col items-center justify-center py-4 mb-4 border-b border-[#2a2a3a]">
            <div className="text-amber-400 text-sm font-medium animate-pulse">
              Quotegiver is gathering ruler perspectives...
            </div>
          </div>
        )}

        {isIllustrating && (
          <div className="flex flex-col items-center justify-center py-4 mb-4 border-b border-[#2a2a3a]">
            <div className="text-amber-400 text-sm font-medium animate-pulse">
              Illustrator is painting ruler portraits...
            </div>
          </div>
        )}

        {isMapping && (
          <div className="flex flex-col items-center justify-center py-4 mb-4 border-b border-[#2a2a3a]">
            <div className="text-amber-400 text-sm font-medium animate-pulse">
              Geographer is mapping territorial changes...
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-4">
            {visibleLogs.length === 0 && !isStreaming ? (
              <p className="text-gray-500 text-center py-4 text-base">No history yet</p>
            ) : (
              [...visibleLogs].reverse().map((log, idx) => (
                <div key={idx} className="border-b border-[#2a2a3a] pb-4 last:border-b-0">
                  <div className="text-amber-400 font-bold mb-2 text-base">{log.year_range}</div>
                  <p className="text-gray-200 text-base leading-relaxed mb-3">{log.narrative}</p>
                  {log.quotes && log.quotes.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {log.quotes.map((q, qIdx) => (
                        <div key={qIdx} className="bg-[#0a0a14] border-l-2 border-amber-600 pl-3 py-2 pr-2 rounded-r flex items-start gap-3">
                          {q.portrait_base64 && (
                            <div className="flex-shrink-0">
                              <Image 
                                src={`data:image/png;base64,${q.portrait_base64}`}
                                alt={`Portrait of ${q.ruler_name}`}
                                width={48}
                                height={48}
                                className="w-12 h-12 rounded border border-amber-600/30 object-cover"
                                style={{ imageRendering: 'pixelated' }}
                                unoptimized
                              />
                            </div>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-gray-200 italic text-sm leading-relaxed">&ldquo;{q.quote}&rdquo;</p>
                            <p className="text-amber-500 text-xs mt-1 font-medium">
                              — {q.ruler_name}, {q.ruler_title}
                              {q.tag && nationTags[q.tag] ? ` of ${nationTags[q.tag].name}` : q.tag ? ` of ${q.tag}` : ''}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'divergences' && (
          <div className="space-y-2">
            {visibleDivergences.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-base">
                No active divergences
              </p>
            ) : (
              visibleDivergences.map((div, idx) => (
                <div key={idx} className="bg-[#0a0a14] p-3 rounded border border-[#2a2a3a]">
                  <p className="text-gray-200 text-base">{div}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
