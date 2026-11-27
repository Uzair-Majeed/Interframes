type Props = {
  count: number;
  setCount: (value: number) => void;
  disabled: boolean;
  canGenerate: boolean;
  onGenerate: () => void;
  buttonLabel?: string;
};

export function CustomizationPanel(props: Props) {
  return (
    <aside className="custom-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">YOUR SETUP</span>
          <h2>Customize</h2>
        </div>
      </div>

      <section className="setting-section">
        <div className="setting-label">
          <div><strong>In-between frames</strong><br /><small>Choose the sequence length</small></div>
        </div>
        <div className="segmented">
          {[1, 3, 7].map((value) => (
            <button
              key={value}
              className={props.count === value ? "active" : ""}
              onClick={() => props.setCount(value)}
              disabled={props.disabled}
            >
              {value}<small>{value === 1 ? "frame" : "frames"}</small>
            </button>
          ))}
        </div>
      </section>

      <div className="model-note">
        <span className="model-indicator" />
        <div><strong>InterFrames · Epoch 14</strong><small>GMA motion guidance</small></div>
        <span className="model-tag">LOCAL</span>
      </div>
      <button className="generate-button panel-generate" disabled={!props.canGenerate} onClick={props.onGenerate}>
        {props.disabled ? <><span className="spinner" /> Working...</> : <>{props.buttonLabel ?? "Generate frames"} <span>↗</span></>}
      </button>
    </aside>
  );
}
