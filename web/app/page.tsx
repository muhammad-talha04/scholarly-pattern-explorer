import HeroScene from "@/components/HeroScene";

const VIEWS = ["Explore patterns", "Lifecycles", "Countries", "Papers & search", "Timeline"];

export default function Home() {
  return (
    <main className="relative h-screen w-full overflow-hidden">
      <div className="absolute inset-0">
        <HeroScene />
      </div>
      <div className="pointer-events-none relative z-10 flex h-full flex-col justify-end p-8 md:p-16">
        <p className="text-sm uppercase tracking-[0.3em] text-aqua">OpenAlex · frequent-pattern mining</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-semibold md:text-6xl">
          Scholarly Pattern Explorer
        </h1>
        <p className="mt-4 max-w-xl text-slate-300">
          Which combinations of research topics are being born, and which is the field leaving
          behind? Sliding-window FP-Growth over millions of papers, rendered in 3D.
        </p>
        <ul className="mt-8 flex flex-wrap gap-3">
          {VIEWS.map((v) => (
            <li
              key={v}
              className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-sm text-slate-300 backdrop-blur"
            >
              {v} <span className="text-slate-500">· soon</span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
