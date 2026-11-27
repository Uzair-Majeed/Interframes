import { useEffect, useState } from "react";
import { listGenerations, type Generation } from "../../lib/api";
import { GenerationRow } from "./GenerationRow";

export function GenerationList() {
  const [items, setItems] = useState<Generation[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listGenerations()
      .then((response) => {
        setItems(response.items);
        setNextCursor(response.next_cursor);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Could not load history.");
      })
      .finally(() => setLoading(false));
  }, []);

  async function loadMore() {
    if (!nextCursor || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await listGenerations(nextCursor);
      setItems((current) => [...current, ...response.items]);
      setNextCursor(response.next_cursor);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Could not load more generations.");
    } finally {
      setLoading(false);
    }
  }

  if (loading && !items.length) {
    return <div className="loading-line"><span className="spinner" /> Loading your generations…</div>;
  }
  if (error && !items.length) {
    return <div className="error-banner"><span>!</span><p>{error}</p></div>;
  }
  if (!items.length) {
    return (
      <div className="history-empty">
        <span className="empty-spark">✳</span>
        <h2>Your canvas is waiting.</h2>
        <p>Your generated sequences will be saved here.</p>
        <a className="generate-button" href="/studio">Create your first sequence <span>↗</span></a>
      </div>
    );
  }

  return (
    <section className="history-list">
      <div className="history-list-head"><span className="history-head-seq">SEQUENCE</span><span>STATUS</span><span>FRAMES</span><span /><span /></div>
      {items.map((item) => (
        <GenerationRow
          key={item.id}
          generation={item}
          onDeleted={(deletedId) => setItems((current) => current.filter((row) => row.id !== deletedId))}
        />
      ))}
      {error && <div className="error-banner" role="alert"><span>!</span><p>{error}</p></div>}
      {nextCursor && (
        <button className="secondary-button" disabled={loading} onClick={() => void loadMore()}>
          {loading ? "Loading…" : "Load more"}
        </button>
      )}
    </section>
  );
}
