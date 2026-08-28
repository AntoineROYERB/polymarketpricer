"use client";

import { useEffect, useRef, useState, useCallback } from "react";

function getWsUrl(key: string) {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/v1/alerts/ws?api_key=${encodeURIComponent(key)}`;
}

export interface WsAlert {
  id: string;
  wallet: string;
  market_id: string;
  market_question: string;
  action: string;
  category: string;
  price: number;
  position_size: number;
  wallet_score: number;
  detected_at: string;
}

type ConnectionStatus = "connecting" | "connected" | "disconnected";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [alerts, setAlerts] = useState<WsAlert[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    // The server requires the key; connecting without one just gets closed with 4001.
    const key = localStorage.getItem("pm-api-key");
    if (!key) {
      setStatus("disconnected");
      return;
    }
    setStatus("connecting");

    const ws = new WebSocket(getWsUrl(key));
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "alert") {
          const payload = data.payload ?? data.alert;
          if (payload) {
            setAlerts((prev) => [payload as WsAlert, ...prev].slice(0, 200));
          }
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setStatus("disconnected");
      wsRef.current = null;
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("disconnected");
  }, []);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return { alerts, status, connect, disconnect };
}
