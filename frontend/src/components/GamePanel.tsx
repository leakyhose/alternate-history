'use client'

import { useState } from 'react'
import type { LogEntry, RulerInfo } from '@/types'

interface GamePanelProps {
  logs: LogEntry[]
  rulers: Record<string, RulerInfo>
  divergences: string[]
  currentYear: number
  merged: boolean
  onContinue: () => void
  isProcessing: boolean
  nationTags?: Record<string, { name: string; color: string }>
}

export default function GamePanel({
  logs,
  rulers,
  divergences,
  currentYear,
  merged,
  onContinue,
  isProcessing,
  nationTags
}: GamePanelProps) {
  const [activeTab, setActiveTab] = useState<'logs' | 'rulers' | 'divergences'>('logs')
  const [isCollapsed, setIsCollapsed] = useState(false)

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="absolute top-5 right-5 bg-[#1a1a24] border-2 border-[#2a2a3a] p-3 z-30 
                   text-amber-400 hover:bg-[#2a2a3a] transition-colors"
      >
        ◀ Show Panel
      </button>
    )
  }

  return (
    <div className="absolute top-5 right-5 bottom-24 w-96 bg-[#1a1a24] border-2 border-[#2a2a3a] 
                    flex flex-col z-30 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#2a2a3a]">
        <div className="text-amber-400 font-bold text-2xl">
          Year {currentYear} AD
          {merged && <span className="ml-2 text-green-400 text-base">(Timeline Merged)</span>}
        </div>
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
          History ({logs.length})
        </button>
        <button
          onClick={() => setActiveTab('rulers')}
          className={`flex-1 py-3 px-4 text-base font-medium transition-colors
            ${activeTab === 'rulers' 
              ? 'text-amber-400 border-b-2 border-amber-400' 
              : 'text-gray-400 hover:text-amber-200'}`}
        >
          Rulers
        </button>
        <button
          onClick={() => setActiveTab('divergences')}
          className={`flex-1 py-3 px-4 text-base font-medium transition-colors
            ${activeTab === 'divergences' 
              ? 'text-amber-400 border-b-2 border-amber-400' 
              : 'text-gray-400 hover:text-amber-200'}`}
        >
          Divergences
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'logs' && (
          <div className="space-y-4">
            {logs.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-base">No history yet</p>
            ) : (
              [...logs].reverse().map((log, idx) => (
                <div key={idx} className="border-b border-[#2a2a3a] pb-4 last:border-b-0">
                  <div className="text-amber-400 font-bold mb-2 text-base">{log.year_range}</div>
                  <p className="text-gray-200 text-base leading-relaxed mb-3">{log.narrative}</p>
                  {log.territorial_changes_summary && (
                    <div className="mt-2">
                      <div className="text-amber-600 text-sm font-bold uppercase mb-1">Territorial Changes</div>
                      <p className="text-gray-300 text-sm leading-relaxed">{log.territorial_changes_summary}</p>
                    </div>
                  )}
                  {log.divergences && log.divergences.length > 0 && (
                    <div className="mt-2">
                      <div className="text-amber-600 text-sm font-bold uppercase mb-1">Active Divergences</div>
                      <ul className="text-gray-400 text-sm list-disc list-inside">
                        {log.divergences.map((d, i) => (
                          <li key={i}>{d}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'rulers' && (
          <div className="space-y-3">
            {Object.keys(rulers).length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-base">No rulers tracked</p>
            ) : (
              Object.entries(rulers).map(([tag, ruler]) => (
                <div key={tag} className="bg-[#0a0a14] p-3 rounded border border-[#2a2a3a]">
                  <div className="text-amber-400 font-bold text-lg">
                    {nationTags?.[tag]?.name || tag}
                  </div>
                  <div className="text-gray-200 text-xl font-bold mt-1">{ruler.name}</div>
                  <div className="text-gray-400 text-base mt-1">
                    {ruler.title}{ruler.dynasty ? ` • ${ruler.dynasty}` : ''} • Age {ruler.age}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'divergences' && (
          <div className="space-y-2">
            {divergences.length === 0 ? (
              <p className="text-gray-500 text-center py-4 text-base">
                Timeline has converged back to real history
              </p>
            ) : (
              divergences.map((div, idx) => (
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
          disabled={isProcessing || merged}
          className="w-full bg-amber-600 hover:bg-amber-500 text-black font-bold py-4 rounded text-lg
                     disabled:bg-gray-600 disabled:text-gray-400 disabled:cursor-not-allowed
                     transition-colors"
        >
          {isProcessing ? 'Processing...' : merged ? 'Timeline Merged' : 'Continue Timeline →'}
        </button>
        {!merged && (
          <p className="text-gray-500 text-sm text-center mt-2">
            Advances the simulation by 20 years
          </p>
        )}
      </div>
    </div>
  )
}
