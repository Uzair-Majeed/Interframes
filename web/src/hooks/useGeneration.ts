import { useEffect, useState } from "react";
import { getGeneration, type Generation } from "../lib/api";

export function useGeneration(id: string | undefined) {
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let live = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const next = await getGeneration(id);
        if (!live) return;
        setGeneration(next);
        setError("");
        if (next.status === "queued" || next.status === "running") {
          timer = window.setTimeout(poll, 900);
        }
      } catch (reason) {
        if (!live) return;
        setError(reason instanceof Error ? reason.message : "Could not load this generation.");
        timer = window.setTimeout(poll, 2500);
      }
    };
    void poll();
    return () => {
      live = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [id]);

  return { generation, error };
}
