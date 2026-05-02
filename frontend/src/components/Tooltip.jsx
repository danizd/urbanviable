export default function Tooltip({ feature, onClose, variables }) {
  if (!feature) {
    return (
      <div className="tooltip-box">
        <strong>Información de zona</strong>
        <p>Haz clic en una sección del mapa para ver sus métricas.</p>
      </div>
    );
  }

  return (
    <div className="tooltip-box">
      <strong>{feature.NMUN || 'Municipio'}</strong>
      <small style={{ color: '#888' }}>Sección: {feature.cusec || 'sin código'}</small>
      <button type="button" className="map-floating-btn" onClick={onClose} style={{ marginBottom: 12 }}>
        Cerrar
      </button>
      <div className="tooltip-grid">
        {variables.map((variable) => (
          <div className="tooltip-row" key={variable.key}>
            <span>{variable.absLabel}</span>
            <span>{variable.absFormat(feature[variable.absKey])}</span>
          </div>
        ))}
      </div>
    </div>
  );
}