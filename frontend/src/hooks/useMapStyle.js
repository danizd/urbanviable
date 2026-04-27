import { useEffect, useRef } from 'react';

export function useMapStyle(mapRef, weights) {
  const layerCheckInterval = useRef(null);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.setPaintProperty !== 'function') {
      return;
    }

    const applyExpression = (retry = true) => {
      const rentaWeight = Number(weights.renta_norm || 0);
      const scoreExpr = ['to-number', ['get', 'renta_norm'], 0];

      const fillColorExpression = [
        'interpolate',
        ['linear'],
        scoreExpr,
        0,
        'rgba(30, 30, 50, 0.6)',
        0.25,
        'rgba(50, 120, 220, 0.8)',
        0.5,
        'rgba(255, 200, 0, 0.9)',
        0.75,
        'rgba(255, 100, 0, 0.95)',
        1,
        'rgba(220, 20, 60, 1)'
      ];

      if (map.getLayer('secciones-fill')) {
        map.setPaintProperty('secciones-fill', 'fill-color', fillColorExpression);
        map.setPaintProperty('secciones-fill', 'fill-opacity', Math.min(Math.max(rentaWeight, 0), 1));
      } else if (retry) {
        // La capa aún no existe, intentar de nuevo en 100ms
        setTimeout(() => applyExpression(false), 100);
      }
    };

    const waitForLayerAndApply = () => {
      if (map.getLayer('secciones-fill')) {
        applyExpression();
      } else {
        // La capa no está lista, iniciar un intervalo para verificar
        layerCheckInterval.current = setInterval(() => {
          if (map.getLayer('secciones-fill')) {
            applyExpression();
            if (layerCheckInterval.current) {
              clearInterval(layerCheckInterval.current);
              layerCheckInterval.current = null;
            }
          }
        }, 100);
      }
    };

    if (typeof map.isStyleLoaded === 'function' && map.isStyleLoaded()) {
      waitForLayerAndApply();
      return;
    }

    const onIdle = () => {
      waitForLayerAndApply();
    };

    map.once('idle', onIdle);

    return () => {
      map.off('idle', onIdle);
      if (layerCheckInterval.current) {
        clearInterval(layerCheckInterval.current);
      }
    };
  }, [mapRef, weights]);
}
