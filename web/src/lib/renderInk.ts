export type CutoffMode = "raw" | "threshold" | "crisp";

const GAUSS_RADIUS = 6;
const GAUSS_WEIGHTS = (() => {
  const sigma = 3.0;
  const weights = new Float32Array(GAUSS_RADIUS * 2 + 1);
  let sum = 0;
  for (let i = -GAUSS_RADIUS; i <= GAUSS_RADIUS; i += 1) {
    const w = Math.exp(-0.5 * (i / sigma) ** 2);
    weights[i + GAUSS_RADIUS] = w;
    sum += w;
  }
  for (let i = 0; i < weights.length; i += 1) weights[i] /= sum;
  return weights;
})();

function separableGaussian(ink: Float32Array, width: number, height: number): Float32Array {
  const horiz = new Float32Array(width * height);
  const out = new Float32Array(width * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      let acc = 0;
      for (let d = -GAUSS_RADIUS; d <= GAUSS_RADIUS; d += 1) {
        const sx = Math.min(width - 1, Math.max(0, x + d));
        acc += GAUSS_WEIGHTS[d + GAUSS_RADIUS] * ink[row + sx];
      }
      horiz[row + x] = acc;
    }
  }
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      let acc = 0;
      for (let d = -GAUSS_RADIUS; d <= GAUSS_RADIUS; d += 1) {
        const sy = Math.min(height - 1, Math.max(0, y + d));
        acc += GAUSS_WEIGHTS[d + GAUSS_RADIUS] * horiz[sy * width + x];
      }
      out[row + x] = acc;
    }
  }
  return out;
}

export function colorizeFrame(
  pixels: Uint8ClampedArray,
  inkColor: string,
  backgroundColor: string,
  cutoff: number | null,
  cutoffMode: CutoffMode = cutoff === null ? "raw" : "threshold",
  width = 0,
  height = 0,
) {
  const ink = hexToRgb(inkColor);
  const background = hexToRgb(backgroundColor);

  if (cutoffMode === "crisp" && width > 0 && height > 0) {
    const level = cutoff ?? 0.5;
    const count = width * height;
    const rawInk = new Float32Array(count);
    for (let i = 0; i < count; i += 1) {
      rawInk[i] = 1 - pixels[i * 4] / 255;
    }
    const blur = separableGaussian(rawInk, width, height);
    const floor = 0.04 + 0.14 * level;
    const detailDenom = Math.max(1e-4, 0.30 - 0.08 * level);
    const coreT = 0.65 + 0.25 * level;
    const coreDenom = Math.max(1e-4, 1.0 - coreT);
    const bgCut = 0.10 + 0.18 * level;

    for (let i = 0; i < count; i += 1) {
      const val = rawInk[i];
      let out = 0;
      if (val >= bgCut) {
        const ridge = Math.max(0, val - 0.85 * blur[i]);
        const detail = Math.min(1, Math.max(0, (ridge - floor) / detailDenom));
        const core = Math.min(1, Math.max(0, (val - coreT) / coreDenom));
        out = Math.max(detail, core);
      }
      const amount = 1 - out;
      const offset = i * 4;
      pixels[offset] = Math.round(ink[0] * (1 - amount) + background[0] * amount);
      pixels[offset + 1] = Math.round(ink[1] * (1 - amount) + background[1] * amount);
      pixels[offset + 2] = Math.round(ink[2] * (1 - amount) + background[2] * amount);
    }
    return pixels;
  }

  const threshold = cutoffMode === "threshold" && cutoff !== null ? (1 - cutoff) * 255 : null;
  for (let index = 0; index < pixels.length; index += 4) {
    const gray = pixels[index];
    const amount = threshold === null ? gray / 255 : gray < threshold ? 0 : 1;
    pixels[index] = Math.round(ink[0] * (1 - amount) + background[0] * amount);
    pixels[index + 1] = Math.round(ink[1] * (1 - amount) + background[1] * amount);
    pixels[index + 2] = Math.round(ink[2] * (1 - amount) + background[2] * amount);
  }
  return pixels;
}

function hexToRgb(color: string): [number, number, number] {
  return [1, 3, 5].map((start) => Number.parseInt(color.slice(start, start + 2), 16)) as [number, number, number];
}
