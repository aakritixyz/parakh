import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import type { CorrelationResult } from "../../caseApi";
import { MapPin } from "lucide-react";
import styles from "./Casework.module.css";
import { fanMarkerOffset } from "./mapLayout";

type MapData = CorrelationResult["map"];
type Receipt = { evidence_id: number; reference: string };

type Props = {
  map: MapData;
  cursor: number;
  formatTime: (value?: string | null) => string;
  onOpenReceipt: (receipt: Receipt) => void;
};

function tooltip(lines: string[]) {
  const node = document.createElement("div");
  node.className = styles.mapTooltip;
  lines.forEach((line, index) => {
    const element = document.createElement(index === 0 ? "strong" : "span");
    element.textContent = line;
    node.appendChild(element);
  });
  return node;
}

export function EvidenceMap({ map, cursor, formatTime, onOpenReceipt }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const tileWarning = useRef<HTMLDivElement>(null);
  const gps = map.gps_trail.slice(
    0,
    Math.ceil((map.gps_trail.length * cursor) / 100),
  );
  const towers = map.towers.slice(
    0,
    Math.ceil((map.towers.length * cursor) / 100),
  );
  const towerGroups = Array.from(
    towers.reduce((groups, tower) => {
      const current = groups.get(tower.cell_id);
      if (current) current.count += 1;
      else groups.set(tower.cell_id, { tower, count: 1 });
      return groups;
    }, new Map<string, { tower: MapData["towers"][number]; count: number }>()),
  ).map(([, group], index) => ({ ...group, label: `T${index + 1}` }));
  const hasLocations = gps.length + towerGroups.length + map.stay_points.length > 0;
  const dataKey = useMemo(
    () => JSON.stringify({ gps, towerGroups, stays: map.stay_points }),
    [gps, towerGroups, map.stay_points],
  );
  const openReceipt = useRef(onOpenReceipt);
  const timeLabel = useRef(formatTime);

  openReceipt.current = onOpenReceipt;
  timeLabel.current = formatTime;

  useEffect(() => {
    if (!container.current || !hasLocations) return;
    if (tileWarning.current) tileWarning.current.hidden = true;

    const instance = L.map(container.current, {
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
    });
    instance.getContainer().setAttribute(
      "aria-label",
      "Interactive street map showing GPS records, route, stay clusters and telecom towers",
    );

    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
    tiles.on("tileerror", () => {
      if (tileWarning.current) tileWarning.current.hidden = false;
    });
    tiles.addTo(instance);

    const token = (name: string) =>
      getComputedStyle(document.documentElement).getPropertyValue(name).trim();

    const bounds: L.LatLngExpression[] = [];
    const fannedMarkers: {
      marker: L.Marker;
      actual: L.LatLng;
      offset: { x: number; y: number };
    }[] = [];
    const route = gps.map((point) => {
      const position: L.LatLngExpression = [Number(point.lat), Number(point.lon)];
      bounds.push(position);
      return position;
    });
    if (route.length > 1) {
      L.polyline(route, {
        color: token("--chart-teal"),
        weight: 5,
        opacity: 0.9,
        lineCap: "round",
        lineJoin: "round",
      })
        .bindTooltip("Recorded GPS sequence", { sticky: true })
        .addTo(instance);
    }

    map.stay_points.forEach((stay) => {
      const position: L.LatLngExpression = [Number(stay.lat), Number(stay.lon)];
      bounds.push(position);
      L.circle(position, {
        radius: Math.max(80, Math.min(300, stay.samples * 35)),
        color: token("--chart-blue"),
        weight: 2,
        dashArray: "6 5",
        fillColor: token("--accent-50"),
        fillOpacity: 0.34,
      })
        .bindTooltip(
          tooltip([
            `Stay cluster ${stay.cluster}`,
            `${stay.samples} samples`,
            `${timeLabel.current(stay.start)} – ${timeLabel.current(stay.end)}`,
          ]),
        )
        .addTo(instance);
    });

    towerGroups.forEach(({ tower, count, label }) => {
      const position: L.LatLngExpression = [Number(tower.lat), Number(tower.lon)];
      bounds.push(position);
      L.circle(position, {
        radius: Math.max(50, Number(tower.radius_m) || 0),
        color: token("--chart-violet"),
        weight: 2,
        dashArray: "7 6",
        fillColor: token("--chart-violet"),
        fillOpacity: 0.12,
      }).addTo(instance);
      const icon = L.divIcon({
        className: styles.leafletDivIcon,
        html: `<span class="${styles.leafletTowerPin}"><b>${label}</b><small>${count}</small></span>`,
        iconSize: [50, 36],
        iconAnchor: [25, 18],
      });
      L.marker(position, {
        icon,
        keyboard: true,
        title: `${tower.cell_id}, ${count} observations`,
        alt: `Tower ${tower.cell_id}`,
      })
        .bindTooltip(
          tooltip([
            `${label} · ${tower.cell_id}`,
            `${count} observation${count === 1 ? "" : "s"}`,
            `Coverage radius: ${tower.radius_m} m`,
            "Select to open receipt",
          ]),
          { direction: "top", offset: [0, -18] },
        )
        .on("click", () => openReceipt.current(tower.support))
        .addTo(instance);
    });

    const coordinateGroups = new Map<string, number[]>();
    gps.forEach((point, index) => {
      const key = `${Number(point.lat).toFixed(5)},${Number(point.lon).toFixed(5)}`;
      coordinateGroups.set(key, [...(coordinateGroups.get(key) ?? []), index]);
    });

    gps.forEach((point, index) => {
      const position: L.LatLngExpression = [Number(point.lat), Number(point.lon)];
      const coordinateKey = `${Number(point.lat).toFixed(5)},${Number(point.lon).toFixed(5)}`;
      const group = coordinateGroups.get(coordinateKey) ?? [index];
      const offset = fanMarkerOffset(group.indexOf(index), group.length);
      const endpoint = index === 0 ? "Start" : index === gps.length - 1 ? "Latest" : "";
      const icon = L.divIcon({
        className: styles.leafletDivIcon,
        html: `<span class="${styles.leafletGpsPin}${endpoint ? ` ${styles.leafletEndpoint}` : ""}"><b>${index + 1}</b></span>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });
      const marker = L.marker(position, {
        icon,
        keyboard: true,
        zIndexOffset: 1000 + index,
        title: `GPS record ${index + 1}${endpoint ? `, ${endpoint}` : ""}`,
        alt: `GPS record ${index + 1}`,
      })
        .bindTooltip(
          tooltip([
            `GPS ${index + 1}${endpoint ? ` · ${endpoint}` : ""}`,
            timeLabel.current(point.timestamp),
            `${Number(point.lat).toFixed(5)}, ${Number(point.lon).toFixed(5)}`,
            "Select to open receipt",
          ]),
          { direction: "top", offset: [0, -15] },
        )
        .on("click", () => openReceipt.current(point.support))
        .addTo(instance);
      fannedMarkers.push({ marker, actual: L.latLng(position), offset });
    });

    const positionStackedMarkers = () => {
      fannedMarkers.forEach(({ marker, actual, offset }) => {
        const actualPoint = instance.latLngToLayerPoint(actual);
        marker.setLatLng(
          instance.layerPointToLatLng(actualPoint.add(L.point(offset.x, offset.y))),
        );
      });
    };
    const fitEvidence = () => {
      instance.invalidateSize({ pan: false });
      if (bounds.length === 1) instance.setView(bounds[0], 15, { animate: false });
      else if (bounds.length > 1) {
        instance.fitBounds(L.latLngBounds(bounds), {
          padding: [60, 60],
          maxZoom: 15,
          animate: false,
        });
      }
      positionStackedMarkers();
    };
    instance.on("zoomend moveend", positionStackedMarkers);
    const fitFrame = requestAnimationFrame(fitEvidence);
    const resizeObserver = new ResizeObserver(fitEvidence);
    resizeObserver.observe(container.current);

    return () => {
      cancelAnimationFrame(fitFrame);
      resizeObserver.disconnect();
      instance.off("zoomend moveend", positionStackedMarkers);
      instance.remove();
    };
  }, [dataKey, hasLocations]);

  if (!hasLocations)
    return (
      <div className={`${styles.map} ${styles.mapEmpty}`} role="status">
        <MapPin />
        <strong>No location records found</strong>
        <span>Upload GPS history or tower records with coordinates to populate this view.</span>
      </div>
    );

  return (
    <>
      <div className={styles.mapGuide} aria-label="Map legend">
        <span><i className={styles.gpsKey}>1</i> Numbered GPS sequence</span>
        <span><i className={styles.routeKey} /> Recorded route</span>
        <span><i className={styles.stayKey} /> Stay-point cluster</span>
        <span><i className={styles.towerKey}>T</i> Tower and coverage</span>
      </div>
      <div className={styles.streetMapShell}>
        <div ref={container} className={styles.streetMap} />
        <div ref={tileWarning} className={styles.tileWarning} hidden role="status">
          Street tiles are unavailable. Evidence overlays remain usable; check the network connection.
        </div>
      </div>
      <p className={styles.mapPrivacyNote}>
        Street basemap © OpenStreetMap contributors. Loading tiles sends the viewed area to the tile provider. Repeated records at one coordinate are fanned slightly so each receipt remains selectable. Tower circles show coverage context, not a precise handset location.
      </p>
      <div className={styles.mapReading}>
        <div><strong>{gps.length}</strong><span>GPS points shown</span></div>
        <div><strong>{map.stay_points.length}</strong><span>Stay-point clusters</span></div>
        <div><strong>{towerGroups.length}</strong><span>Distinct towers</span></div>
        <p><strong>How to read this:</strong> zoom or drag the street map, then follow the numbered route from 1 to {gps.length}. Select any GPS or tower marker to open its source receipt.</p>
      </div>
      {towerGroups.length > 0 && (
        <div className={styles.towerDirectory}>
          {towerGroups.map(({ tower, count, label }) => (
            <span key={tower.cell_id}>
              <i>{label}</i><strong>{tower.cell_id}</strong>
              <small>{count} observation{count === 1 ? "" : "s"} · {tower.radius_m} m radius</small>
            </span>
          ))}
        </div>
      )}
    </>
  );
}
