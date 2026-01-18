'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import MapCanvas from '@components/MapCanvas'
import YearSlider from '@components/YearSlider'
import CountryInfo from '@components/CountryInfo'
import DivergenceInput from '@components/DivergenceInput'
import GamePanel from '@components/GamePanel'
import type { 
  ProvinceHistory, 
  RulerHistory, 
  ScenarioMetadata, 
  StartResponse, 
  ContinueResponse,
  LogEntry,
  RulerInfo,
  GameProvince
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
        // Switch to game mode
        setGameId(data.game_id)
        setGameMode(true)
        setGameYear(data.result.current_year)
        setGameMerged(data.result.merged)
        setGameLogs(data.result.logs)
        setGameRulers(data.result.rulers)
        setGameDivergences(data.result.divergences)

        // Fetch provinces for the game
        const provincesRes = await fetch(`/game/${data.game_id}/provinces`)
        if (provincesRes.ok) {
          const provincesData = await provincesRes.json()
          setGameProvinces(provincesData.provinces)
        } else {
          console.error('Failed to fetch provinces:', provincesRes.status)
        }

        // Fetch full game state for nation tags
        const gameStateRes = await fetch(`/game/${data.game_id}`)
        if (gameStateRes.ok) {
          const gameState = await gameStateRes.json()
          setGameNationTags(gameState.nation_tags || {})
        } else {
          console.error('Failed to fetch game state:', gameStateRes.status)
        }

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
  }, [scenarioId])

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

      // Fetch updated provinces
      const provincesRes = await fetch(`/game/${gameId}/provinces`)
      const provincesData = await provincesRes.json()
      setGameProvinces(provincesData.provinces)

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

  // Determine which province history to use
  const activeProvinceHistory = gameMode && gameProvinces.length > 0
    ? gameProvincesToHistory(gameProvinces, gameYear)
    : defaultProvinceHistory

  // In game mode, use game nation tags for colors (merge with scenario)
  const activeMetadata = gameMode && Object.keys(gameNationTags).length > 0
    ? { ...scenarioMetadata, tags: { ...scenarioMetadata?.tags, ...gameNationTags } }
    : scenarioMetadata

  const isLoading = !dataLoaded || !mapReady || year === null

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-black">
      {isLoading && <PixelLoader />}
      {dataLoaded && yearRange && year !== null && (
        <>
          {/* Year slider - only show when not in game mode */}
          {!gameMode && (
            <YearSlider
              onChange={setYear}
              initialValue={year}
              min={yearRange.min}
              max={yearRange.max}
            />
          )}

          {/* Country info - show in both modes but position differently when game panel is open */}
          <CountryInfo
            defaultRulerHistory={gameMode ? null : defaultRulerHistory}
            scenarioMetadata={activeMetadata as ScenarioMetadata}
            selectedTag={selectedTag}
            year={year}
            onTagChange={setSelectedTag}
          />

          {/* Map */}
          <MapCanvas
            defaultProvinceHistory={activeProvinceHistory}
            scenarioMetadata={activeMetadata as ScenarioMetadata}
            year={year}
            onProvinceSelect={setSelectedTag}
            onReady={() => setMapReady(true)}
          />

          {/* Game Panel - shows logs, rulers, divergences when in game mode */}
          {gameMode && (
            <GamePanel
              logs={gameLogs}
              rulers={gameRulers}
              divergences={gameDivergences}
              currentYear={gameYear}
              merged={gameMerged}
              onContinue={handleContinue}
              isProcessing={isProcessing}
              nationTags={gameNationTags}
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
