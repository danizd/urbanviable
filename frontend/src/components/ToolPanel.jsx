import ScoreSlider from './ScoreSlider';
import Tooltip from './Tooltip';

export default function ToolPanel({ variables, weights, onWeightChange, feature, onClearFeature }) {
  return (
    <aside className="sidebar">
      <section className="sidebar-section">
        <h3>Scouting score</h3>
        <p>Ajusta qué importa para tu negocio y deja que el mapa responda al instante.</p>
      </section>

      <section className="sidebar-section">
        <h3>Variables</h3>
        {variables.map((variable) => (
          <ScoreSlider
            key={variable.key}
            variable={variable}
            value={weights[variable.key] ?? 0}
            onChange={onWeightChange}
          />
        ))}
      </section>

      <section className="sidebar-section">
        <h3>Información de zona</h3>
        <Tooltip feature={feature} onClose={onClearFeature} variables={variables} />
      </section>
    </aside>
  );
}