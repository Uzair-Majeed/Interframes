import { useEffect, useRef, useState } from "react";
import type { Frame } from "../../lib/api";
import { apiUrl } from "../../lib/api";
import { colorizeFrame, type CutoffMode } from "../../lib/renderInk";

export type FrameStyle = {
  inkColor: string;
  backgroundColor: string;
  cutoff: number | null;
  cutoffMode: CutoffMode;
};

type Props = {
  frames: Frame[];
  fps: number;
  setFps: (value: number) => void;
  showSettings?: boolean;
  inkColor?: string;
  setInkColor?: (value: string) => void;
  backgroundColor?: string;
  setBackgroundColor?: (value: string) => void;
  cutoff?: number | null;
  setCutoff?: (value: number | null) => void;
  cutoffMode?: CutoffMode;
  setCutoffMode?: (value: CutoffMode) => void;
  onFrameStylesChange?: (styles: Record<number, FrameStyle>) => void;
  onMoveFrame?: (position: number, direction: -1 | 1) => void;
  onRemoveFrame?: (position: number) => void;
  onInsertFrameAfter?: (position: number) => void;
  insertingPosition?: number | null;
};

export function CanvasPlayer({
  frames, fps, setFps, showSettings = false,
  inkColor = "#111312", setInkColor = () => {},
  backgroundColor = "#ffffff", setBackgroundColor = () => {},
  cutoff = null, setCutoff = () => {},
  cutoffMode = "raw", setCutoffMode = () => {}, onFrameStylesChange,
  onMoveFrame, onRemoveFrame, onInsertFrameAfter, insertingPosition = null,
}: Props) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [applyToAllFrames, setApplyToAllFrames] = useState(true);
  const [frameStyles, setFrameStyles] = useState<Record<number, FrameStyle>>({});
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    setIndex((current) => (frames.length ? Math.min(current, frames.length - 1) : 0));
  }, [frames.length]);
  useEffect(() => {
    setFrameStyles({});
    setApplyToAllFrames(true);
    onFrameStylesChange?.({});
  }, [frames[0]?.url]);
  useEffect(() => {
    if (!playing || frames.length < 2) return;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % frames.length), 1000 / fps);
    return () => window.clearInterval(timer);
  }, [playing, frames.length, fps]);

  const frame = frames[index];
  const styleKey = frame?.index ?? index;
  const frameStyle = applyToAllFrames
    ? { inkColor, backgroundColor, cutoff, cutoffMode }
    : frameStyles[styleKey] ?? { inkColor, backgroundColor, cutoff, cutoffMode };

  function updateFrameStyle<K extends keyof FrameStyle>(key: K, value: FrameStyle[K]) {
    if (applyToAllFrames) {
      if (key === "inkColor") setInkColor(value as string);
      if (key === "backgroundColor") setBackgroundColor(value as string);
      if (key === "cutoff") setCutoff(value as number | null);
      if (key === "cutoffMode") setCutoffMode(value as CutoffMode);
      return;
    }
    const updated = {
      ...frameStyles,
      [styleKey]: { ...(frameStyles[styleKey] ?? { inkColor, backgroundColor, cutoff, cutoffMode }), [key]: value },
    };
    setFrameStyles(updated);
    onFrameStylesChange?.(updated);
  }
  function updateMode(nextMode: CutoffMode) {
    const nextCutoff = nextMode === "raw" ? null : (frameStyle.cutoff ?? 0.5);
    if (applyToAllFrames) {
      setCutoffMode(nextMode);
      setCutoff(nextCutoff);
      return;
    }
    const updated = {
      ...frameStyles,
      [styleKey]: {
        ...(frameStyles[styleKey] ?? { inkColor, backgroundColor, cutoff, cutoffMode }),
        cutoffMode: nextMode,
        cutoff: nextCutoff,
      },
    };
    setFrameStyles(updated);
    onFrameStylesChange?.(updated);
  }
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !frame) return;
    const image = new Image();
    image.onload = () => {
      const context = canvas.getContext("2d");
      if (!context) return;
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      context.drawImage(image, 0, 0);
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
      pixels.data.set(
        colorizeFrame(
          pixels.data,
          frameStyle.inkColor,
          frameStyle.backgroundColor,
          frameStyle.cutoff,
          frameStyle.cutoffMode,
          canvas.width,
          canvas.height,
        ),
      );
      context.putImageData(pixels, 0, 0);
    };
    image.src = apiUrl(frame.url);
  }, [frame?.url, frameStyle.inkColor, frameStyle.backgroundColor, frameStyle.cutoff, frameStyle.cutoffMode]);

  return (
    <div className="player-wrap">
      <div className="canvas-stage">
        <div className="checkerboard" />
        <div className="canvas-zoom-controls" aria-label="Canvas zoom">
          <button type="button" onClick={() => setZoom((value) => Math.max(0.5, +(value - 0.25).toFixed(2)))} aria-label="Zoom out" disabled={zoom <= 0.5}>−</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setZoom((value) => Math.min(2, +(value + 0.25).toFixed(2)))} aria-label="Zoom in" disabled={zoom >= 2}>+</button>
        </div>
        {frame ? (
          <canvas
            ref={canvasRef}
            className="canvas-image"
            style={{ transform: `scale(${zoom})` }}
            role="img"
            aria-label={`Generated frame ${index + 1}`}
          />
        ) : (
          <div className="canvas-empty">
            <div className="sketch-mark"><span /><span /><span /></div>
            <p>Your frames will appear here</p>
            <small>Upload two drawings to get started</small>
          </div>
        )}
        <span className="canvas-resolution">{frame ? "Frame preview" : "Canvas"}</span>
      </div>
      <div className="player-controls">
        <button
          className="play-button"
          aria-label={playing ? "Pause" : "Play"}
          disabled={frames.length < 2}
          onClick={() => setPlaying((value) => !value)}
        >
          {playing ? "Ⅱ" : "▶"}
        </button>
        <input
          className="scrubber"
          type="range"
          min={0}
          max={Math.max(0, frames.length - 1)}
          value={Math.min(index, Math.max(0, frames.length - 1))}
          onChange={(event) => {
            setPlaying(false);
            setIndex(Number(event.target.value));
          }}
          disabled={!frames.length}
          aria-label="Scrub through generated frames"
        />
        <span className="frame-counter">{frames.length ? `${index + 1} / ${frames.length}` : "— / —"}</span>
        <label className="fps-select">
          <span>{fps} FPS</span>
          <input type="range" min="1" max="60" value={fps} onChange={(event) => setFps(Number(event.target.value))} aria-label="Preview FPS" />
        </label>
      </div>
      <div className="frame-strip">
        {frames.length ? frames.map((item, position) => (
          <button
            className={`frame-thumb ${position === index ? "selected" : ""}`}
            key={`${item.index}-${position}`}
            onClick={() => { setIndex(position); setPlaying(false); }}
          >
            <img src={apiUrl(item.url)} alt={`Frame ${position + 1}`} />
            <span>{String(position + 1).padStart(2, "0")}</span>
          </button>
        )) : (
          <div className="strip-placeholder"><span /> <span /> <span /> <span /> <span /></div>
        )}
      </div>
      {(onMoveFrame || onRemoveFrame || onInsertFrameAfter) && frames.length > 0 && (
        <div className="frame-actions-bar">
          <span>Frame {index + 1} of {frames.length}</span>
          <div className="frame-action-buttons">
            {onMoveFrame && (
              <>
                <button type="button" className="frame-action-btn" disabled={index <= 0} onClick={() => { onMoveFrame(index, -1); setIndex(index - 1); }}>← Move left</button>
                <button type="button" className="frame-action-btn" disabled={index >= frames.length - 1} onClick={() => { onMoveFrame(index, 1); setIndex(index + 1); }}>Move right →</button>
              </>
            )}
            {onInsertFrameAfter && (
              <button
                type="button"
                className="frame-action-btn accent"
                disabled={index >= frames.length - 1 || insertingPosition !== null}
                onClick={() => onInsertFrameAfter(index)}
              >
                {insertingPosition === index ? "Generating..." : "+ Add in-between"}
              </button>
            )}
            {onRemoveFrame && (
              <button
                type="button"
                className="frame-action-btn danger"
                disabled={frames.length <= 2}
                onClick={() => {
                  onRemoveFrame(index);
                  setIndex((current) => Math.max(0, Math.min(current, frames.length - 2)));
                }}
              >
                × Remove
              </button>
            )}
          </div>
        </div>
      )}
      {showSettings && <div className="preview-settings">
        <label className="apply-all-toggle"><input type="checkbox" checked={applyToAllFrames} onChange={(event) => {
          const applyToAll = event.target.checked;
          setApplyToAllFrames(applyToAll);
          if (applyToAll) {
            setFrameStyles({});
            onFrameStylesChange?.({});
          }
        }} /> Apply to all frames</label>
        <label>Ink<input type="color" value={frameStyle.inkColor} onChange={(event) => updateFrameStyle("inkColor", event.target.value)} /></label>
        <label>Background<input type="color" value={frameStyle.backgroundColor} onChange={(event) => updateFrameStyle("backgroundColor", event.target.value)} /></label>
        <label>Cutoff<select value={frameStyle.cutoffMode} onChange={(event) => updateMode(event.target.value as CutoffMode)}><option value="raw">Raw</option><option value="crisp">Crisp lines</option><option value="threshold">Threshold</option></select></label>
        {frameStyle.cutoffMode !== "raw" && <label>Level<input type="range" min="0" max="1" step="0.01" value={frameStyle.cutoff ?? 0.5} onChange={(event) => updateFrameStyle("cutoff", Number(event.target.value))} /></label>}
      </div>}
    </div>
  );
}
