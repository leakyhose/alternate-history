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
  ProvinceSnapshot
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

  // Timeline branching state
  const [branchStartYear, setBranchStartYear] = useState<number | null>(null)
  const [selectedTimelinePoint, setSelectedTimelinePoint] = useState<TimelinePoint>({ timeline: 'main', year: 0 })
  const [provinceSnapshots, setProvinceSnapshots] = useState<ProvinceSnapshot[]>([])

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false)
  const [inputError, setInputError] = useState<string | null>(null)
  const [inputAlternative, setInputAlternative] = useState<string | null>(null)

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

  // Start a new game
  const handleStartGame = useCallback(async (command: string, yearsToProgress: number) => {
    setIsProcessing(true)
    setInputError(null)
    setInputAlternative(null)

    // Create AbortController with 5 minute timeout for long-running workflow
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300000) // 5 minutes

    try {
      // Call backend directly to bypass Next.js proxy timeout
      const response = await fetch(`${BACKEND_URL}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command,
          scenario_id: scenarioId,
          years_to_progress: yearsToProgress
        }),
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      // Check for HTTP errors before parsing JSON
      if (!response.ok) {
        let errorMessage = `Server error: ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          // Response wasn't JSON, use status text
          errorMessage = `Server error: ${response.statusText}`
        }
        setInputError(errorMessage)
        setIsProcessing(false)
        return
      }

      const data: StartResponse = await response.json()

      if (data.status === 'rejected') {
        setInputError(data.reason || 'Command was rejected')
        setInputAlternative(data.alternative || null)
        setIsProcessing(false)
        return
      }

      if (data.status === 'accepted' && data.game_id && data.result) {
        // Capture branch start year from the response
        const startYear = data.year || year || 0
        setBranchStartYear(startYear)

        // Switch to game mode
        setGameId(data.game_id)
        setGameMode(true)
        setGameYear(data.result.current_year)
        setGameMerged(data.result.merged)
        setGameLogs(data.result.logs)
        setGameRulers(data.result.rulers)
        setGameDivergences(data.result.divergences)

        // Use snapshots from API response for timeline scrubbing
        if (data.snapshots && data.snapshots.length > 0) {
          setProvinceSnapshots(data.snapshots)
          // Set current provinces to the latest snapshot
          const latestSnapshot = data.snapshots[data.snapshots.length - 1]
          setGameProvinces(latestSnapshot.provinces)
        } else {
          // Fallback: fetch provinces separately
          const provincesRes = await fetch(`/game/${data.game_id}/provinces`)
          if (provincesRes.ok) {
            const provincesData = await provincesRes.json()
            setGameProvinces(provincesData.provinces)
          } else {
            console.error('Failed to fetch provinces:', provincesRes.status)
          }
        }

        // Fetch full game state for nation tags
        const gameStateRes = await fetch(`/game/${data.game_id}`)
        if (gameStateRes.ok) {
          const gameState = await gameStateRes.json()
          setGameNationTags(gameState.nation_tags || {})
        } else {
          console.error('Failed to fetch game state:', gameStateRes.status)
        }

        // Set timeline point to the newest log entry
        setSelectedTimelinePoint({
          timeline: 'alternate',
          year: data.result.current_year,
          logIndex: data.result.logs.length - 1
        })

        // Update year to game year
        setYear(data.result.current_year)
      }
    } catch (err) {
      console.error('Error starting game:', err)
      if (err instanceof Error && err.name === 'AbortError') {
        setInputError('Request timed out. The server is taking too long to respond.')
      } else {
        setInputError('Failed to connect to server')
      }
    } finally {
      setIsProcessing(false)
    }
  }, [scenarioId, year])

  // Continue the game
  const handleContinue = useCallback(async () => {
    if (!gameId) return

    setIsProcessing(true)

    // Create AbortController with 5 minute timeout for long-running workflow
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 300000) // 5 minutes

    try {
      // Call backend directly to bypass Next.js proxy timeout
      const response = await fetch(`${BACKEND_URL}/continue/${gameId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          years_to_progress: 20
        }),
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      // Check for HTTP errors before parsing JSON
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
        return
      }

      const data: ContinueResponse = await response.json()

      setGameYear(data.current_year)
      setGameMerged(data.merged)
      setGameLogs(data.logs)

      if (data.result) {
        setGameRulers(data.result.rulers)
        setGameDivergences(data.result.divergences)
      }

      // Use snapshots from API response for timeline scrubbing
      if (data.snapshots && data.snapshots.length > 0) {
        setProvinceSnapshots(data.snapshots)
        // Set current provinces to the latest snapshot
        const latestSnapshot = data.snapshots[data.snapshots.length - 1]
        setGameProvinces(latestSnapshot.provinces)
      } else {
        // Fallback: fetch provinces separately
        const provincesRes = await fetch(`/game/${gameId}/provinces`)
        const provincesData = await provincesRes.json()
        setGameProvinces(provincesData.provinces)
      }

      // Update timeline point to the newest log entry
      setSelectedTimelinePoint({
        timeline: 'alternate',
        year: data.current_year,
        logIndex: data.logs.length - 1
      })

      // Update year
      setYear(data.current_year)
    } catch (err) {
      console.error('Error continuing game:', err)
      if (err instanceof Error && err.name === 'AbortError') {
        console.error('Request timed out')
      }
    } finally {
      setIsProcessing(false)
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
      if (snapshot) {
        return snapshot.rulers
      }
    }

    return gameRulers
  }, [gameMode, selectedTimelinePoint, provinceSnapshots, gameRulers])

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
            />
          )}

          {/* Map */}
          <MapCanvas
            defaultProvinceHistory={activeProvinceHistory}
            scenarioMetadata={activeMetadata as ScenarioMetadata}
            year={activeYear || year}
            onProvinceSelect={setSelectedTag}
            onReady={() => setMapReady(true)}
          />

          {/* Game Info Panel - shows logs and divergences when in game mode */}
          {gameMode && (
            <GameInfoPanel
              logs={gameLogs}
              divergences={gameDivergences}
              selectedTimelinePoint={selectedTimelinePoint}
              merged={gameMerged}
              onContinue={handleContinue}
              isProcessing={isProcessing}
            />
          )}

          {/* Divergence Input - always visible at bottom */}
          <DivergenceInput
            onSubmit={handleStartGame}
            disabled={gameMode}
            isProcessing={isProcessing}
            error={inputError}
            alternative={inputAlternative}
            currentYear={gameMode ? gameYear : undefined}
          />
        </>
      )}
    </div>
  )
}
