"use client";

import { useEffect, useRef, useState, useCallback } from "react";

function getWsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/v1/alerts/ws`;
}

export interface WsAlert {
  id: string;
  wallet: string;
  market_question: string;
  action: string;
  category: string;
  price: number;
  position_size: number;
  wallet_score: number;
}

type ConnectionStatus = "connecting" | "connected" | "disconnected";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [alerts, setAlerts] = useState<WsAlert[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setStatus("connecting");

    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "alert") {
          setAlerts((prev) => [data.alert as WsAlert, ...prev].slice(0, 100));
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
