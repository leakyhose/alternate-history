'use client'

import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useParams } from 'next/navigation'
import MapCanvas from '@components/MapCanvas'
import CountryInfo from '@components/CountryInfo'
import DivergenceInput from '@components/DivergenceInput'
import BranchingTimeline from '@components/BranchingTimeline'
import GameInfoPanel from '@components/GameInfoPanel'
import GameRulerInfo from '@components/GameRulerInfo'
import { useGameWebSocket } from '@/hooks/useGameWebSocket'
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
  Quote,
} from '@/types'

// Direct backend URL for long-running workflow requests (bypasses Next.js proxy timeout)
// Strip trailing slash to avoid double-slash issues
const BACKEND_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

// Debug: Log at module load time (this runs when JS is parsed)
console.log('='.repeat(50))
console.log('� ENV DEBUG AT BUILD TIME:')
console.log('   process.env.NEXT_PUBLIC_API_URL =', process.env.NEXT_PUBLIC_API_URL)
console.log('   BACKEND_URL =', BACKEND_URL)
console.log('='.repeat(50))

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
  const [gameYearsToProgress, setGameYearsToProgress] = useState<number>(10)  // Store the years used for this game

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

  // WebSocket for real-time updates from aggregator
  const {
    status: wsStatus,
    connect: wsConnect,
    disconnect: wsDisconnect,
    onTimelineUpdate,
    onQuotesUpdate,
    onProvincesUpdate,
    onPortraitsUpdate,
  } = useGameWebSocket()

  // Track which updates have arrived for the current iteration
  const updatesReceivedRef = useRef({ timeline: false, quotes: false, provinces: false, portraits: false })
  const streamingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const geographerTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  // Separate state for tracking if geographer has sent updates (for "Updating map..." indicator)
  const [geographerComplete, setGeographerComplete] = useState(true)

  // Helper to check if all updates arrived and reset streaming phase
  const checkStreamingComplete = useCallback(() => {
    const received = updatesReceivedRef.current
    // We need timeline. Geographer updates are nice to have but we have initial provinces from timeline.
    // Wait for portraits a bit, then go idle.
    if (received.timeline) {
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current)
      }
      // If portraits arrived, quick transition; if geographer arrived, medium wait; otherwise longer wait
      const delay = received.portraits ? 500 : received.provinces ? 2000 : 10000
      streamingTimeoutRef.current = setTimeout(() => {
        setStreamingPhase('idle')
      }, delay)
    }
  }, [])

  // Set up WebSocket event handlers (using refs to avoid stale closures)
  useEffect(() => {
    // Timeline update - narrative, rulers, divergences arrive first
    // This is the main event loop completing - user can continue after this
    onTimelineUpdate.current = (msg) => {
      console.log('📜 Timeline update received:', msg.iteration)

      // Reset tracking for new iteration
      updatesReceivedRef.current = { timeline: true, quotes: false, provinces: false, portraits: false }
      setStreamingPhase('quoting')
      setGeographerComplete(false)  // Geographer hasn't sent updates for this iteration yet

      // Set a timeout for geographer - don't show "Updating map..." forever
      if (geographerTimeoutRef.current) {
        clearTimeout(geographerTimeoutRef.current)
      }
      geographerTimeoutRef.current = setTimeout(() => {
        console.log('⏱️ Geographer timeout - marking complete')
        setGeographerComplete(true)
      }, 30000)  // 30 second timeout for geographer

      // Parse year from year_range (e.g., "630-650" -> 650)
      let newYear = 0
      const yearMatch = msg.year_range.match(/(\d+)$/)
      if (yearMatch) {
        newYear = parseInt(yearMatch[1], 10)
        setGameYear(newYear)
        setYear(newYear)
      }

      // Build log entry (without quotes yet)
      const logEntry: LogEntry = {
        year_range: msg.year_range,
        narrative: msg.writer_output.narrative,
        divergences: [...msg.writer_output.updated_divergences, ...msg.writer_output.new_divergences],
      }

      const newRulers = msg.ruler_updates_output.rulers
      setGameLogs(prev => {
        const newLogs = [...prev, logEntry]
        // Update timeline point to this new log
        setSelectedTimelinePoint({
          timeline: 'alternate',
          year: newYear,
          logIndex: newLogs.length - 1,
        })
        return newLogs
      })
      setGameRulers(newRulers)
      setGameDivergences(prev => [
        ...prev,
        ...msg.writer_output.new_divergences.filter(d => !prev.includes(d))
      ])
      setGameMerged(msg.writer_output.merged)

      // Initialize provinces from timeline event (full province state before geographer updates)
      // This gives us a complete map to display immediately
      const initialProvinces = msg.current_provinces || []
      if (initialProvinces.length > 0) {
        console.log('📍 Initializing provinces from timeline:', initialProvinces.length, 'provinces')
        setGameProvinces(initialProvinces)
      }

      // Create initial snapshot for this log entry (will be updated when geographer arrives)
      // Use functional update to get the correct log index
      setGameLogs(logs => {
        const logIndex = logs.length - 1
        setProvinceSnapshots(prevSnapshots => {
          // Ensure we have enough snapshot slots (pad with empty if needed)
          const newSnapshots = [...prevSnapshots]
          while (newSnapshots.length <= logIndex) {
            newSnapshots.push({ provinces: [], rulers: {}, divergences: [] })
          }
          // Set snapshot for this log entry
          newSnapshots[logIndex] = {
            provinces: initialProvinces,
            rulers: newRulers,
            divergences: logEntry.divergences,
          }
          console.log('📸 Created snapshot for log', logIndex, 'with', initialProvinces.length, 'provinces')
          return newSnapshots
        })
        return logs
      })

      // Main loop done - user can now trigger continue (isProcessing can be false)
      // But we keep streaming phase active to show other services are working
      setIsProcessing(false)
      checkStreamingComplete()
    }

    // Quotes update - quotes for the rulers
    onQuotesUpdate.current = (msg) => {
      console.log('💬 Quotes update received:', msg.quotes?.length || 0, 'quotes')
      updatesReceivedRef.current.quotes = true
      setStreamingPhase('illustrating')

      // Add quotes to the latest log entry
      setGameLogs(prev => {
        if (prev.length === 0) return prev
        const updated = [...prev]
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          quotes: msg.quotes,
        }
        return updated
      })
      checkStreamingComplete()
    }

    // Provinces update - map data (from Geographer service) - geographer is NOW DONE
    // NOTE: This contains only CHANGED provinces, not the full list
    onProvincesUpdate.current = (msg) => {
      console.log('🗺️ Provinces update received:', msg.provinces?.length || 0, 'province updates')
      updatesReceivedRef.current.provinces = true
      setGeographerComplete(true)  // Geographer has finished for this iteration

      // Clear geographer timeout since it completed
      if (geographerTimeoutRef.current) {
        clearTimeout(geographerTimeoutRef.current)
        geographerTimeoutRef.current = null
      }

      if (!msg.provinces || msg.provinces.length === 0) {
        checkStreamingComplete()
        return
      }

      // Merge province updates with existing provinces (geographer only sends changes)
      setGameProvinces(prevProvinces => {
        // Create a map of existing provinces by ID
        const provinceMap = new Map(prevProvinces.map(p => [p.id, p]))

        // Apply updates
        for (const update of msg.provinces) {
          provinceMap.set(update.id, update)
        }

        // Convert back to array
        const mergedProvinces = Array.from(provinceMap.values())
        console.log('📍 Merged provinces:', mergedProvinces.length, 'total,', msg.provinces.length, 'changed')

        // Update the snapshot for the latest log entry with merged provinces
        setGameLogs(logs => {
          if (logs.length > 0) {
            const logIndex = logs.length - 1
            setProvinceSnapshots(prevSnapshots => {
              const newSnapshots = [...prevSnapshots]
              // Update existing snapshot (or create if missing)
              if (newSnapshots[logIndex]) {
                newSnapshots[logIndex] = {
                  ...newSnapshots[logIndex],
                  provinces: mergedProvinces,
                }
              } else {
                // Shouldn't happen, but handle gracefully
                while (newSnapshots.length <= logIndex) {
                  newSnapshots.push({ provinces: [], rulers: {}, divergences: [] })
                }
                newSnapshots[logIndex] = {
                  provinces: mergedProvinces,
                  rulers: {},
                  divergences: logs[logIndex]?.divergences || [],
                }
              }
              console.log('📸 Updated snapshot', logIndex, 'with geographer changes')
              return newSnapshots
            })
          }
          return logs
        })

        return mergedProvinces
      })
      checkStreamingComplete()
    }

    // Portraits update - ruler portraits (last to arrive)
    onPortraitsUpdate.current = (msg) => {
      console.log('🎨 Portraits update received:', msg.portraits?.length || 0, 'portraits')
      updatesReceivedRef.current.portraits = true

      if (msg.status === 'success' && msg.portraits.length > 0) {
        // Merge portraits into the latest log's quotes
        setGameLogs(prev => {
          if (prev.length === 0) return prev
          const updated = [...prev]
          const latestLog = updated[updated.length - 1]
          if (latestLog.quotes) {
            updated[updated.length - 1] = {
              ...latestLog,
              quotes: latestLog.quotes.map(q => {
                const portrait = msg.portraits.find(
                  p => p.tag === q.tag && p.ruler_name === q.ruler_name
                )
                return portrait ? { ...q, portrait_base64: portrait.portrait_base64 } : q
              })
            }
          }
          return updated
        })
      }

      // All updates complete
      setStreamingPhase('complete')
      setTimeout(() => {
        setStreamingPhase('idle')
      }, 500)
    }

    // Cleanup timeouts on unmount
    return () => {
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current)
      }
      if (geographerTimeoutRef.current) {
        clearTimeout(geographerTimeoutRef.current)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [checkStreamingComplete]) // Include checkStreamingComplete

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      wsDisconnect()
    }
  }, [wsDisconnect])

  // Load default scenario data
  useEffect(() => {
    if (!scenarioId) return

    console.log('📂 Loading scenario data from:', BACKEND_URL)
    Promise.all([
      fetch(`${BACKEND_URL}/scenarios/${scenarioId}/provinces`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch(`${BACKEND_URL}/scenarios/${scenarioId}/rulers`, { cache: 'no-store' })
        .then(res => {
          if (!res.ok) throw new Error(`${res.status}`)
          return res.json()
        }),
      fetch(`${BACKEND_URL}/scenarios/${scenarioId}/metadata`, { cache: 'no-store' })
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

  // Start a new game (non-streaming, returns full state)
  const handleStartGame = useCallback(async (command: string, yearsToProgress: number) => {
    setIsProcessing(true)
    setInputError(null)
    setInputAlternative(null)
    setStreamingPhase('filtering')
    setGameYearsToProgress(yearsToProgress)  // Store the years for future Continue calls

    try {
      const url = `${BACKEND_URL}/start`
      console.log('🚀 Starting game - POST to:', url)
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command,
          scenario_id: scenarioId,
          years_to_progress: yearsToProgress
        })
      })
      console.log('📡 Response status:', response.status, response.statusText)

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

      const data = await response.json() as StartResponse

      // Check if rejected
      if (data.status === 'rejected') {
        setInputError(data.reason || 'Command was rejected')
        setInputAlternative(data.alternative || null)
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }

      // Success - extract all state from response
      const result = data.result
      const currentYear = result?.current_year || data.year || 0
      const logs = result?.logs || []
      const rulers = result?.rulers || {}
      const divergences = result?.divergences || [command]
      const provinces = result?.provinces || []
      const snapshots = result?.snapshots || []
      const nationTags = result?.nation_tags || {}
      const merged = result?.merged || false

      // Set game mode and create timeline branch immediately
      // WebSocket will fill in the actual content (logs, quotes, provinces, portraits)
      setGameMode(true)
      setGameId(data.game_id || null)
      setBranchStartYear(data.year || 0)
      setGameYear(currentYear)
      setGameMerged(merged)
      setGameLogs([])  // Start empty - WebSocket will fill
      setGameRulers({})  // Start empty - WebSocket will fill
      setGameDivergences(divergences)
      setGameProvinces([])  // Start empty - WebSocket will fill
      setProvinceSnapshots([])
      setGameNationTags(nationTags)
      setYear(currentYear)
      setSelectedTimelinePoint({
        timeline: 'alternate',
        year: currentYear,
        logIndex: 0
      })

      // Connect to WebSocket for real-time updates
      if (data.game_id) {
        console.log('🔌 Connecting WebSocket for game:', data.game_id)
        wsConnect(data.game_id)
      }

      // Keep processing/streaming active - WebSocket handlers will set to idle when complete
      setStreamingPhase('dreaming')
      // Note: isProcessing stays true until WebSocket delivers all updates
    } catch (err) {
      console.error('Error starting game:', err)
      setInputError('Failed to connect to server')
      setIsProcessing(false)
      setStreamingPhase('idle')
    }
  }, [scenarioId, wsConnect])

  // Continue the game - triggers backend workflow, WebSocket delivers updates
  const handleContinue = useCallback(async () => {
    if (!gameId) return

    setIsProcessing(true)
    setStreamingPhase('dreaming')

    try {
      const url = `${BACKEND_URL}/continue/${gameId}`
      console.log('🔄 Continuing game - POST to:', url)
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          years_to_progress: gameYearsToProgress
        })
      })
      console.log('📡 Response status:', response.status, response.statusText)

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

      // Response received - now wait for WebSocket updates
      // The WebSocket handlers will update state progressively
      console.log('✅ Continue request accepted, waiting for WebSocket updates...')

      // If WebSocket is not connected, fall back to parsing response directly
      if (wsStatus !== 'connected') {
        console.log('⚠️ WebSocket not connected, using response data directly')
        const data = await response.json() as ContinueResponse

        if (data.status === 'merged') {
          setGameMerged(true)
          setIsProcessing(false)
          setStreamingPhase('idle')
          return
        }

        const result = data.result
        const currentYear = data.current_year || gameYear
        const logs = data.logs || gameLogs
        const rulers = result?.rulers || gameRulers
        const divergences = result?.divergences || gameDivergences
        const provinces = result?.provinces || gameProvinces
        const snapshots = result?.snapshots || provinceSnapshots

        setGameYear(currentYear)
        setGameMerged(data.merged || false)
        setGameLogs(logs)
        setGameRulers(rulers)
        setGameDivergences(divergences)
        setGameProvinces(provinces)
        setProvinceSnapshots(snapshots)
        setYear(currentYear)
        setSelectedTimelinePoint({
          timeline: 'alternate',
          year: currentYear,
          logIndex: logs.length > 0 ? logs.length - 1 : 0
        })

        setIsProcessing(false)
        setStreamingPhase('idle')
      }
      // Otherwise, WebSocket handlers will manage state updates
    } catch (err) {
      console.error('Error continuing game:', err)
      setIsProcessing(false)
      setStreamingPhase('idle')
    }
  }, [gameId, gameYearsToProgress, wsStatus, gameYear, gameLogs, gameRulers, gameDivergences, gameProvinces, provinceSnapshots])

  // Add a new divergence to an existing timeline
  // If command is empty, just continue without adding a new divergence
  const handleAddDivergence = useCallback(async (command: string, yearsToProgress: number) => {
    if (!gameId) return

    setIsProcessing(true)
    setInputError(null)
    setInputAlternative(null)

    // Only filter if there's a command (new divergence)
    if (command) {
      setStreamingPhase('filtering')

      try {
        // First, filter the divergence to check if it's valid for the current era
        const filterUrl = `${BACKEND_URL}/game/${gameId}/filter-divergence`
        console.log('🔍 Filtering divergence - POST to:', filterUrl)
        const filterResponse = await fetch(filterUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command })
        })
        console.log('📡 Filter response status:', filterResponse.status, filterResponse.statusText)

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
      } catch (error) {
        console.error('Error filtering divergence:', error)
        setInputError('Failed to validate divergence')
        setIsProcessing(false)
        setStreamingPhase('idle')
        return
      }
    }

    // Continue with the new divergence (or just continue without one)
    setStreamingPhase('dreaming')

    try {
      const url = `${BACKEND_URL}/continue/${gameId}`
      console.log('➕ Adding divergence - POST to:', url)
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_divergences: command ? [command] : [],
          years_to_progress: yearsToProgress
        })
      })
      console.log('📡 Response status:', response.status, response.statusText)

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

      // Response received - WebSocket will deliver progressive updates
      console.log('✅ Continue request accepted, waiting for WebSocket updates...')

      // Fallback if WebSocket not connected
      if (wsStatus !== 'connected') {
        console.log('⚠️ WebSocket not connected, using response data directly')
        const data = await response.json() as ContinueResponse

        if (data.status === 'merged') {
          setGameMerged(true)
          setIsProcessing(false)
          setStreamingPhase('idle')
          return
        }

        const result = data.result
        const currentYear = data.current_year || gameYear
        const logs = data.logs || gameLogs
        const rulers = result?.rulers || gameRulers
        const divergences = result?.divergences || gameDivergences
        const provinces = result?.provinces || gameProvinces
        const snapshots = result?.snapshots || provinceSnapshots

        setGameYear(currentYear)
        setGameMerged(data.merged || false)
        setGameLogs(logs)
        setGameRulers(rulers)
        setGameDivergences(divergences)
        setGameProvinces(provinces)
        setProvinceSnapshots(snapshots)
        setYear(currentYear)
        setSelectedTimelinePoint({
          timeline: 'alternate',
          year: currentYear,
          logIndex: logs.length > 0 ? logs.length - 1 : 0
        })

        setIsProcessing(false)
        setStreamingPhase('idle')
      }
      // Otherwise WebSocket handlers manage state
    } catch (err) {
      console.error('Error adding divergence:', err)
      setInputError('Failed to connect to server')
      setIsProcessing(false)
      setStreamingPhase('idle')
    }
  }, [gameId, wsStatus, gameYear, gameLogs, gameRulers, gameDivergences, gameProvinces, provinceSnapshots])

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
              !geographerComplete &&
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
              isProcessing={isProcessing}
              streamingPhase={streamingPhase}
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

          {/* WebSocket connection status indicator */}
          {gameMode && (
            <div className="fixed bottom-4 left-4 z-40">
              <div className={`flex items-center gap-2 px-3 py-1 rounded text-xs font-mono ${
                wsStatus === 'connected' ? 'bg-green-900/80 text-green-300' :
                wsStatus === 'connecting' ? 'bg-yellow-900/80 text-yellow-300' :
                wsStatus === 'error' ? 'bg-red-900/80 text-red-300' :
                'bg-gray-900/80 text-gray-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  wsStatus === 'connected' ? 'bg-green-400' :
                  wsStatus === 'connecting' ? 'bg-yellow-400 animate-pulse' :
                  wsStatus === 'error' ? 'bg-red-400' :
                  'bg-gray-500'
                }`} />
                {wsStatus === 'connected' ? 'Live' :
                 wsStatus === 'connecting' ? 'Connecting...' :
                 wsStatus === 'error' ? 'Disconnected' : 'Offline'}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
