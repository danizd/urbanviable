import { Link } from 'react-router-dom';

export default function HowToUsePage() {
  return (
    <div className="home-container">
      <header className="home-header">
        <span className="home-logo">UrbanViable</span>
        <nav className="home-nav">
          <Link to="/">Inicio</Link>
          <Link to="/scouting">Scouting</Link>
        </nav>
      </header>
      <main className="page-copy">
        <h1>Cómo usar UrbanViable</h1>
        <p>
          Abre el mapa, mueve los sliders y observa cómo cambia el calor de las secciones censales sin esperar a consultas al servidor.
        </p>
        <h2>Flujo recomendado</h2>
        <ul>
          <li>Empieza por la renta y la densidad para filtrar el potencial de demanda.</li>
          <li>Después ajusta jóvenes, mayores y actividad para perfilar el tipo de zona.</li>
          <li>Usa el panel de información para comprobar valores absolutos antes de decidir.</li>
        </ul>
      </main>
    </div>
  );
}