import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import DataStatus from '../components/DataStatus';
import MapViewer from '../components/MapViewer';
import ToolPanel from '../components/ToolPanel';
import { DEFAULT_WEIGHTS, VARIABLES } from '../constants/variables';
import { useMapStyle } from '../hooks/useMapStyle';

export default function ScoutingPage() {
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [feature, setFeature] = useState(null);
  const mapRef = useRef(null);

  useMapStyle(mapRef, weights);

  const handleWeightChange = (key, value) => {
    if (key !== 'renta_norm') {
      return;
    }

    setWeights((current) => ({ ...current, [key]: value }));
  };

  return (
    <div className="scouting-layout">
      <header className="scouting-header">
        <strong>UrbanViable</strong>
        <nav>
          <Link to="/">Inicio</Link>
          <Link to="/como-usar">¿Cómo usar?</Link>
        </nav>
        <DataStatus />
      </header>
      <main className="scouting-main">
        <ToolPanel
          variables={VARIABLES}
          weights={weights}
          onWeightChange={handleWeightChange}
          feature={feature}
          onClearFeature={() => setFeature(null)}
        />
        <div className="map-shell">
          <MapViewer mapRef={mapRef} onFeatureClick={setFeature} />
        </div>
      </main>
    </div>
  );
}