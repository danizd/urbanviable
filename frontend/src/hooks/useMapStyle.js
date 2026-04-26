import { useEffect, useRef } from 'react';

export function useMapStyle(mapRef, weights) {
  const layerCheckInterval = useRef(null);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.setPaintProperty !== 'function') {
      return;
    }

    const applyExpression = (retry = true) => {
      const activeEntries = Object.entries(weights).filter(([, value]) => value > 0);
      const totalWeight = activeEntries.reduce((sum, [, value]) => sum + value, 0);

      let fillColorExpression;

      if (totalWeight === 0) {
        fillColorExpression = 'rgba(80, 80, 100, 0.2)';
      } else {
       const terms = activeEntries.map(([key, value]) => {
           const propertyName = key;
           return [
             '*',
             ['to-number', ['get', propertyName], 0],
             value / totalWeight,
           ];
         });
        const scoreExpr = terms.length === 1 ? terms[0] : ['+', ...terms];

        fillColorExpression = [
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
      }

      if (map.getLayer('secciones-fill')) {
        map.setPaintProperty('secciones-fill', 'fill-color', fillColorExpression);
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
