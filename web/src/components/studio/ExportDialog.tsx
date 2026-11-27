import { useState, type FormEvent } from "react";
import { apiUrl, createExport } from "../../lib/api";
import type { CutoffMode } from "../../lib/renderInk";
import type { FrameStyle } from "./CanvasPlayer";

type Props = {
  generationId: string;
  format: "gif" | "png_zip";
  fps: number;
  setFps: (value: number) => void;
  inkColor: string;
  backgroundColor: string;
  cutoff: number | null;
  cutoffMode: CutoffMode;
  frameStyles: Record<number, FrameStyle>;
  frameIndices?: number[];
  onClose: () => void;
  onError: (message: string) => void;
};

export function ExportDialog({
  generationId,
  format,
  fps,
  setFps,
  inkColor,
  backgroundColor,
  cutoff,
  cutoffMode,
  frameStyles,
  frameIndices,
  onClose,
  onError,
}: Props) {
  const [width, setWidth] = useState(512);
  const [height, setHeight] = useState(512);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    onError("");
    try {
      const result = await createExport(generationId, {
        format,
        width,
        height,
        fps,
        ink_color: inkColor,
        background_color: backgroundColor,
        cutoff,
        cutoff_mode: cutoffMode,
        frame_indices: frameIndices,
        frame_styles: Object.fromEntries(Object.entries(frameStyles).map(([index, style]) => [index, {
          ink_color: style.inkColor,
          background_color: style.backgroundColor,
          cutoff: style.cutoff,
          cutoff_mode: style.cutoffMode,
        }])),
      });
      window.location.assign(apiUrl(result.download_url));
      onClose();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Export failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <form className="export-dialog" role="dialog" aria-modal="true" aria-labelledby="export-title" onSubmit={(event) => void submit(event)}>
        <div className="dialog-heading">
          <div><span className="eyebrow">FINAL TOUCHES</span><h2 id="export-title">Export sequence</h2></div>
          <button type="button" className="dialog-close" aria-label="Close export dialog" onClick={onClose}>×</button>
        </div>
        <p>Using your current preview ink, background, and cutoff settings.</p>
        <div className="dialog-grid">
          <label><span>Width</span><input type="number" min="16" max="2048" value={width} onChange={(event) => setWidth(Number(event.target.value))} /></label>
          <label><span>Height</span><input type="number" min="16" max="2048" value={height} onChange={(event) => setHeight(Number(event.target.value))} /></label>
          {format === "gif" && (
            <label className="export-fps"><span>Playback speed · {fps} FPS</span><input type="range" min="1" max="60" value={fps} onChange={(event) => setFps(Number(event.target.value))} /></label>
          )}
        </div>
        <div className="dialog-footer">
          <span>{format === "gif" ? "Animated GIF" : "Numbered PNG ZIP"}</span>
          <div><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="generate-button" disabled={busy}>{busy ? "Rendering..." : "Create export"} <span>↗</span></button></div>
        </div>
      </form>
    </div>
  );
}
