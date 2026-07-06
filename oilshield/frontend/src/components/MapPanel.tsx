// MapPanel — a react-leaflet map wrapper for the Risk Radar (Requirement 4.1).
//
// Draws shipping corridors as colored polylines (colored by risk band via the
// shared `bandColor` helper) over free, OpenStreetMap-derived dark tiles
// (CARTO dark basemap, no API key required). Optional route polylines are drawn
// as thin dashed lines. Presentational: all geometry and colors come in as
// props. Leaflet's CSS is imported here so the tiles and panes render correctly.

import { MapContainer, TileLayer, Polyline, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { RiskBand } from "../types";
import { bandColor } from "../lib";

/** A corridor drawn as a band-colored polyline. */
export interface CorridorPolyline {
  id: string;
  name: string;
  /** Ordered [lat, lng] coordinate pairs. */
  positions: [number, number][];
  band: RiskBand;
}

/** An optional tanker route drawn as a thin dashed polyline. */
export interface RoutePolyline {
  id: string;
  name: string;
  positions: [number, number][];
  color?: string;
}

export interface MapPanelProps {
  corridors?: CorridorPolyline[];
  routes?: RoutePolyline[];
  /** Initial map center [lat, lng]. Defaults to the Arabian Sea region. */
  center?: [number, number];
  /** Initial zoom level. */
  zoom?: number;
  /** CSS height for the map container. */
  height?: number | string;
  className?: string;
}

// Center roughly over the Arabian Sea so India + the Gulf corridors are visible.
const DEFAULT_CENTER: [number, number] = [18, 58];
const DEFAULT_ZOOM = 4;

const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';

/** Leaflet map wrapper rendering band-colored corridor polylines. */
export function MapPanel({
  corridors = [],
  routes = [],
  center = DEFAULT_CENTER,
  zoom = DEFAULT_ZOOM,
  height = 360,
  className,
}: MapPanelProps) {
  return (
    <div
      className={`overflow-hidden rounded-lg border border-slate-200 ${className ?? ""}`}
      style={{ height }}
    >
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%", background: "#EEF2F4" }}
      >
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />

        {routes.map((route) => (
          <Polyline
            key={route.id}
            positions={route.positions}
            pathOptions={{
              color: route.color ?? "#64748b",
              weight: 1.5,
              opacity: 0.6,
              dashArray: "4 6",
            }}
          >
            <Tooltip sticky>{route.name}</Tooltip>
          </Polyline>
        ))}

        {corridors.map((corridor) => (
          <Polyline
            key={corridor.id}
            positions={corridor.positions}
            pathOptions={{
              color: bandColor(corridor.band),
              weight: 5,
              opacity: 0.9,
            }}
          >
            <Tooltip sticky>
              {corridor.name} — {corridor.band}
            </Tooltip>
          </Polyline>
        ))}
      </MapContainer>
    </div>
  );
}

export default MapPanel;
