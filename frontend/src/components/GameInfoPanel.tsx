'use client'

import { useState, useMemo } from 'react'
import type { LogEntry, TimelinePoint } from '@/types'

interface GameInfoPanelProps {
  logs: LogEntry[]
  divergences: string[]
  selectedTimelinePoint: TimelinePoint
  merged: boolean
  onContinue: () => void
  isProcessing: boolean
}

export default function GameInfoPanel({
  logs,
  divergences,
  selectedTimelinePoint,
  merged,
  onContinue,
  isProcessing
}: GameInfoPanelProps) {
  const [activeTab, setActiveTab] = useState<'logs' | 'divergences'>('logs')
  const [isCollapsed, setIsCollapsed] = useState(false)

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
        className="absolute top-32 right-5 bg-[#1a1a24] border-2 border-[#2a2a3a] p-3 z-30
                   text-amber-400 hover:bg-[#2a2a3a] transition-colors"
      >
        ◀
      </button>
    )
  }

  const isViewingPast = selectedTimelinePoint.timeline === 'alternate' &&
    selectedTimelinePoint.logIndex !== undefined &&
    selectedTimelinePoint.logIndex < logs.length - 1

  return (
    <div className="absolute top-32 right-5 bottom-24 w-96 bg-[#1a1a24] border-2 border-[#2a2a3a]
                    flex flex-col z-30 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-end p-2 border-b border-[#2a2a3a]">
        <button
          onClick={() => setIsCollapsed(true)}
          className="text-gray-400 hover:text-amber-400 px-2"
        >
          ▶
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#2a2a3a]">
        <button
          onClick={() => setActiveTab('logs')}
          className={`flex-1 py-3 px-4 text-base font-medium transition-colors
            ${activeTab === 'logs'
              ? 'text-amber-400 border-b-2 border-amber-400'
              : 'text-gray-400 hover:text-amber-200'}`}
        >
          History ({visibleLogs.length})
        </button>
        <button
          onClick={() => setActiveTab('divergences')}
          className={`flex-1 py-3 px-4 text-base font-medium transition-colors
            ${activeTab === 'divergences'
              ? 'text-amber-400 border-b-2 border-amber-400'
              : 'text-gray-400 hover:text-amber-200'}`}
        >
          Divergences ({visibleDivergences.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'logs' && (
          <div className="space-y-4">
            {visibleLogs.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-base">No history yet</p>
            ) : (
              [...visibleLogs].reverse().map((log, idx) => (
                <div key={idx} className="border-b border-[#2a2a3a] pb-4 last:border-b-0">
                  <div className="text-amber-400 font-bold mb-2 text-base">{log.year_range}</div>
                  <p className="text-gray-200 text-base leading-relaxed mb-3">{log.narrative}</p>
                  {log.territorial_changes_summary && (
                    <div className="mt-2">
                      <div className="text-amber-600 text-sm font-bold uppercase mb-1">Territorial Changes</div>
                      <p className="text-gray-300 text-sm leading-relaxed">{log.territorial_changes_summary}</p>
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

      {/* Continue Button */}
      <div className="p-4 border-t border-[#2a2a3a] bg-[#1a1a24]">
        <button
          onClick={onContinue}
          disabled={isProcessing || merged || selectedTimelinePoint.timeline === 'main' || isViewingPast}
          className="w-full bg-amber-600 hover:bg-amber-500 text-black font-bold py-4 rounded text-lg
                     disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed
                     transition-colors"
        >
          {isProcessing ? 'Processing...'
            : merged ? 'Timeline Merged'
            : 'Continue Timeline →'}
        </button>
        {!merged && selectedTimelinePoint.timeline === 'alternate' && !isViewingPast && (
          <p className="text-gray-500 text-sm text-center mt-2">
            Advances the simulation by 20 years
          </p>
        )}
      </div>
    </div>
  )
}
