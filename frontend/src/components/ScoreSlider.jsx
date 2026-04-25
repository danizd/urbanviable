export default function ScoreSlider({ variable, value, onChange }) {
  return (
    <div className="slider-card">
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
        onChange={(event) => onChange(variable.key, Number(event.target.value))}
      />
      <small>{variable.description}</small>
    </div>
  );
}