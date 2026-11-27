import { useRef } from "react";
import type { EndpointInput } from "../../lib/api";
import { apiUrl } from "../../lib/api";

type Props = {
  label: string;
  number: string;
  endpoint: EndpointInput | null;
  preview: string | null;
  busy: boolean;
  onChoose: (file: File) => void;
};

export function EndpointUpload({ label, number, endpoint, preview, busy, onChoose }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const src = preview ?? (endpoint ? apiUrl(endpoint.asset.preview_url) : "");
  return (
    <section className={`endpoint-card ${src ? "has-image" : ""}`}>
      <div className="endpoint-topline">
        <span className="step-number">{number}</span>
        <span>{label}</span>
        {endpoint && <span className="asset-size">{endpoint.asset.width} × {endpoint.asset.height}</span>}
      </div>
      <button className="upload-surface" onClick={() => inputRef.current?.click()} disabled={busy}>
        {src ? (
          <img src={src} alt={`${label} drawing`} />
        ) : (
          <span className="upload-placeholder">
            <span className="upload-plus">+</span>
            <strong>Drop a drawing here</strong>
            <small>or browse PNG, JPG, WebP</small>
          </span>
        )}
        {src && <span className="replace-badge">Replace image</span>}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        hidden
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          if (file) onChoose(file);
          event.currentTarget.value = "";
        }}
      />
      <div className="endpoint-foot">
        <span className={`status-dot ${endpoint ? "approved" : ""}`} />
        {endpoint ? "Image checked" : "Waiting for image"}
      </div>
    </section>
  );
}
