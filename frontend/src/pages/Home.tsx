import { Link } from 'react-router-dom';

export function Home() {
  return (
    <section>
      <div className="hero-banner">
        <span className="hero-badge">Controle Patrimonial &bull; Empréstimos</span>
        <h1 className="hero-title">Sistema de Gestão e Empréstimo de Equipamentos</h1>
        <p className="hero-description">
          Acompanhe a disponibilidade de notebooks, kits de laboratório, projetores e periféricos
          em tempo real, com histórico rastreável de retiradas e devoluções.
        </p>
        <Link to="/sobre" className="btn-primary">
          Conhecer o Sistema &rarr;
        </Link>
      </div>

      <div className="card-grid">
        <article className="card">
          <h2 className="card-title">Catálogo de Ativos</h2>
          <p className="card-text">
            Cadastro unificado de equipamentos com número de patrimônio, categoria, localização e
            estado de conservação.
          </p>
        </article>

        <article className="card">
          <h2 className="card-title">Fluxo de Empréstimos</h2>
          <p className="card-text">
            Registro ágil de solicitações, prazos de devolução, renovações e alertas automáticos
            para empréstimos em atraso.
          </p>
        </article>

        <article className="card">
          <h2 className="card-title">Observabilidade &amp; API</h2>
          <p className="card-text">
            Backend em FastAPI com documentação OpenAPI em <code>/docs</code>, healthcheck em{' '}
            <code>/health</code> e logs estruturados em JSON.
          </p>
        </article>
      </div>
    </section>
  );
}

