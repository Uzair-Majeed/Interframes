import { Link } from "react-router-dom";
import { GenerationList } from "../components/history/GenerationList";

export function HistoryPage() {
  return (
    <div className="app-shell">
      <aside className="side-nav">
        <a className="brand" href="/studio"><span className="brand-symbol"><i /><i /><i /></span><span>inter<span>frames</span></span></a>
        <div className="nav-caption">WORKSPACE</div>
        <Link className="nav-link" to="/studio"><span className="nav-glyph">◫</span> Studio</Link>
        <Link className="nav-link selected" to="/history"><span className="nav-glyph">▤</span> Your generations<span className="nav-current" /></Link>
        <div className="sidebar-bottom"><div className="local-card"><span className="local-pulse" /><div><strong>Local workspace</strong><small>Private on this device</small></div></div></div>
      </aside>
      <main className="main-area">
        <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><b>/</b><strong>Your generations</strong></div><Link className="secondary-button" to="/studio">＋ New sequence</Link></header>
        <div className="history-content">
          <div className="page-title-row"><div><span className="eyebrow">YOUR WORKSPACE</span><h1>Every <em>frame</em> has a story.</h1><p>Revisit, replay, and export your sequences.</p></div><span className="library-count">LOCAL LIBRARY <b>↗</b></span></div>
          <GenerationList />
        </div>
      </main>
    </div>
  );
}
