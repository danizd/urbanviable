import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function MapViewer({ mapRef, onFeatureClick }) {
  const mapContainerRef = useRef(null);
  const sourceName = import.meta.env.REACT_APP_SOURCE_NAME || 'galicia-scouting';
  const layerName = import.meta.env.REACT_APP_LAYER_NAME || 'secciones';

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
      map.addSource(sourceName, {
        type: 'vector',
        url: `${import.meta.env.REACT_APP_TILE_URL || '/tiles'}/galicia-scouting.json`,
      });

      map.addLayer({
        id: 'secciones-fill',
        type: 'fill',
        source: sourceName,
        'source-layer': layerName,
        paint: {
          'fill-color': 'rgba(80, 80, 100, 0.2)',
          'fill-opacity': 0.9,
        },
      });

      map.addLayer({
        id: 'secciones-outline',
        type: 'line',
        source: sourceName,
        'source-layer': layerName,
        paint: {
          'line-color': 'rgba(255, 255, 255, 0.18)',
          'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0, 10, 0.7, 13, 1.1],
        },
      });

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
  }, [layerName, mapRef, onFeatureClick, sourceName]);

  return <div ref={mapContainerRef} className="map-canvas" />;
}