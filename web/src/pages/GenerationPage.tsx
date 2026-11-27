import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CanvasPlayer, type FrameStyle } from "../components/studio/CanvasPlayer";
import { CustomizationPanel } from "../components/studio/CustomizationPanel";
import { ExportDialog } from "../components/studio/ExportDialog";
import { useGeneration } from "../hooks/useGeneration";
import { cancelGeneration, deleteGeneration, insertFrame, regenerateGeneration, type Frame } from "../lib/api";
import type { CutoffMode } from "../lib/renderInk";

export function GenerationPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { generation, error } = useGeneration(id);
  const [fps, setFps] = useState(12);
  const [inkColor, setInkColor] = useState("#111312");
  const [backgroundColor, setBackgroundColor] = useState("#ffffff");
  const [cutoff, setCutoff] = useState<number | null>(null);
  const [cutoffMode, setCutoffMode] = useState<CutoffMode>("raw");
  const [frameStyles, setFrameStyles] = useState<Record<number, FrameStyle>>({});
  const [frames, setFrames] = useState<Frame[]>([]);
  const [regenCount, setRegenCount] = useState(1);
  const [regenBusy, setRegenBusy] = useState(false);
  const [insertingPos, setInsertingPos] = useState<number | null>(null);
  const [exportFormat, setExportFormat] = useState<"gif" | "png_zip">("gif");
  const [exportOpen, setExportOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const pending = generation?.status === "queued" || generation?.status === "running";
  const activeModels = [...new Set((generation?.frame_models ?? []).filter((name) => name !== "endpoint"))];

  useEffect(() => {
    if (!generation) return;
    setRegenCount(generation.total || 1);
    if (generation.status === "ready") {
      setFrames(generation.frames);
    } else {
      setFrames([]);
    }
  }, [generation?.id, generation?.status]);

  async function remove() {
    if (!id || !window.confirm("Delete this generation and its stored frames?")) return;
    await deleteGeneration(id);
    navigate("/history");
  }

  async function regenerate() {
    if (!generation?.start_asset_id || !generation?.end_asset_id) return;
    setRegenBusy(true);
    setNotice("");
    try {
      const job = await regenerateGeneration(generation.start_asset_id, generation.end_asset_id, regenCount);
      navigate(`/studio/${job.id}`);
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not start regeneration.");
    } finally {
      setRegenBusy(false);
    }
  }

  function moveFrame(position: number, direction: -1 | 1) {
    const target = position + direction;
    if (target < 0 || target >= frames.length) return;
    setFrames((current) => {
      const next = [...current];
      const [moved] = next.splice(position, 1);
      next.splice(target, 0, moved);
      return next;
    });
  }

  function removeFrame(position: number) {
    if (frames.length <= 2) return;
    setFrames((current) => current.filter((_, idx) => idx !== position));
  }

  async function addFrameAfter(position: number) {
    if (!id || position < 0 || position >= frames.length - 1) return;
    setInsertingPos(position);
    setNotice("");
    try {
      const left = frames[position];
      const right = frames[position + 1];
      const inserted = await insertFrame(id, left.index, right.index);
      setFrames((current) => {
        const next = [...current];
        next.splice(position + 1, 0, inserted);
        return next;
      });
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not insert in-between frame.");
    } finally {
      setInsertingPos(null);
    }
  }

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
        <header className="topbar"><div className="breadcrumbs"><Link to="/studio">Studio</Link><b>/</b><strong>Generation</strong></div><Link className="text-button" to="/history">All generations <span>↗</span></Link></header>
        <div className="generation-content">
          <div className="page-title-row">
            <div><span className="eyebrow">YOUR GENERATION</span><h1>{pending ? "Making something move." : generation?.status === "ready" ? "A little more alive." : "Generation details"}</h1><p>{id?.slice(0, 8)} · {generation?.stage ?? "Loading generation"}</p></div>
            {generation?.status === "ready" && <div className="export-actions"><button className="secondary-button" onClick={() => { setExportFormat("png_zip"); setExportOpen(true); }}>↓ PNG sequence</button><button className="generate-button" onClick={() => { setExportFormat("gif"); setExportOpen(true); }}>Export GIF <span>↗</span></button></div>}
          </div>
          {error && <div className="error-banner" role="alert"><span>!</span><div><strong>Couldn’t load generation</strong><p>{error}</p></div></div>}
          {pending && (
            <div className="progress-card">
              <div className="progress-orbit"><span /></div>
              <div className="progress-copy"><strong>{generation?.stage || "Preparing"}</strong><p>Keeping the sequence in order while the models work.</p></div>
              <span className="progress-count">{generation?.completed ?? 0}<i> / </i>{generation?.total ?? 0}</span>
              <div className="progress-track"><span style={{ width: generation?.total ? `${(generation.completed / generation.total) * 100}%` : "10%" }} /></div>
              <button className="text-button" onClick={() => id && void cancelGeneration(id)}>Cancel</button>
            </div>
          )}
          {generation?.status === "failed" && (
            <div className="error-banner" role="alert"><span>!</span><div><strong>{generation.error?.code ?? "Generation failed"}</strong><p>{generation.error?.detail ?? "See backend logs for more information."}</p></div></div>
          )}
          {generation?.status === "cancelled" && <div className="notice-banner">This generation was cancelled. <Link to="/studio">Start another</Link></div>}
          {generation?.status === "ready" && (
            <>
              <div className="result-layout">
                <section className="result-preview">
                  <div className="section-title-row"><div><h2>Frame sequence</h2><span>{frames.length} frames · {activeModels.join(" + ")}</span></div><span className="ready-pill"><i /> READY</span></div>
                  <CanvasPlayer
                    frames={frames}
                    fps={fps}
                    setFps={setFps}
                    showSettings
                    inkColor={inkColor}
                    setInkColor={setInkColor}
                    backgroundColor={backgroundColor}
                    setBackgroundColor={setBackgroundColor}
                    cutoff={cutoff}
                    setCutoff={setCutoff}
                    cutoffMode={cutoffMode}
                    setCutoffMode={setCutoffMode}
                    onFrameStylesChange={setFrameStyles}
                    onMoveFrame={moveFrame}
                    onRemoveFrame={removeFrame}
                    onInsertFrameAfter={(pos) => void addFrameAfter(pos)}
                    insertingPosition={insertingPos}
                  />
                </section>
                <div className="result-sidebar">
                  {generation.start_asset_id && generation.end_asset_id && (
                    <CustomizationPanel
                      count={regenCount}
                      setCount={setRegenCount}
                      disabled={regenBusy}
                      canGenerate={!regenBusy}
                      onGenerate={() => void regenerate()}
                      buttonLabel="Regenerate frames"
                    />
                  )}
                  <aside className="result-details">
                    <span className="eyebrow">MODEL</span>
                    <h3>Generation model</h3>
                    {activeModels.map((name, index) => (
                      <div className="route-step" key={name}>
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <div><strong>{name}</strong><small>{"GMA-guided InterFrames prediction"}</small></div>
                        <i>✓</i>
                      </div>
                    ))}
                    {generation.warnings.length > 0 && <div className="quality-note"><strong>Quality notes</strong>{generation.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>}
                    {notice && <p className="error-text">{notice}</p>}
                    <button className="danger-link" onClick={() => void remove()}>Delete generation</button>
                  </aside>
                </div>
              </div>
            </>
          )}
          {(generation?.status === "failed" || generation?.status === "cancelled") && generation.start_asset_id && generation.end_asset_id && (
            <div className="regen-fallback">
              <CustomizationPanel
                count={regenCount}
                setCount={setRegenCount}
                disabled={regenBusy}
                canGenerate={!regenBusy}
                onGenerate={() => void regenerate()}
                buttonLabel="Regenerate frames"
              />
            </div>
          )}
          {!generation && !error && <div className="loading-line"><span className="spinner" /> Loading generation…</div>}
        </div>
      </main>
      {exportOpen && generation && id && (
        <ExportDialog
          generationId={id}
          format={exportFormat}
          fps={fps}
          setFps={setFps}
          inkColor={inkColor}
          backgroundColor={backgroundColor}
          cutoff={cutoff}
          cutoffMode={cutoffMode}
          frameStyles={frameStyles}
          frameIndices={frames.map((item) => item.index)}
          onClose={() => setExportOpen(false)}
          onError={setNotice}
        />
      )}
    </div>
  );
}
