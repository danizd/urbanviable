import { useEffect } from 'react';

export function useMapStyle(mapRef, weights) {
  useEffect(() => {
    const map = mapRef.current;
    if (!map || typeof map.setPaintProperty !== 'function') {
      return;
    }

    const applyExpression = () => {
      const activeEntries = Object.entries(weights).filter(([, value]) => value > 0);
      const totalWeight = activeEntries.reduce((sum, [, value]) => sum + value, 0);

      let fillColorExpression;

      if (totalWeight === 0) {
        fillColorExpression = 'rgba(80, 80, 100, 0.2)';
      } else {
        const terms = activeEntries.map(([key, value]) => [
          '*',
          ['to-number', ['get', key], 0],
          value / totalWeight,
        ]);
        const scoreExpr = terms.length === 1 ? terms[0] : ['+', ...terms];

        fillColorExpression = [
          'interpolate',
          ['linear'],
          scoreExpr,
          0,
          'rgba(60, 60, 80, 0.15)',
          0.3,
          'rgba(30, 120, 180, 0.55)',
          0.6,
          'rgba(255, 165, 0, 0.75)',
          1,
          'rgba(220, 20, 20, 0.9)',
        ];
      }

      if (map.getLayer('secciones-fill')) {
        map.setPaintProperty('secciones-fill', 'fill-color', fillColorExpression);
      }
    };

    if (typeof map.isStyleLoaded === 'function' && map.isStyleLoaded()) {
      applyExpression();
      return;
    }

    map.once('idle', applyExpression);

    return () => {
      map.off('idle', applyExpression);
    };
  }, [mapRef, weights]);
}
