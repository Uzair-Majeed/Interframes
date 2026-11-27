import { Link, useNavigate } from "react-router-dom";
import type { Generation } from "../../lib/api";
import { apiUrl, deleteGeneration } from "../../lib/api";

export function GenerationRow({
  generation,
  onDeleted,
}: {
  generation: Generation;
  onDeleted: (id: string) => void;
}) {
  const navigate = useNavigate();
  const date = generation.created_at ? new Date(generation.created_at).toLocaleString() : "Recently";
  const thumbnail = generation.frames[Math.floor(generation.frames.length / 2)];

  async function handleDelete(event: React.MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!window.confirm("Delete this generation and its stored frames?")) return;
    await deleteGeneration(generation.id);
    onDeleted(generation.id);
  }

  return (
    <Link className="history-row" to={`/studio/${generation.id}`}>
      <div className="history-thumb">
        {thumbnail ? <img src={apiUrl(thumbnail.url)} alt="" /> : <span className="thumb-placeholder">✳</span>}
      </div>
      <div className="history-info"><strong>Untitled sequence</strong><span>{date} · {generation.id.slice(0, 8)}</span></div>
      <span className={`history-status ${generation.status}`}>{generation.status}</span>
      <span className="history-count">{generation.total} in-between</span>
      <div className="history-actions">
        <button
          type="button"
          className="regenerate-button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            navigate(`/studio/${generation.id}`);
          }}
        >
          ↺ Regenerate
        </button>
        <button
          type="button"
          className="delete-row-button"
          title="Delete generation"
          onClick={(event) => void handleDelete(event)}
        >
          × Delete
        </button>
      </div>
      <span className="row-arrow">↗</span>
    </Link>
  );
}
