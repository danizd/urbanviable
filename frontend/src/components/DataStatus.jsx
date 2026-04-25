import { useEffect, useState } from 'react';
import { getDataStatus } from '../services/api';

export default function DataStatus() {
  const [status, setStatus] = useState(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let alive = true;

    getDataStatus()
      .then((data) => {
        if (alive) {
          setStatus(data);
          setHasError(false);
        }
      })
      .catch(() => {
        if (alive) {
          setHasError(true);
        }
      });

    return () => {
      alive = false;
    };
  }, []);

  if (hasError) {
    return null;
  }

  if (!status?.updated_at) {
    return <span className="badge">Datos no disponibles</span>;
  }

  const updatedAt = new Date(status.updated_at);
  const now = new Date();
  const ageInDays = (now - updatedAt) / (1000 * 60 * 60 * 24);
  const isWarning = ageInDays > 400;

  return <span className={`badge ${isWarning ? 'warning' : ''}`}>{isWarning ? '⚠️' : '✅'} Datos: {updatedAt.toLocaleDateString('es-ES')}</span>;
}