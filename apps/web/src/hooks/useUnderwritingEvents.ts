"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CreditUnderwritingEvent } from "@/types/underwriting";
import { getUnderwritingEventsUrl } from "@/lib/api";

interface UseUnderwritingEventsOptions {
  onEvent?: (event: CreditUnderwritingEvent) => void;
  enabled?: boolean;
}

export function useUnderwritingEvents(options: UseUnderwritingEventsOptions = {}) {
  const { onEvent, enabled = true } = options;
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [events, setEvents] = useState<CreditUnderwritingEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<CreditUnderwritingEvent | null>(null);
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLastEvent(null);
  }, []);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") {
      return;
    }

    const url = getUnderwritingEventsUrl();
    const eventSource = new EventSource(url);

    eventSource.onopen = () => {
      setIsConnected(true);
    };

    const handleMessage = (e: MessageEvent) => {
      try {
        const parsed: CreditUnderwritingEvent = JSON.parse(e.data);
        setLastEvent(parsed);
        setEvents((prev) => [parsed, ...prev.slice(0, 49)]);
        if (onEventRef.current) {
          onEventRef.current(parsed);
        }
      } catch (err) {
        console.error("Error al parsear evento SSE:", err);
      }
    };

    // FastAPI envía `event: credit_event`
    eventSource.addEventListener("credit_event", handleMessage);
    eventSource.onmessage = handleMessage;

    eventSource.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      eventSource.removeEventListener("credit_event", handleMessage);
      eventSource.close();
      setIsConnected(false);
    };
  }, [enabled]);

  return {
    isConnected,
    events,
    lastEvent,
    clearEvents,
  };
}
