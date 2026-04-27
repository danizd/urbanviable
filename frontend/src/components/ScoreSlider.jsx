export default function ScoreSlider({ variable, value, onChange }) {
  const isEnabled = variable.enabled !== false;

  return (
    <div className={`slider-card ${isEnabled ? '' : 'disabled'}`}>
      <label>
        <span>{variable.label}</span>
        <span>{Math.round(value * 100)}%</span>
      </label>
      <input
        type="range"
        min="0"
        max="1"
        step="0.01"
        value={value}
        disabled={!isEnabled}
        onChange={(event) => onChange(variable.key, Number(event.target.value))}
      />
      <small>{variable.description}</small>
    </div>
  );
}