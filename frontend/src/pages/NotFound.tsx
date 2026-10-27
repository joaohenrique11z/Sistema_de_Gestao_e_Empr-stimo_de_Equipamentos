import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <section className="not-found-box">
      <div className="not-found-code">404</div>
      <h1 className="hero-title">Página não encontrada</h1>
      <p className="hero-description">
        O endereço que você tentou acessar não existe ou foi movido.
      </p>
      <Link to="/" className="btn-primary">
        Voltar para a Página Inicial
      </Link>
    </section>
  );
}

