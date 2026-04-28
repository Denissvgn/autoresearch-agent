import { useEffect, useRef, useState, useCallback } from 'react';

export interface WSEvent {
  type: string;
  event?: string;
  research_id?: string;
  pipeline_id?: string;
  [key: string]: unknown;
}

export function useWebSocket() {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Map<string, Set<(e: WSEvent) => void>>>(new Map());

  useEffect(() => {
    let disposed = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (disposed) return;
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${proto}//${window.location.host}/ws/events`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
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
          if (!type || type === 'ping') return; // ignore server heartbeat
          const event: WSEvent = { ...rawEvent, type };
          setLastEvent(event);
          const handlers = listenersRef.current.get(event.type);
          if (handlers) handlers.forEach((fn: (e: WSEvent) => void) => fn(event));
          const allHandlers = listenersRef.current.get('*');
          if (allHandlers) allHandlers.forEach((fn: (e: WSEvent) => void) => fn(event));
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
