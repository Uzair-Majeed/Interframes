import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CustomizationPanel } from "../components/studio/CustomizationPanel";
import { EndpointUpload } from "../components/studio/EndpointUpload";
import { CanvasPlayer } from "../components/studio/CanvasPlayer";
import { createGeneration, uploadAsset, type EndpointInput } from "../lib/api";

type Slot = { value: EndpointInput | null; preview: string | null };

export function StudioPage() {
  const navigate = useNavigate();
  const [start, setStart] = useState<Slot>({ value: null, preview: null });
  const [end, setEnd] = useState<Slot>({ value: null, preview: null });
  const [count, setCount] = useState(1);
  const [fps, setFps] = useState(12);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function choose(slot: "start" | "end", file: File) {
    setError("");
    const preview = URL.createObjectURL(file);
    if (slot === "start") setStart({ value: null, preview });
    else setEnd({ value: null, preview });

    setBusy(true);
    try {
      const asset = await uploadAsset(file);
      const value = { asset };
      if (slot === "start") setStart({ value, preview });
      else setEnd({ value, preview });
    } catch (reason) {
      if (slot === "start") setStart({ value: null, preview: null });
      else setEnd({ value: null, preview: null });
      URL.revokeObjectURL(preview);
      setError(reason instanceof Error ? reason.message : "The image could not be uploaded.");
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!start.value || !end.value) return;
    setBusy(true);
    setError("");
    try {
      const job = await createGeneration(start.value, end.value, count);
      navigate(`/studio/${job.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start generation.");
    } finally {
      setBusy(false);
    }
  }

  function swap() {
    setStart(end);
    setEnd(start);
  }

  const canGenerate = Boolean(start.value && end.value) && !busy;
  return (
    <div className="app-shell">
      <aside className="side-nav">
        <a className="brand" href="/studio" aria-label="InterFrames studio">
          <span className="brand-symbol"><i /><i /><i /></span>
          <span>inter<span>frames</span></span>
        </a>
        <div className="nav-caption">WORKSPACE</div>
        <a className="nav-link selected" href="/studio"><span className="nav-glyph">✦</span> Studio <span className="nav-current" /></a>
        <a className="nav-link" href="/history"><span className="nav-glyph">▤</span> Your generations</a>
        <div className="sidebar-bottom">
          <div className="local-card"><span className="local-pulse" /><div><strong>Local workspace</strong><small>Private on this device</small></div></div>
          <div className="profile-row"><span className="avatar">IF</span><span><strong>My workspace</strong><small>Personal</small></span><span className="more">···</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><b>/</b><strong>Studio</strong></div>
          <div className="topbar-right"><span className="secure-label"><span /> Local processing</span><button className="help-button" title="Model and moderation setup is documented in the README">?</button></div>
        </header>

        <div className="studio-content">
          <div className="page-title-row">
            <div>
              <span className="eyebrow">FRAME INTERPOLATION WORKSPACE</span>
              <h1>Give your drawings <em>motion.</em></h1>
            </div>
            <div className="step-chip"><span>01</span> Create sequence</div>
          </div>

          <div className="studio-layout">
            <section className="work-column">
              <div className="section-title-row">
                <div><h2>Your sequence</h2></div>
                <button className="swap-button" onClick={swap} disabled={!start.preview && !end.preview}>⇄ <span>Swap</span></button>
              </div>
              <div className="endpoint-row">
                <EndpointUpload label="START FRAME" number="A" endpoint={start.value} preview={start.preview} busy={busy} onChoose={(file) => void choose("start", file)} />
                <div className="flow-connector"><span /><i>→</i><span /></div>
                <EndpointUpload label="END FRAME" number="B" endpoint={end.value} preview={end.preview} busy={busy} onChoose={(file) => void choose("end", file)} />
              </div>
              <div className="preview-heading"><div><h2>Preview</h2></div></div>
              <CanvasPlayer frames={[]} fps={fps} setFps={setFps} />
            </section>

            <CustomizationPanel
              count={count}
              setCount={setCount}
              disabled={busy}
              canGenerate={canGenerate}
              onGenerate={() => void generate()}
            />
          </div>

          {error && <div className="error-banner" role="alert"><span>!</span><div><strong>Couldn’t continue</strong><p>{error}</p></div><button onClick={() => setError("")}>×</button></div>}
        </div>
      </main>
    </div>
  );
}
