"use client";
import { useEffect, useState } from "react";
import type { Result, Source } from "./api/client";

export function useApi<T>(fn: () => Promise<Result<T>>, deps: unknown[]) {
  const [nonce, setNonce] = useState(0);
  const [state, set] = useState<{ data?: T; source?: Source; error?: string; loading: boolean }>({ loading: true });
  useEffect(() => {
    let live = true;
    set((s) => ({ ...s, loading: true, error: undefined }));
    fn().then((r) => live && set({ data: r.data, source: r.source, loading: false }))
      .catch((e: Error) => live && set({ error: e.message, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);
  return { ...state, reload: () => setNonce((n) => n + 1) };
}
