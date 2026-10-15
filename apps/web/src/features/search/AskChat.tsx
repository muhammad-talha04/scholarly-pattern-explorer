"use client";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { Spinner } from "@/components/ui";

interface Msg { role: "user" | "bot"; text: string; sources?: string[] }
export function AskChat({ paperId }: { paperId: string }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  async function send(e: React.FormEvent) {
    e.preventDefault();
    const question = q.trim(); if (!question || busy) return;
    setMsgs((m) => [...m, { role: "user", text: question }]); setQ(""); setBusy(true);
    try { const r = await api.ask(paperId, question); setMsgs((m) => [...m, { role: "bot", text: r.data.answer, sources: r.data.sources }]); }
    catch (err) { setMsgs((m) => [...m, { role: "bot", text: `Could not answer: ${(err as Error).message}` }]); }
    finally { setBusy(false); }
  }
  return (
    <div>
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {msgs.map((m, i) => (
          <div key={i} className={`rounded-xl px-3 py-2 text-sm ${m.role === "user" ? "ml-8 bg-sky-500/15" : "mr-8 bg-white/5"}`}>
            {m.text}
            {m.sources && m.sources.filter(Boolean).length > 0 && <details className="mt-1 text-xs text-slate-400"><summary>Evidence</summary>{m.sources.map((s, j) => <p key={j} className="mt-1 border-l border-white/10 pl-2">{s}</p>)}</details>}
          </div>
        ))}
        {busy && <Spinner />}
      </div>
      <form onSubmit={send} className="mt-2 flex gap-2">
        <input aria-label="Ask about this paper" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about this paper…" className="input flex-1" />
        <button className="btn" disabled={busy}>Ask</button>
      </form>
    </div>
  );
}
