'use client'

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import type { LogEntry, TimelinePoint } from '@/types'

interface BranchingTimelineProps {
  minYear: number
  maxYear: number
  selectedYear: number
  onYearChange: (year: number) => void
  gameMode: boolean
  branchStartYear?: number
  logs: LogEntry[]
  merged: boolean
  currentGameYear: number
  selectedTimelinePoint: TimelinePoint
  onTimelinePointSelect: (point: TimelinePoint) => void
}

function parseEndYear(yearRange: string): number {
  const parts = yearRange.split('-')
  return parseInt(parts.length === 2 ? parts[1] : parts[0], 10)
}

function parseStartYear(yearRange: string): number {
  const parts = yearRange.split('-')
  return parseInt(parts[0], 10)
}

export default function BranchingTimeline({
  minYear,
  maxYear,
  selectedYear,
  onYearChange,
  gameMode,
  branchStartYear,
  logs,
  merged,
  currentGameYear,
  selectedTimelinePoint,
  onTimelinePointSelect
}: BranchingTimelineProps) {
  const [mainYear, setMainYear] = useState(selectedYear)
  const [altYear, setAltYear] = useState(currentGameYear)
  const [isDraggingMain, setIsDraggingMain] = useState(false)
  const [isDraggingAlt, setIsDraggingAlt] = useState(false)
  const mainTrackRef = useRef<HTMLDivElement>(null)
  const altTrackRef = useRef<HTMLDivElement>(null)

  // Update altYear when currentGameYear changes (new logs come in)
  useEffect(() => {
    if (currentGameYear > 0) {
      setAltYear(currentGameYear)
    }
  }, [currentGameYear])

  // Calculate the max year of the alternate timeline
  const altMaxYear = useMemo(() => {
    if (logs.length === 0) return currentGameYear
    return parseEndYear(logs[logs.length - 1].year_range)
  }, [logs, currentGameYear])

  // Calculate effective max year (extends if alternate goes past main)
  const effectiveMaxYear = useMemo(() => {
    if (!gameMode || logs.length === 0) return maxYear
    return Math.max(maxYear, altMaxYear)
  }, [gameMode, logs, maxYear, altMaxYear])

  // Year to percent conversion (same scale for both timelines)
  const yearToPercent = useCallback((year: number) => {
    return ((year - minYear) / (effectiveMaxYear - minYear)) * 100
  }, [minYear, effectiveMaxYear])

  // Branch point as percentage
  const branchPercent = useMemo(() => {
    if (!branchStartYear) return 0
    return yearToPercent(branchStartYear)
  }, [branchStartYear, yearToPercent])

  // Get the log index for a given year on the alternate timeline
  // We use the END year of each log to determine the snapshot to show.
  // This means: years before the end of a generation show the PREVIOUS snapshot,
  // and only at/after the end year do we show that generation's snapshot.
  const getLogIndexForYear = useCallback((year: number): number => {
    for (let i = logs.length - 1; i >= 0; i--) {
      const endYear = parseEndYear(logs[i].year_range)
      if (endYear <= year) return i
    }
    return 0
  }, [logs])

  // Update main year from mouse position
  const updateMainYear = useCallback((clientX: number) => {
    if (!mainTrackRef.current) return
    const rect = mainTrackRef.current.getBoundingClientRect()
    const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    const newYear = Math.round(minYear + percent * (effectiveMaxYear - minYear))
    const clampedYear = Math.max(minYear, Math.min(maxYear, newYear))
    setMainYear(clampedYear)
    onYearChange(clampedYear)
    onTimelinePointSelect({ timeline: 'main', year: clampedYear })
  }, [minYear, maxYear, effectiveMaxYear, onYearChange, onTimelinePointSelect])

  // Update alternate timeline year from mouse position
  const updateAltYear = useCallback((clientX: number) => {
    if (!altTrackRef.current || !branchStartYear) return
    const rect = altTrackRef.current.getBoundingClientRect()
    // Same coordinate system as main timeline
    const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    const newYear = Math.round(minYear + percent * (effectiveMaxYear - minYear))
    // Clamp to alternate timeline range
    const clampedYear = Math.max(branchStartYear, Math.min(altMaxYear, newYear))

    setAltYear(clampedYear)
    const logIndex = getLogIndexForYear(clampedYear)
    onTimelinePointSelect({
      timeline: 'alternate',
      year: clampedYear,
      logIndex
    })
  }, [minYear, effectiveMaxYear, branchStartYear, altMaxYear, getLogIndexForYear, onTimelinePointSelect])

  // Mouse event handlers for main timeline
  useEffect(() => {
    if (!isDraggingMain) return
    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault()
      updateMainYear(e.clientX)
    }
    const handleMouseUp = () => setIsDraggingMain(false)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingMain, updateMainYear])

  // Mouse event handlers for alternate timeline
  useEffect(() => {
    if (!isDraggingAlt) return
    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault()
      updateAltYear(e.clientX)
    }
    const handleMouseUp = () => setIsDraggingAlt(false)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDraggingAlt, updateAltYear])

  const handleMainMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDraggingMain(true)
    updateMainYear(e.clientX)
  }

  const handleAltMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsDraggingAlt(true)
    updateAltYear(e.clientX)
  }

  // Slider positions using same scale
  const mainSliderPercent = yearToPercent(mainYear)
  const altSliderPercent = yearToPercent(altYear)
  const altMaxPercent = yearToPercent(altMaxYear)
  const mainMaxPercent = yearToPercent(maxYear)  // Where the main timeline actually ends

  // Fill percentages
  const mainFillPercent = selectedTimelinePoint.timeline === 'alternate'
    ? branchPercent
    : mainSliderPercent

  // Alt fill: from branch point to current alt position, as percentage of the visible track
  const altFillPercent = useMemo(() => {
    if (altMaxPercent <= branchPercent) return 0
    return ((altSliderPercent - branchPercent) / (altMaxPercent - branchPercent)) * 100
  }, [altSliderPercent, branchPercent, altMaxPercent])

  const decrementYear = () => {
    if (selectedTimelinePoint.timeline === 'main') {
      if (mainYear > minYear) {
        const newYear = mainYear - 1
        setMainYear(newYear)
        onYearChange(newYear)
        onTimelinePointSelect({ timeline: 'main', year: newYear })
      }
    } else {
      if (branchStartYear && altYear > branchStartYear) {
        const newYear = altYear - 1
        setAltYear(newYear)
        const logIndex = getLogIndexForYear(newYear)
        onTimelinePointSelect({ timeline: 'alternate', year: newYear, logIndex })
      }
    }
  }

  const incrementYear = () => {
    if (selectedTimelinePoint.timeline === 'main') {
      if (mainYear < maxYear) {
        const newYear = mainYear + 1
        setMainYear(newYear)
        onYearChange(newYear)
        onTimelinePointSelect({ timeline: 'main', year: newYear })
      }
    } else {
      if (altYear < altMaxYear) {
        const newYear = altYear + 1
        setAltYear(newYear)
        const logIndex = getLogIndexForYear(newYear)
        onTimelinePointSelect({ timeline: 'alternate', year: newYear, logIndex })
      }
    }
  }

  const displayYear = selectedTimelinePoint.timeline === 'main' ? mainYear : altYear
  const showAltTimeline = gameMode && logs.length > 0 && branchStartYear !== undefined
  const isAltSelected = selectedTimelinePoint.timeline === 'alternate'

  return (
    <div className="absolute top-8 left-1/2 w-2/3 -translate-x-1/2 z-50 select-none pointer-events-auto px-4">
      <div className="relative bg-[#1a1a24] border-2 border-[#2a2a3a] p-2 shadow-[0_2px_0_#0a0a10]">
        {/* Year display tab */}
        <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-[-2px] bg-[#1a1a24] border-2 border-b-0 border-[#2a2a3a] px-[3px] py-[1px] flex items-center gap-[2px]">
          <button
            onClick={decrementYear}
            className="outline-none border-none focus:outline-none focus:border-none active:outline-none text-amber-400 hover:text-amber-300"
            style={{ imageRendering: 'pixelated' }}
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor">
              <rect x="4" y="0" width="2" height="2" />
              <rect x="2" y="2" width="2" height="2" />
              <rect x="0" y="4" width="2" height="2" />
              <rect x="2" y="6" width="2" height="2" />
            </svg>
          </button>
          <span className="text-amber-400 font-bold text-xl tracking-wide leading-none whitespace-nowrap">
            {displayYear}
          </span>
          <button
            onClick={incrementYear}
            className="outline-none border-none focus:outline-none focus:border-none active:outline-none text-amber-400 hover:text-amber-300"
            style={{ imageRendering: 'pixelated' }}
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="currentColor">
              <rect x="2" y="0" width="2" height="2" />
              <rect x="4" y="2" width="2" height="2" />
              <rect x="6" y="4" width="2" height="2" />
              <rect x="4" y="6" width="2" height="2" />
            </svg>
          </button>
        </div>

        {/* Main timeline track - only extends to maxYear, not effectiveMaxYear */}
        <div
          ref={mainTrackRef}
          className="cursor-pointer relative h-2"
          onMouseDown={handleMainMouseDown}
        >
          {/* Visible track portion (only to maxYear) */}
          <div
            className="absolute top-0 left-0 h-full bg-pixel-track border-[3px] border-pixel-dark shadow-[inset_0_0_0_2px_#4a4a6a]"
            style={{ width: `${mainMaxPercent}%` }}
          >
            <div
              className="absolute top-0 left-0 h-full bg-pixel-amber"
              style={{ width: `${(mainFillPercent / mainMaxPercent) * 100}%` }}
            />
          </div>
          {selectedTimelinePoint.timeline === 'main' && (
            <div
              className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-grab w-3 h-4 bg-pixel-knob border-[3px] border-pixel-dark"
              style={{ left: `${mainSliderPercent}%` }}
              onMouseDown={handleMainMouseDown}
            />
          )}
        </div>

        {/* Alternate timeline */}
        {showAltTimeline && (
          <>
            {/* Alt timeline - full width container for consistent coordinates */}
            <div
              ref={altTrackRef}
              className="relative h-2 mt-3 cursor-pointer"
              onMouseDown={handleAltMouseDown}
            >
              {/* Connector line at start of alt track - only colored when alt is selected */}
              <div
                className={`absolute w-[2px] ${isAltSelected ? 'bg-amber-500' : 'bg-[#4a4a6a]'}`}
                style={{
                  left: `${branchPercent}%`,
                  top: '-14px',
                  height: '14px'
                }}
              />

              {/* Visible track portion (from branch to end) */}
              <div
                className="absolute top-0 h-full bg-pixel-track border-[3px] border-pixel-dark shadow-[inset_0_0_0_2px_#4a4a6a]"
                style={{
                  left: `${branchPercent}%`,
                  width: `${altMaxPercent - branchPercent}%`
                }}
              >
                {/* Fill within the visible track - only show when alt is selected */}
                {isAltSelected && (
                  <div
                    className="absolute top-0 left-0 h-full bg-amber-600"
                    style={{ width: `${altFillPercent}%` }}
                  />
                )}
              </div>

              {/* Knob positioned using full timeline coordinates */}
              {isAltSelected && (
                <div
                  className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-grab w-3 h-4 bg-pixel-knob border-[3px] border-pixel-dark z-10"
                  style={{ left: `${altSliderPercent}%` }}
                  onMouseDown={handleAltMouseDown}
                />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
