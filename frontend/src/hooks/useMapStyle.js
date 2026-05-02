import { useEffect, useRef } from 'react';

export function useMapStyle(mapRef, weights) {
  const layerCheckInterval = useRef(null);
  const timeoutRef = useRef(null);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.setPaintProperty !== 'function') {
      return;
    }

    const applyExpression = (retry = true) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        const vars = [
          'renta_norm',
          'densidad_norm',
          'jovenes_norm',
          'mayores_norm',
          'actividad_norm',
          'uso_comercial_norm',
          'antiguedad_norm',
        ];

        const activeVars = vars.filter(v => (weights[v] || 0) > 0);

        if (activeVars.length === 0) {
          if (map.getLayer('secciones-fill')) {
            map.setPaintProperty('secciones-fill', 'fill-color', 'rgba(80, 80, 100, 0.2)');
            map.setPaintProperty('secciones-fill', 'fill-opacity', 0.9);
          }
          return;
        }

        let scoreExpr = ['*', ['get', activeVars[0]], weights[activeVars[0]]];
        let totalWeight = weights[activeVars[0]];
        
        for (let i = 1; i < activeVars.length; i++) {
          const v = activeVars[i];
          const w = weights[v] || 0;
          scoreExpr = ['+', scoreExpr, ['*', ['get', v], w]];
          totalWeight += w;
        }

        if (totalWeight > 0 && activeVars.length > 1) {
          scoreExpr = ['/', scoreExpr, totalWeight];
        }

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
          map.setPaintProperty('secciones-fill', 'fill-opacity', 0.9);
        } else if (retry) {
          setTimeout(() => applyExpression(false), 100);
        }
      }, 100);
    };

    const waitForLayerAndApply = () => {
      if (map.getLayer('secciones-fill')) {
        applyExpression();
      } else {
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
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [mapRef, weights]);
}