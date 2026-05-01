import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function MapViewer({ mapRef, onFeatureClick }) {
  const mapContainerRef = useRef(null);
  const sourceName = import.meta.env.REACT_APP_SOURCE_NAME || 'galicia-scouting';
  const tileUrl = import.meta.env.REACT_APP_TILE_URL || '/tiles';

  useEffect(() => {
    if (mapRef.current || !mapContainerRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      center: [-7.8, 42.8],
      zoom: 7,
      minZoom: 6,
      maxZoom: 16,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-left');

    map.on('load', () => {
      const geojsonUrl = tileUrl + '/galicia_scouting.geojson';

      fetch(geojsonUrl)
        .then(response => response.json())
        .then(geojson => {
          map.addSource(sourceName, {
            type: 'geojson',
            data: geojson,
          });

          map.addLayer({
            id: 'secciones-fill',
            type: 'fill',
            source: sourceName,
            paint: {
              'fill-color': 'rgba(80, 80, 100, 0.2)',
              'fill-opacity': 0.9,
            },
          });

          map.addLayer({
            id: 'secciones-outline',
            type: 'line',
            source: sourceName,
            paint: {
              'line-color': 'rgba(255, 255, 255, 0.18)',
              'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0, 10, 0.7, 13, 1.1],
            },
          });
        })
        .catch(err => console.error('Error loading GeoJSON:', err));

      map.on('click', 'secciones-fill', (event) => {
        const feature = event.features?.[0];
        if (feature?.properties && onFeatureClick) {
          onFeatureClick(feature.properties);
        }
      });

      map.on('mouseenter', 'secciones-fill', () => {
        map.getCanvas().style.cursor = 'pointer';
      });

      map.on('mouseleave', 'secciones-fill', () => {
        map.getCanvas().style.cursor = '';
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [mapRef, onFeatureClick, sourceName, tileUrl]);

  return <div ref={mapContainerRef} className="map-canvas" />;
}