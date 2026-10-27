import { Link } from 'react-router-dom';

export function About() {
  return (
    <section>
      <div className="hero-banner">
        <span className="hero-badge">Sobre o Projeto</span>
        <h1 className="hero-title">Arquitetura e Tecnologias</h1>
        <p className="hero-description">
          Este projeto foi estruturado em formato monorepo integrando boas práticas de engenharia
          de software, containerização, CI/CD e observabilidade.
        </p>
        <Link to="/" className="btn-primary">
          &larr; Voltar para o Início
        </Link>
      </div>

      <div className="card-grid">
        <article className="card">
          <h2 className="card-title">Frontend Responsivo</h2>
          <p className="card-text">
            Desenvolvido com React, TypeScript, Vite e React Router, adotando design mobile-first e
            sistema de tokens CSS em <code>src/styles/theme.css</code>.
          </p>
        </article>

        <article className="card">
          <h2 className="card-title">Backend FastAPI</h2>
          <p className="card-text">
            Configuração tipada com <code>pydantic-settings</code>, documentação Swagger em{' '}
            <code>/docs</code> e logs JSON estruturados com <code>structlog</code>.
          </p>
        </article>

        <article className="card">
          <h2 className="card-title">DevOps &amp; Infra</h2>
          <p className="card-text">
            Ambientes com Docker Compose (hot reload em desenvolvimento e Caddy com HTTPS
            automático em staging) e pipeline de CI no Azure DevOps.
          </p>
        </article>
      </div>
    </section>
  );
}

