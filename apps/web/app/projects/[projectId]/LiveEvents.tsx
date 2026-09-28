"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { ProjectEvent } from "../../../lib/types";

const MAX_EVENTS = 30;

export function LiveEvents({
  projectId,
  initialEvents,
}: {
  projectId: string;
  initialEvents: ProjectEvent[];
}) {
  const [events, setEvents] = useState<ProjectEvent[]>(initialEvents);
  const [connected, setConnected] = useState(false);
  const lastEventId = useRef<string | null>(null);

  const streamUrl = useMemo(
    () =>
      "/api/titan/projects/" +
      projectId +
      "/events/stream" +
      (lastEventId.current
        ? "?cursor=" + encodeURIComponent(lastEventId.current)
        : ""),
    [projectId],
  );

  useEffect(() => {
    const source = new EventSource(streamUrl);

    source.onopen = () => setConnected(true);

    source.addEventListener("titan.event", (message) => {
      try {
        const event = JSON.parse(message.data) as ProjectEvent;
        lastEventId.current = message.lastEventId || event.occurred_at;

        setEvents((current) => {
          if (current.some((item) => item.id === event.id)) {
            return current;
          }
          return [event, ...current].slice(0, MAX_EVENTS);
        });
      } catch {
        // Ignore malformed event payloads; the stream remains alive.
      }
    });

    source.onerror = () => {
      setConnected(false);
    };

    return () => {
      source.close();
      setConnected(false);
    };
  }, [projectId, streamUrl]);

  return (
    <div className="card">
      <div className="row">
        <h2>Live events</h2>
        <span className={"badge " + (connected ? "success" : "")}>
          {connected ? "live" : "reconnecting"}
        </span>
      </div>

      <div className="stack" style={{ marginTop: 12 }}>
        {events.slice(0, 12).map((event) => (
          <div className="event" key={event.id}>
            <div className="row">
              <strong>{event.type}</strong>
              <span className="muted">{event.actor_type}</span>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {new Date(event.occurred_at).toLocaleString()}
            </div>
          </div>
        ))}

        {events.length === 0 ? (
          <p className="muted">Waiting for the first event.</p>
        ) : null}
      </div>
    </div>
  );
}
