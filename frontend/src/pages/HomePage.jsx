import { Link } from 'react-router-dom';

export default function HomePage() {
  return (
    <div className="home-container">
      <header className="home-header">
        <span className="home-logo">UrbanViable</span>
        <nav className="home-nav">
          <Link to="/scouting">Scouting</Link>
          <Link to="/como-usar">¿Cómo usar?</Link>
        </nav>
      </header>
      <main className="home-hero">
        <div className="home-hero-inner">
          <span className="home-kicker">Inteligencia de ubicación para Galicia</span>
          <h1>Descubre dónde abrir mejor.</h1>
          <p>
            Ajusta qué te importa para tu negocio y visualiza, en tiempo real, las secciones censales con mayor atractivo comercial.
          </p>
          <Link to="/scouting" className="btn-cta">
            Explorar el mapa
          </Link>
        </div>
      </main>
    </div>
  );
}