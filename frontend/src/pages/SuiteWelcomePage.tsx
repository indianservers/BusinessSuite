import { useRef, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Search } from "lucide-react";
import { modules } from "@/lib/moduleCatalog";
import SuiteHeader from "@/components/suite/SuiteHeader";
import "./module-dashboard.css";

export default function SuiteWelcomePage() {
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const visible = modules.filter((m) =>
    `${m.name} ${m.label} ${m.description}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  return (
    <div className="module-dashboard suite-public">
      <a className="suite-skip" href="#suite-main">
        Skip to content
      </a>
      <SuiteHeader />
      <main className="md-main" id="suite-main" tabIndex={-1}>
        <section className="suite-public-hero">
          <p className="md-eyebrow">One account. Six connected applications.</p>
          <h1>
            Your work <span>starts here.</span>
          </h1>
          <p>
            Explore your applications, then sign in with your Business Suite
            account. Your organization determines which applications you can
            access.
          </p>
          <Link className="suite-primary" to="/login">
            Sign in to your workspace <ArrowRight size={17} />
          </Link>
        </section>
        <div className="md-section-head">
          <h2>Explore applications</h2>
          <label className="md-search">
            <Search size={18} />
            <input
              ref={search}
              aria-label="Search applications"
              placeholder="Find an application…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <kbd>Ctrl K</kbd>
          </label>
        </div>
        <div className="md-grid">
          {visible.map((m) => {
            const Icon = m.icon;
            return (
              <article key={m.key} className={`md-card md-${m.key}`}>
                <div className="md-card-top">
                  <span className="md-icon">
                    <Icon size={36} />
                  </span>
                </div>
                <h3>{m.name}</h3>
                <p className="md-category">{m.label}</p>
                <p className="md-description">{m.description}</p>
                <Link
                  className="md-open"
                  to={`/login?next=${encodeURIComponent(m.homePath)}`}
                  aria-label={`Sign in to ${m.name}`}
                >
                  Sign in to open <ArrowRight size={16} />
                </Link>
              </article>
            );
          })}
        </div>
        {!visible.length && (
          <div className="md-empty" role="status">
            <h2>No matching applications</h2>
            <button onClick={() => setQuery("")}>Show all applications</button>
          </div>
        )}
        <footer className="suite-public-footer">
          <Link to="/help">Help & support</Link>
          <span>Business Suite · One connected workspace</span>
        </footer>
      </main>
    </div>
  );
}
