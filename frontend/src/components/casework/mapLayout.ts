export type MapCoordinate = {
  key: string;
  lat: number;
  lon: number;
};

export type ProjectedMapCoordinate = MapCoordinate & {
  x: number;
  y: number;
};

const clamp = (value: number) => Math.min(92, Math.max(8, value));

/**
 * Project arbitrary case coordinates into the schematic map viewport.
 * Coordinates are deliberately relative to the supplied records: this is not
 * a geographic basemap and must not imply greater location precision.
 */
export function projectMapCoordinates(
  coordinates: MapCoordinate[],
): ProjectedMapCoordinate[] {
  const valid = coordinates.filter(
    ({ lat, lon }) => Number.isFinite(lat) && Number.isFinite(lon),
  );
  if (!valid.length) return [];

  const latitudes = valid.map(({ lat }) => lat);
  const longitudes = valid.map(({ lon }) => lon);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const latRange = maxLat - minLat;
  const lonRange = maxLon - minLon;

  return valid.map((coordinate) => ({
    ...coordinate,
    x: clamp(lonRange ? 8 + ((coordinate.lon - minLon) / lonRange) * 84 : 50),
    y: clamp(latRange ? 92 - ((coordinate.lat - minLat) / latRange) * 84 : 50),
  }));
}

/** Spread nearly identical marker positions just enough to keep every receipt selectable. */
export function spreadMapCoordinates(
  coordinates: ProjectedMapCoordinate[],
): ProjectedMapCoordinate[] {
  const placed: ProjectedMapCoordinate[] = [];
  for (const coordinate of coordinates) {
    const overlaps = placed.filter(
      (point) =>
        Math.hypot(point.x - coordinate.x, point.y - coordinate.y) < 3.2,
    ).length;
    if (!overlaps) {
      placed.push(coordinate);
      continue;
    }
    const angle = ((overlaps * 137.5 - 45) * Math.PI) / 180;
    const radius = Math.min(5, 2.4 + overlaps * 0.8);
    placed.push({
      ...coordinate,
      x: clamp(coordinate.x + Math.cos(angle) * radius),
      y: clamp(coordinate.y + Math.sin(angle) * radius),
    });
  }
  return placed;
}

/** Fan stacked geographic markers in screen pixels without changing their recorded coordinates. */
export function fanMarkerOffset(index: number, count: number) {
  if (count <= 1) return { x: 0, y: 0 };
  const radius = count === 2 ? 15 : 22;
  const angle = -Math.PI / 2 + (index * Math.PI * 2) / count;
  return {
    x: Math.round(Math.cos(angle) * radius),
    y: Math.round(Math.sin(angle) * radius),
  };
}
