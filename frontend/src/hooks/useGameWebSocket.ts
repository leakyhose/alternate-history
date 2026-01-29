/**
 * WebSocket hook for real-time game updates from the Aggregator service.
 *
 * Connects to ws://localhost:8001/ws/{gameId} and receives:
 * - timeline_update: Narrative, rulers, territorial changes
 * - quotes_update: Generated quotes for rulers
 * - provinces_update: Province ownership changes
 * - portraits_update: Generated ruler portraits
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AggregatorMessage,
  TimelineUpdateMessage,
  QuotesUpdateMessage,
  ProvincesUpdateMessage,
  PortraitsUpdateMessage,
  Quote,
  GameProvince,
  RulerInfo,
  LogEntry,
} from '@/types';

const AGGREGATOR_URL = process.env.NEXT_PUBLIC_AGGREGATOR_URL || 'ws://localhost:8001';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface PendingIteration {
  iteration: number;
  hasTimeline: boolean;
  hasQuotes: boolean;
  hasProvinces: boolean;
  hasPortraits: boolean;
  // Data as it arrives
  narrative?: string;
  yearRange?: string;
  rulers?: Record<string, RulerInfo>;
  divergences?: string[];
  territorialChanges?: TimelineUpdateMessage['cartographer_output']['territorial_changes'];
  quotes?: Quote[];
  provinces?: GameProvince[];
  merged?: boolean;
}

export interface UseGameWebSocketResult {
  // Connection state
  status: ConnectionStatus;
  connect: (gameId: string) => void;
  disconnect: () => void;

  // Iteration tracking
  pendingIterations: Map<number, PendingIteration>;
  completedIterations: Set<number>;

  // Latest data (convenience)
  latestLog: LogEntry | null;
  latestProvinces: GameProvince[] | null;
  latestRulers: Record<string, RulerInfo> | null;

  // Event handlers (set these to react to updates)
  onTimelineUpdate: React.MutableRefObject<((msg: TimelineUpdateMessage) => void) | null>;
  onQuotesUpdate: React.MutableRefObject<((msg: QuotesUpdateMessage) => void) | null>;
  onProvincesUpdate: React.MutableRefObject<((msg: ProvincesUpdateMessage) => void) | null>;
  onPortraitsUpdate: React.MutableRefObject<((msg: PortraitsUpdateMessage) => void) | null>;
}

export function useGameWebSocket(): UseGameWebSocketResult {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [pendingIterations, setPendingIterations] = useState<Map<number, PendingIteration>>(new Map());
  const [completedIterations, setCompletedIterations] = useState<Set<number>>(new Set());

  const [latestLog, setLatestLog] = useState<LogEntry | null>(null);
  const [latestProvinces, setLatestProvinces] = useState<GameProvince[] | null>(null);
  const [latestRulers, setLatestRulers] = useState<Record<string, RulerInfo> | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const gameIdRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Callback refs for event handlers
  const onTimelineUpdate = useRef<((msg: TimelineUpdateMessage) => void) | null>(null);
  const onQuotesUpdate = useRef<((msg: QuotesUpdateMessage) => void) | null>(null);
  const onProvincesUpdate = useRef<((msg: ProvincesUpdateMessage) => void) | null>(null);
  const onPortraitsUpdate = useRef<((msg: PortraitsUpdateMessage) => void) | null>(null);

  const updatePendingIteration = useCallback((iteration: number, updates: Partial<PendingIteration>) => {
    setPendingIterations(prev => {
      const newMap = new Map(prev);
      const current = newMap.get(iteration) || {
        iteration,
        hasTimeline: false,
        hasQuotes: false,
        hasProvinces: false,
        hasPortraits: false,
      };
      newMap.set(iteration, { ...current, ...updates });
      return newMap;
    });
  }, []);

  const checkIterationComplete = useCallback((iteration: number) => {
    setPendingIterations(prev => {
      const pending = prev.get(iteration);
      if (pending && pending.hasTimeline && pending.hasQuotes && pending.hasProvinces && pending.hasPortraits) {
        // Mark as complete
        setCompletedIterations(completed => new Set(completed).add(iteration));
        // Remove from pending
        const newMap = new Map(prev);
        newMap.delete(iteration);
        return newMap;
      }
      return prev;
    });
  }, []);

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message = JSON.parse(event.data) as AggregatorMessage | { type: 'ping' };

      // Handle ping/pong
      if (message.type === 'ping') {
        wsRef.current?.send('pong');
        return;
      }

      const aggregatorMsg = message as AggregatorMessage;
      const iteration = aggregatorMsg.iteration ?? 0;

      switch (aggregatorMsg.type) {
        case 'timeline_update': {
          const msg = aggregatorMsg as TimelineUpdateMessage;

          // Build log entry from timeline data
          const logEntry: LogEntry = {
            year_range: msg.year_range,
            narrative: msg.writer_output.narrative,
            divergences: [...msg.writer_output.updated_divergences, ...msg.writer_output.new_divergences],
          };

          setLatestLog(logEntry);
          setLatestRulers(msg.ruler_updates_output.rulers);

          updatePendingIteration(iteration, {
            hasTimeline: true,
            narrative: msg.writer_output.narrative,
            yearRange: msg.year_range,
            rulers: msg.ruler_updates_output.rulers,
            divergences: logEntry.divergences,
            territorialChanges: msg.cartographer_output.territorial_changes,
            merged: msg.writer_output.merged,
          });

          onTimelineUpdate.current?.(msg);
          checkIterationComplete(iteration);
          break;
        }

        case 'quotes_update': {
          const msg = aggregatorMsg as QuotesUpdateMessage;

          updatePendingIteration(iteration, {
            hasQuotes: true,
            quotes: msg.quotes,
          });

          // Update latest log with quotes
          setLatestLog(prev => prev ? { ...prev, quotes: msg.quotes } : null);

          onQuotesUpdate.current?.(msg);
          checkIterationComplete(iteration);
          break;
        }

        case 'provinces_update': {
          const msg = aggregatorMsg as ProvincesUpdateMessage;

          setLatestProvinces(msg.provinces);

          updatePendingIteration(iteration, {
            hasProvinces: true,
            provinces: msg.provinces,
          });

          onProvincesUpdate.current?.(msg);
          checkIterationComplete(iteration);
          break;
        }

        case 'portraits_update': {
          const msg = aggregatorMsg as PortraitsUpdateMessage;

          // Merge portraits into quotes
          if (msg.status === 'success' && msg.portraits.length > 0) {
            setLatestLog(prev => {
              if (!prev?.quotes) return prev;
              const updatedQuotes = prev.quotes.map(q => {
                const portrait = msg.portraits.find(
                  p => p.tag === q.tag && p.ruler_name === q.ruler_name
                );
                return portrait ? { ...q, portrait_base64: portrait.portrait_base64 } : q;
              });
              return { ...prev, quotes: updatedQuotes };
            });
          }

          updatePendingIteration(iteration, {
            hasPortraits: true,
          });

          onPortraitsUpdate.current?.(msg);
          checkIterationComplete(iteration);
          break;
        }
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }, [updatePendingIteration, checkIterationComplete]);

  const connect = useCallback((gameId: string) => {
    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    gameIdRef.current = gameId;
    setStatus('connecting');

    const ws = new WebSocket(`${AGGREGATOR_URL}/ws/${gameId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`WebSocket connected for game ${gameId}`);
      setStatus('connected');
    };

    ws.onmessage = handleMessage;

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setStatus('error');
    };

    ws.onclose = (event) => {
      console.log(`WebSocket closed: ${event.code} ${event.reason}`);
      setStatus('disconnected');

      // Auto-reconnect after 2 seconds if we still have a game ID
      if (gameIdRef.current && event.code !== 1000) {
        reconnectTimeoutRef.current = setTimeout(() => {
          if (gameIdRef.current) {
            console.log('Attempting to reconnect...');
            connect(gameIdRef.current);
          }
        }, 2000);
      }
    };
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    gameIdRef.current = null;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }

    setStatus('disconnected');
    setPendingIterations(new Map());
    setCompletedIterations(new Set());
    setLatestLog(null);
    setLatestProvinces(null);
    setLatestRulers(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
      }
    };
  }, []);

  return {
    status,
    connect,
    disconnect,
    pendingIterations,
    completedIterations,
    latestLog,
    latestProvinces,
    latestRulers,
    onTimelineUpdate,
    onQuotesUpdate,
    onProvincesUpdate,
    onPortraitsUpdate,
  };
}
