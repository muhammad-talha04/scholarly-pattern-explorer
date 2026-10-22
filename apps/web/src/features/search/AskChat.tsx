"use client";
import { useState } from "react";
import { api } from "@/lib/api/client";
import { Spinner } from "@/components/ui";

interface Msg { role: "user" | "bot"; text: string; sources?: string[] }

/** History is plain text. Markers such as **bold** and [links](url) are not sent. */
function plainText(value: string): string {
  return value
    .replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, "$1")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/(\*\*|__)([\s\S]*?)\1/g, "$2")
    .replace(/(\*|_)([\s\S]*?)\1/g, "$2")
    .replace(/^\s*[-*]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function AskChat({ paperId }: { paperId: string }) {
  // Turns stay in this component. They are not written to storage or a shared store.
  const [scope, setScope] = useState(paperId);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  if (scope !== paperId) {
    setScope(paperId);
    setMsgs([]);
    setQ("");
  }
  async function send(e: React.FormEvent) {
    e.preventDefault();
    const question = q.trim(); if (!question || busy) return;
    const history = msgs.slice(-2).map((m) => ({
      role: (m.role === "user" ? "user" : "assistant") as "user" | "assistant",
      content: plainText(m.text),
    }));
    setMsgs((m) => [...m, { role: "user", text: question }]); setQ(""); setBusy(true);
    try { const r = await api.ask(paperId, question, history); setMsgs((m) => [...m, { role: "bot", text: r.data.answer, sources: r.data.sources }]); }
    catch (err) { setMsgs((m) => [...m, { role: "bot", text: `Could not answer: ${(err as Error).message}` }]); }
    finally { setBusy(false); }
  }
  return (
    <div>
      <div className="max-h-64 space-y-2 overflow-y-auto">
        {msgs.map((m, i) => (
          <div key={i} className={`rounded-xl px-3 py-2 text-sm ${m.role === "user" ? "ml-8 bg-accent/15" : "mr-8 bg-white/5"}`}>
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
