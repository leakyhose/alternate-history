'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'next/navigation'
import MapCanvas from '@components/MapCanvas'
import CountryInfo from '@components/CountryInfo'
import DivergenceInput from '@components/DivergenceInput'
import BranchingTimeline from '@components/BranchingTimeline'
import GameInfoPanel from '@components/GameInfoPanel'
import GameRulerInfo from '@components/GameRulerInfo'
import type {
  ProvinceHistory,
  RulerHistory,
  ScenarioMetadata,
  StartResponse,
  ContinueResponse,
  LogEntry,
  RulerInfo,
  GameProvince,
  TimelinePoint,
  ProvinceSnapshot,
  StreamingPhase,
  StreamEvent
} from '@/types'

// Direct backend URL for long-running workflow requests (bypasses Next.js proxy timeout)
const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function PixelLoader() {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setFrame(f => (f + 1) % 4)
    }, 300)
    return () => clearInterval(interval)
  }, [])

  const dots = '.'.repeat(frame + 1)

  return (
    <div className="absolute inset-0 bg-black flex items-center justify-center z-50">
      <div className="text-center">
        <div className="text-pixel-amber text-2xl font-bold tracking-wide">
          Loading{dots}
        </div>
      </div>
    </div>
  )
}

// Convert game provinces to ProvinceHistory format for the map
function gameProvincesToHistory(provinces: GameProvince[], year: number): ProvinceHistory {
  return {
    [String(year)]: provinces.map(p => ({
      ID: p.id,
      NAME: p.name,
      OWNER: p.owner,
      CONTROL: p.control
    }))
  }
}

export default function ScenarioPage() {
  const params = useParams()
  const scenarioId = params.id as string

  // Default history mode state
  const [year, setYear] = useState<number | null>(null)
  const [selectedTag, setSelectedTag] = useState<string | null>(null)
  const [defaultProvinceHistory, setDefaultProvinceHistory] = useState<ProvinceHistory | null>(null)
  const [defaultRulerHistory, setDefaultRulerHistory] = useState<RulerHistory | null>(null)
  const [scenarioMetadata, setScenarioMetadata] = useState<ScenarioMetadata | null>(null)
  const [yearRange, setYearRange] = useState<{ min: number; max: number } | null>(null)
  const [dataLoaded, setDataLoaded] = useState(false)
  const [mapReady, setMapReady] = useState(false)

  // Game mode state
  const [gameMode, setGameMode] = useState(false)
  const [gameId, setGameId] = useState<string | null>(null)
  const [gameProvinces, setGameProvinces] = useState<GameProvince[]>([])
  const [gameLogs, setGameLogs] = useState<LogEntry[]>([])
  const [gameRulers, setGameRulers] = useState<Record<string, RulerInfo>>({})
  const [gameDivergences, setGameDivergences] = useState<string[]>([])
  const [gameYear, setGameYear] = useState<number>(0)
  const [gameMerged, setGameMerged] = useState(false)
  const [gameNationTags, setGameNationTags] = useState<Record<string, { name: string; color: string }>>({})
  const [gameYearsToProgress, setGameYearsToProgress] = useState<number>(5)  // Store the years used for this game)

  // Timeline branching state
  const [branchStartYear, setBranchStartYear] = useState<number | null>(null)
  const [selectedTimelinePoint, setSelectedTimelinePoint] = useState<TimelinePoint>({ timeline: 'main', year: 0 })
  const [provinceSnapshots, setProvinceSnapshots] = useState<ProvinceSnapshot[]>([])

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false)
  const [inputError, setInputError] = useState<string | null>(null)
  const [inputAlternative, setInputAlternative] = useState<string | null>(null)

  // Streaming state for progressive updates
  const [streamingPhase, setStreamingPhase] = useState<StreamingPhase>('idle')

  // Load default scenario data
  useEffect(() => {
    if (!scenarioId) return

    Promise.all([
      fetch(`/api/scenarios/${scenarioId}/provinces`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch(`/api/scenarios/${scenarioId}/rulers`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch(`/api/scenarios/${scenarioId}/metadata`, { cache: 'no-store' })
        .then(res => res.json())
        .catch(() => ({ name: scenarioId, tags: {} }))
    ])
      .then(([provinces, rulers, metadata]) => {
        setDefaultProvinceHistory(provinces)
        setDefaultRulerHistory(rulers)
        setScenarioMetadata(metadata)

        // Use period from metadata if available, otherwise calculate from provinces data
        if (metadata.period) {
          setYearRange({ min: metadata.period.start, max: metadata.period.end })
          setYear(metadata.period.start)
          setSelectedTimelinePoint({ timeline: 'main', year: metadata.period.start })
        } else {
          // Calculate year range from provinces data
          const scenarioTags = new Set(Object.keys(metadata.tags || {}))
          const years = Object.keys(provinces).map(Number).filter(n => !isNaN(n)).sort((a, b) => a - b)

          if (years.length > 0) {
            const minYear = years[0]

            let lastActiveYear = minYear
            for (const yr of years) {
              const yearData = provinces[String(yr)]
              if (yearData && Array.isArray(yearData)) {
                const hasScenarioProvince = yearData.some(
                  (p: { OWNER?: string }) => p.OWNER && scenarioTags.has(p.OWNER)
                )
                if (hasScenarioProvince) {
                  lastActiveYear = yr
                }
              }
            }

            const maxYear = lastActiveYear + 1
            setYearRange({ min: minYear, max: maxYear })
            setYear(minYear)
            setSelectedTimelinePoint({ timeline: 'main', year: minYear })
          }
        }

        setDataLoaded(true)
      })
      .catch(err => {
        console.error(err)
        setDataLoaded(true)
      })
  }, [scenarioId])

  // Start a new game with SSE streaming
  const handleStartGame = useCallback(async (command: string, yearsToProgress: number) => {
    setIsProcessing(true)
    setInputError(null)
    setInputAlternative(null)
    setStreamingPhase('filtering')
    setGameYearsToProgress(yearsToProgress)  // Store the years for future Continue calls

    try {
      // Use POST request with fetch for SSE (EventSource only supports GET)
      const response = await fetch(`${BACKEND_URL}/start-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command,
          scenario_id: scenarioId,
          years_to_progress: yearsToProgress
        })
      })

      if (!response.ok) {
        let errorMessage = `Server error: ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          errorMessage = `Server error: ${response.statusText}`
        }
        setInputError(errorMessage)
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      // Process the SSE stream
      const reader = response.body?.getReader()
      if (!reader) {
        setInputError('Failed to read response stream')
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as StreamEvent

              switch (data.event) {
                case 'rejected':
                  setInputError(data.reason || 'Command was rejected')
                  setInputAlternative(data.alternative || null)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  return

                case 'filter_complete':
                  // Timeline branches immediately
                  setBranchStartYear(data.year)
                  setGameId(data.game_id)
                  setGameMode(true)
                  setGameNationTags(data.nation_tags)
                  setYear(data.year)
                  setStreamingPhase('dreaming')
                  // Initialize with empty state until dreamer completes
                  setGameLogs([])
                  setGameRulers({})
                  setGameDivergences([command])
                  setSelectedTimelinePoint({
                    timeline: 'alternate',
                    year: data.year,
                    logIndex: 0
                  })
                  break

                case 'dreamer_complete':
                  // Populate the panel with narrative and rulers
                  setGameLogs([data.log_entry])
                  setGameRulers(data.rulers)
                  setGameDivergences(data.divergences)
                  setStreamingPhase('quoting')
                  break

                case 'quotegiver_complete':
                  // Update the log entry with quotes
                  setGameLogs(prev => {
                    if (prev.length === 0) return prev
                    const updated = [...prev]
                    updated[updated.length - 1] = {
                      ...updated[updated.length - 1],
                      quotes: data.quotes
                    }
                    return updated
                  })
                  setStreamingPhase('mapping')
                  break

                case 'geographer_complete':
                  // Map updates with provinces
                  setGameProvinces(data.provinces)
                  break

                case 'complete':
                  // Finalize everything
                  setGameId(data.game_id)
                  setGameYear(data.current_year)
                  setGameMerged(data.merged)
                  setGameLogs(data.logs)
                  setGameRulers(data.rulers)
                  setGameDivergences(data.divergences)
                  setProvinceSnapshots(data.snapshots)
                  if (data.snapshots && data.snapshots.length > 0) {
                    const latestSnapshot = data.snapshots[data.snapshots.length - 1]
                    setGameProvinces(latestSnapshot.provinces)
                  }
                  setSelectedTimelinePoint({
                    timeline: 'alternate',
                    year: data.current_year,
                    logIndex: data.logs.length - 1
                  })
                  setYear(data.current_year)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  break

                case 'error':
                  setInputError(data.message)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  return
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError)
            }
          }
        }
      }
    } catch (err) {
      console.error('Error starting game:', err)
      if (err instanceof Error && err.name === 'AbortError') {
        setInputError('Request timed out. The server is taking too long to respond.')
      } else {
        setInputError('Failed to connect to server')
      }
      setIsProcessing(false)
      setStreamingPhase('idle')
    }
  }, [scenarioId])

  // Continue the game with SSE streaming
  const handleContinue = useCallback(async () => {
    if (!gameId) return

    setIsProcessing(true)
    setStreamingPhase('dreaming')

    try {
      const response = await fetch(`${BACKEND_URL}/continue-stream/${gameId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          years_to_progress: gameYearsToProgress
        })
      })

      if (!response.ok) {
        let errorMessage = `Server error: ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          errorMessage = `Server error: ${response.statusText}`
        }
        console.error('Error continuing game:', errorMessage)
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        console.error('Failed to read response stream')
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as StreamEvent

              switch (data.event) {
                case 'dreamer_complete':
                  // Append new log entry (keep existing logs)
                  setGameLogs(prev => [...prev, data.log_entry])
                  setGameRulers(data.rulers)
                  setGameDivergences(data.divergences)
                  setStreamingPhase('quoting')
                  break

                case 'quotegiver_complete':
                  // Update the latest log entry with quotes
                  setGameLogs(prev => {
                    if (prev.length === 0) return prev
                    const updated = [...prev]
                    updated[updated.length - 1] = {
                      ...updated[updated.length - 1],
                      quotes: data.quotes
                    }
                    return updated
                  })
                  setStreamingPhase('mapping')
                  break

                case 'geographer_complete':
                  setGameProvinces(data.provinces)
                  break

                case 'complete':
                  setGameYear(data.current_year)
                  setGameMerged(data.merged)
                  setGameLogs(data.logs)
                  setGameRulers(data.rulers)
                  setGameDivergences(data.divergences)
                  setProvinceSnapshots(data.snapshots)
                  if (data.snapshots && data.snapshots.length > 0) {
                    const latestSnapshot = data.snapshots[data.snapshots.length - 1]
                    setGameProvinces(latestSnapshot.provinces)
                  }
                  setSelectedTimelinePoint({
                    timeline: 'alternate',
                    year: data.current_year,
                    logIndex: data.logs.length - 1
                  })
                  setYear(data.current_year)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  break

                case 'error':
                  console.error('Continue stream error:', data.message)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  return
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError)
            }
          }
        }
      }
    } catch (err) {
      console.error('Error continuing game:', err)
      if (err instanceof Error && err.name === 'AbortError') {
        console.error('Request timed out')
      }
      setIsProcessing(false)
      setStreamingPhase('idle')
    }
  }, [gameId, gameYearsToProgress])

  // Add a new divergence to an existing timeline with SSE streaming
  const handleAddDivergence = useCallback(async (command: string, yearsToProgress: number) => {
    if (!gameId) return

    setIsProcessing(true)
    setInputError(null)
    setInputAlternative(null)
    setStreamingPhase('filtering')

    try {
      // First, filter the divergence to check if it's valid for the current era
      const filterResponse = await fetch(`${BACKEND_URL}/game/${gameId}/filter-divergence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      })

      if (!filterResponse.ok) {
        let errorMessage = `Server error: ${filterResponse.status}`
        try {
          const errorData = await filterResponse.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          errorMessage = `Server error: ${filterResponse.statusText}`
        }
        setInputError(errorMessage)
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      const filterResult = await filterResponse.json()

      if (filterResult.status === 'rejected') {
        setInputError(filterResult.reason || 'Divergence was rejected')
        setInputAlternative(filterResult.alternative || null)
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      // If accepted, add the divergence and continue with streaming
      setStreamingPhase('dreaming')

      const response = await fetch(`${BACKEND_URL}/continue-stream/${gameId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_divergences: [command],
          years_to_progress: yearsToProgress
        })
      })

      if (!response.ok) {
        let errorMessage = `Server error: ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          errorMessage = `Server error: ${response.statusText}`
        }
        setInputError(errorMessage)
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        setInputError('Failed to read response stream')
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)) as StreamEvent

              switch (data.event) {
                case 'dreamer_complete':
                  setGameLogs(prev => [...prev, data.log_entry])
                  setGameRulers(data.rulers)
                  setGameDivergences(data.divergences)
                  setStreamingPhase('quoting')
                  break

                case 'quotegiver_complete':
                  // Update the latest log entry with quotes
                  setGameLogs(prev => {
                    if (prev.length === 0) return prev
                    const updated = [...prev]
                    updated[updated.length - 1] = {
                      ...updated[updated.length - 1],
                      quotes: data.quotes
                    }
                    return updated
                  })
                  setStreamingPhase('mapping')
                  break

                case 'geographer_complete':
                  setGameProvinces(data.provinces)
                  break

                case 'complete':
                  setGameYear(data.current_year)
                  setGameMerged(data.merged)
                  setGameLogs(data.logs)
                  setGameRulers(data.rulers)
                  setGameDivergences(data.divergences)
                  setProvinceSnapshots(data.snapshots)
                  if (data.snapshots && data.snapshots.length > 0) {
                    const latestSnapshot = data.snapshots[data.snapshots.length - 1]
                    setGameProvinces(latestSnapshot.provinces)
                  }
                  setSelectedTimelinePoint({
                    timeline: 'alternate',
                    year: data.current_year,
                    logIndex: data.logs.length - 1
                  })
                  setYear(data.current_year)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  break

                case 'error':
                  setInputError(data.message)
                  setIsProcessing(false)
                  setStreamingPhase('idle')
                  return
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError)
            }
          }
        }
      }
    } catch (err) {
      console.error('Error adding divergence:', err)
      if (err instanceof Error && err.name === 'AbortError') {
        setInputError('Request timed out. The server is taking too long to respond.')
      } else {
        setInputError('Failed to connect to server')
      }
      setIsProcessing(false)
      setStreamingPhase('idle')
    }
  }, [gameId])

  // Handle timeline point selection
  const handleTimelinePointSelect = useCallback((point: TimelinePoint) => {
    setSelectedTimelinePoint(point)

    if (point.timeline === 'main') {
      // Switch to viewing historical data at selected year
      setYear(point.year)
    } else if (point.logIndex !== undefined) {
      // Switch to viewing alternate timeline at selected log point
      const snapshot = provinceSnapshots[point.logIndex]
      if (snapshot) {
        setGameProvinces(snapshot.provinces)
        setGameRulers(snapshot.rulers)
        setGameDivergences(snapshot.divergences)
      }
      setYear(point.year)
    }
  }, [provinceSnapshots])

  // Handle year change from timeline (for main timeline dragging)
  const handleYearChange = useCallback((newYear: number) => {
    setYear(newYear)
  }, [])

  // Determine which province history to use based on selected timeline point
  const activeProvinceHistory = useMemo(() => {
    if (!gameMode) {
      return defaultProvinceHistory
    }

    if (selectedTimelinePoint.timeline === 'main') {
      // Show historical data when main timeline is selected
      return defaultProvinceHistory
    }

    // Show game provinces for alternate timeline
    if (gameProvinces.length > 0) {
      return gameProvincesToHistory(gameProvinces, gameYear)
    }

    return defaultProvinceHistory
  }, [gameMode, selectedTimelinePoint, defaultProvinceHistory, gameProvinces, gameYear])

  // Determine the active year for the map
  const activeYear = useMemo(() => {
    if (!gameMode) return year

    if (selectedTimelinePoint.timeline === 'main') {
      return selectedTimelinePoint.year
    }

    // For alternate timeline, use the game year
    return gameYear
  }, [gameMode, selectedTimelinePoint, year, gameYear])

  // In game mode, use game nation tags for colors (merge with scenario)
  const activeMetadata = gameMode && Object.keys(gameNationTags).length > 0
    ? { ...scenarioMetadata, tags: { ...scenarioMetadata?.tags, ...gameNationTags } }
    : scenarioMetadata

  // Get rulers to display based on selected timeline point
  const activeRulers = useMemo(() => {
    if (!gameMode) return {}

    if (selectedTimelinePoint.timeline === 'main') {
      return {}  // Don't show game rulers when viewing main timeline
    }

    if (selectedTimelinePoint.logIndex !== undefined) {
      const snapshot = provinceSnapshots[selectedTimelinePoint.logIndex]
      if (snapshot && snapshot.rulers && Object.keys(snapshot.rulers).length > 0) {
        return snapshot.rulers
      }
    }

    return gameRulers
  }, [gameMode, selectedTimelinePoint, provinceSnapshots, gameRulers])

  // Determine if we're viewing the latest year of the alternate timeline
  const isViewingLatestAltYear = useMemo(() => {
    if (!gameMode || gameLogs.length === 0) return false
    if (selectedTimelinePoint.timeline !== 'alternate') return false
    // Check if we're on the latest log entry
    return selectedTimelinePoint.logIndex === gameLogs.length - 1
  }, [gameMode, gameLogs, selectedTimelinePoint])

  // Show divergence input when:
  // 1. No alternate timeline exists (not in game mode), OR
  // 2. In game mode AND viewing the latest year of the alternate timeline
  const showDivergenceInput = !gameMode || isViewingLatestAltYear

  const isLoading = !dataLoaded || !mapReady || year === null

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      {isLoading && <PixelLoader />}
      {dataLoaded && yearRange && year !== null && (
        <>
          {/* Branching Timeline - replaces YearSlider and handles both modes */}
          <BranchingTimeline
            minYear={yearRange.min}
            maxYear={yearRange.max}
            selectedYear={year}
            onYearChange={handleYearChange}
            gameMode={gameMode}
            branchStartYear={branchStartYear || undefined}
            logs={gameLogs}
            merged={gameMerged}
            currentGameYear={gameYear}
            selectedTimelinePoint={selectedTimelinePoint}
            onTimelinePointSelect={handleTimelinePointSelect}
          />

          {/* Country info - show in history mode or when viewing main timeline in game mode */}
          {(!gameMode || selectedTimelinePoint.timeline === 'main') && (
            <CountryInfo
              defaultRulerHistory={defaultRulerHistory}
              scenarioMetadata={activeMetadata as ScenarioMetadata}
              selectedTag={selectedTag}
              year={activeYear || year}
              onTagChange={setSelectedTag}
            />
          )}

          {/* Game Ruler Info - show when viewing alternate timeline */}
          {gameMode && selectedTimelinePoint.timeline === 'alternate' && (
            <GameRulerInfo
              rulers={activeRulers}
              nationTags={gameNationTags}
              selectedTag={selectedTag}
              onTagChange={setSelectedTag}
            />
          )}

          {/* Map */}
          <MapCanvas
            defaultProvinceHistory={activeProvinceHistory}
            scenarioMetadata={activeMetadata as ScenarioMetadata}
            year={activeYear || year}
            onProvinceSelect={setSelectedTag}
            onReady={() => setMapReady(true)}
            isStreamingMap={
              (streamingPhase === 'mapping' || streamingPhase === 'dreaming') &&
              selectedTimelinePoint.timeline === 'alternate' &&
              (gameLogs.length === 0 || selectedTimelinePoint.logIndex === gameLogs.length - 1)
            }
          />

          {/* Game Info Panel - shows logs and divergences when viewing alternate timeline */}
          {gameMode && selectedTimelinePoint.timeline === 'alternate' && (
            <GameInfoPanel
              logs={gameLogs}
              divergences={gameDivergences}
              selectedTimelinePoint={selectedTimelinePoint}
              merged={gameMerged}
              onContinue={handleContinue}
              isProcessing={isProcessing}
              streamingPhase={streamingPhase}
              yearsToProgress={gameYearsToProgress}
              nationTags={gameNationTags}
            />
          )}

          {/* Divergence Input - show when no alternate timeline exists OR when viewing latest year of alternate */}
          {showDivergenceInput && (
            <DivergenceInput
              onSubmit={gameMode ? handleAddDivergence : handleStartGame}
              disabled={false}
              isProcessing={isProcessing}
              error={inputError}
              alternative={inputAlternative}
              currentYear={gameMode ? gameYear : undefined}
              isAddingDivergence={gameMode}
            />
          )}
        </>
      )}
    </div>
  )
}
