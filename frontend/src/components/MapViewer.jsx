import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function MapViewer({ mapRef, onFeatureClick }) {
  const mapContainerRef = useRef(null);
  const sourceName = import.meta.env.VITE_REACT_APP_SOURCE_NAME || 'galicia-scouting';
  const tileUrl = import.meta.env.VITE_REACT_APP_TILE_URL !== undefined ? import.meta.env.VITE_REACT_APP_TILE_URL : '';

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
          
          const props = feature.properties;
          const nmun = props.NMUN || 'Municipio';
          const html = `
            <div style="padding: 8px; min-width: 150px;">
              <strong style="font-size: 14px;">${nmun}</strong>
              <div style="color: #666; font-size: 12px; margin-top: 4px;">
                Sección: ${props.cusec || '-'}
              </div>
              <div style="margin-top: 8px; font-size: 12px;">
                <div>Renta: ${props.renta_abs?.toLocaleString() || 0} €</div>
                <div>Actividad: ${props.actividad_abs || 0} estab.</div>
              </div>
            </div>
          `;
          
          new maplibregl.Popup()
            .setLngLat(event.lngLat)
            .setHTML(html)
            .addTo(map);
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