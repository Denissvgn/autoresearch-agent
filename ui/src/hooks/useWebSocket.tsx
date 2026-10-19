import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { getAutoresearchWebSocketProtocols } from '../api/client';

export interface WSEvent {
  type: string;
  event?: string;
  research_id?: string;
  pipeline_id?: string;
  [key: string]: unknown;
}

interface WebSocketContextValue {
  connected: boolean;
  lastEvent: WSEvent | null;
  on: (type: string, handler: (e: WSEvent) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

function useWebSocketState(): WebSocketContextValue {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Map<string, Set<(e: WSEvent) => void>>>(new Map());
  const cursorRef = useRef<number>(0);
  const seenOpenRef = useRef(false);

  useEffect(() => {
    let disposed = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function dispatch(event: WSEvent) {
      const handlers = listenersRef.current.get(event.type);
      if (handlers) handlers.forEach((fn: (e: WSEvent) => void) => fn(event));
      const allHandlers = listenersRef.current.get('*');
      if (allHandlers) allHandlers.forEach((fn: (e: WSEvent) => void) => fn(event));
    }

    function connect() {
      if (disposed) return;
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      // cursor-based reconnect: replay from the last seen sequence; when
      // the cursor has expired the server answers with a resync plan
      const cursor = cursorRef.current;
      const cursorParam = cursor > 0 ? `?cursor=${cursor}` : '';
      const url = `${proto}//${window.location.host}/ws/events${cursorParam}`;
      const protocols = getAutoresearchWebSocketProtocols();
      const ws = protocols ? new WebSocket(url, protocols) : new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // a reconnect restores authoritative state through a resync: the
        // consumers refetch instead of trusting stale client state
        if (seenOpenRef.current) {
          const resync: WSEvent = {
            type: 'resync',
            reason: 'reconnected',
            cursor,
          };
          setLastEvent(resync);
          dispatch(resync);
        }
        seenOpenRef.current = true;
      };
      ws.onclose = () => {
        setConnected(false);
        if (!disposed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
      ws.onmessage = (msg) => {
        try {
          const rawEvent = JSON.parse(msg.data) as WSEvent;
          const type = rawEvent.type ?? rawEvent.event;
          if (!type || type === 'ping') return;
          const event: WSEvent = { ...rawEvent, type };
          const sequence = Number(event.sequence ?? event.cursor ?? 0);
          if (Number.isFinite(sequence) && sequence > cursorRef.current) {
            cursorRef.current = sequence;
          }
          setLastEvent(event);
          dispatch(event);
          // the server's catchup plan: expired cursors force a resync
          if (type === 'catchup' && event.mode === 'resync') {
            const resync: WSEvent = {
              type: 'resync',
              reason: 'cursor_expired',
              cursor: cursorRef.current,
            };
            setLastEvent(resync);
            dispatch(resync);
          }
        } catch {
          // ignore non-JSON
        }
      };
    }

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, []);

  const on = useCallback((type: string, handler: (e: WSEvent) => void) => {
    if (!listenersRef.current.has(type)) {
      listenersRef.current.set(type, new Set());
    }
    listenersRef.current.get(type)!.add(handler);
    return () => {
      listenersRef.current.get(type)?.delete(handler);
    };
  }, []);

  return { connected, lastEvent, on };
}

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const value = useWebSocketState();
  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocket() {
  const value = useContext(WebSocketContext);
  if (!value) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return value;
}
