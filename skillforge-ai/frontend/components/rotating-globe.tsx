"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { geoDistance, geoGraticule10, geoOrthographic, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import world from "world-atlas/countries-110m.json";

type ActivityLocation = { label: string; lat: number; lon: number; count: number };
type ActivityResponse = {
  window_minutes: number;
  active_total: number;
  locations: ActivityLocation[];
  mode: "observed-aggregate" | "no-activity" | string;
  reason?: string;
};

type Rotation = [number, number, number];
const VIEW = 640;
const countries = feature(world as never, (world as unknown as { objects: { countries: never } }).objects.countries);

export function RotatingGlobe() {
  const [rotation, setRotation] = useState<Rotation>([-18, -12, 0]);
  const [activity, setActivity] = useState<ActivityResponse>({ window_minutes: 30, active_total: 0, locations: [], mode: "no-activity" });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef<{ x: number; y: number; rotation: Rotation } | null>(null);
  const resumeAt = useRef(0);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/activity/globe", { cache: "no-store" })
      .then(response => response.json())
      .then((body: ActivityResponse) => { if (!cancelled) setActivity(body); })
      .catch(() => { if (!cancelled) setActivity({ window_minutes: 30, active_total: 0, locations: [], mode: "no-activity", reason: "Activity feed unavailable" }); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) return;
    let frame = 0;
    let previous = performance.now();
    const tick = (now: number) => {
      const delta = now - previous;
      previous = now;
      if (!dragging && now >= resumeAt.current) {
        setRotation(current => [current[0] + delta * 0.0065, current[1], current[2]]);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [dragging]);

  const projection = useMemo(() => geoOrthographic()
    .translate([VIEW / 2, VIEW / 2])
    .scale(294)
    .clipAngle(90)
    .precision(0.2)
    .rotate(rotation), [rotation]);

  const path = useMemo(() => geoPath(projection), [projection]);
  const geographyPath = path(countries as never) ?? "";
  const graticulePath = path(geoGraticule10()) ?? "";
  const center: [number, number] = [-rotation[0], -rotation[1]];

  function onPointerDown(event: React.PointerEvent<SVGSVGElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStart.current = { x: event.clientX, y: event.clientY, rotation };
    setDragging(true);
  }

  function onPointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const start = dragStart.current;
    if (!start) return;
    const dx = event.clientX - start.x;
    const dy = event.clientY - start.y;
    const nextLat = Math.max(-70, Math.min(70, start.rotation[1] - dy * 0.28));
    setRotation([start.rotation[0] + dx * 0.32, nextLat, 0]);
  }

  function onPointerUp(event: React.PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    dragStart.current = null;
    setDragging(false);
    resumeAt.current = performance.now() + 3000;
  }

  const visibleMarkers = activity.locations.flatMap(location => {
    const distance = geoDistance(center, [location.lon, location.lat]);
    if (distance > Math.PI / 2) return [];
    const point = projection([location.lon, location.lat]);
    if (!point) return [];
    return [{ ...location, x: point[0], y: point[1], opacity: Math.max(0.18, 1 - distance / (Math.PI / 2)) }];
  });

  return <div className="sf-globe-block">
    <svg
      className={dragging ? "sf-globe dragging" : "sf-globe"}
      viewBox={`0 0 ${VIEW} ${VIEW}`}
      role="img"
      aria-label={activity.active_total > 0 ? `Rotating world map showing ${activity.active_total} recent aggregated learner sessions` : "Rotating world map. No recent aggregated learner activity is available."}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <defs>
        <radialGradient id="sf-globe-ocean" cx="38%" cy="28%" r="76%">
          <stop offset="0%" stopColor="rgba(154,140,255,.10)"/>
          <stop offset="58%" stopColor="rgba(154,140,255,.025)"/>
          <stop offset="100%" stopColor="rgba(255,255,255,.01)"/>
        </radialGradient>
        <filter id="sf-marker-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3.2" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <circle cx={VIEW / 2} cy={VIEW / 2} r="294" className="sf-globe-ocean" fill="url(#sf-globe-ocean)"/>
      <path d={graticulePath} className="sf-globe-graticule"/>
      <path d={geographyPath} className="sf-globe-land"/>
      <circle cx={VIEW / 2} cy={VIEW / 2} r="294" className="sf-globe-rim"/>
      {visibleMarkers.map(marker => <g key={`${marker.label}-${marker.lat}-${marker.lon}`} opacity={marker.opacity} transform={`translate(${marker.x} ${marker.y})`}>
        <circle r={8 + Math.min(marker.count, 8) * .55} className="sf-globe-marker-halo"/>
        <circle r={3.4} className="sf-globe-marker" filter="url(#sf-marker-glow)"/>
      </g>)}
    </svg>
    <div className="sf-globe-caption" aria-live="polite">
      {activity.active_total > 0 ? <><strong>{activity.active_total} recent sessions</strong><span>Coarse, privacy-preserving activity aggregated over the last {activity.window_minutes} minutes.</span></> : <><strong>Global practice, without fabricated activity.</strong><span>{activity.reason ?? "No recent observed aggregate learner activity is available yet."}</span></>}
    </div>
  </div>;
}
