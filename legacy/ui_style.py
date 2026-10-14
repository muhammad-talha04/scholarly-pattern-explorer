"""Visual layer for app.py: CSS, colour palette, Plotly styling, HTML cards.

Kept apart from app.py so the app file reads as "what is shown" and this file
as "how it looks". Nothing here touches the database.
"""
from __future__ import annotations

import html

# ---------------------------------------------------------------- palette ----
BG = "#0A0F1E"
PANEL = "#0F172A"
PANEL_2 = "#131B2E"
INK = "#E6EAF2"
MUTED = "#8B97B0"
GRID = "#1E2A44"
TEAL = "#2DD4BF"
VIOLET = "#A78BFA"
PINK = "#F472B6"
AMBER = "#FBBF24"

CATEGORICAL = ["#2DD4BF", "#A78BFA", "#F472B6", "#FBBF24",
               "#60A5FA", "#34D399", "#FB923C", "#E879F9"]
SEQUENTIAL = [[0.0, "#111A2E"], [0.25, "#134E4A"], [0.5, "#0D9488"],
              [0.75, "#2DD4BF"], [1.0, "#FDE68A"]]
AURORA = [[0.0, "#312E81"], [0.35, "#7C3AED"], [0.65, "#2DD4BF"], [1.0, "#FDE68A"]]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

/* ---------- page background: soft aurora glow ---------- */
[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(1200px 600px at 8% -10%, rgba(45,212,191,.10), transparent 60%),
    radial-gradient(900px 500px at 95% 0%, rgba(167,139,250,.12), transparent 55%),
    #0A0F1E;
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px; }
#MainMenu, footer { visibility: hidden; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0D1426 0%, #0A1020 100%);
  border-right: 1px solid #1E2A44;
}
.side-brand { display:flex; align-items:center; gap:.65rem; margin:.2rem 0 1.1rem; }
.side-brand .logo {
  width:38px; height:38px; border-radius:11px; display:grid; place-items:center;
  background: linear-gradient(135deg,#0D9488 0%,#2DD4BF 45%,#7C3AED 100%);
  box-shadow: 0 6px 22px rgba(45,212,191,.35);
}
.side-brand .t1 { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.02rem; color:#E6EAF2; line-height:1.1;}
.side-brand .t2 { font-size:.72rem; color:#8B97B0; letter-spacing:.06em; text-transform:uppercase;}
.side-label {
  font-size:.7rem; letter-spacing:.12em; text-transform:uppercase; color:#5EEAD4;
  font-weight:600; margin: 1.1rem 0 .35rem;
}

/* ---------- hero ---------- */
.hero {
  position:relative; overflow:hidden; border-radius:22px; padding:1.6rem 1.9rem 1.4rem;
  background: linear-gradient(135deg, rgba(19,27,46,.95), rgba(15,23,42,.85));
  border:1px solid #243049;
  box-shadow: 0 20px 60px rgba(0,0,0,.35);
  margin-bottom: 1.1rem;
}
.hero:before {
  content:""; position:absolute; inset:-2px; border-radius:22px; padding:1px;
  background: linear-gradient(120deg, rgba(45,212,191,.7), rgba(167,139,250,.55), rgba(244,114,182,.35));
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude; pointer-events:none;
}
.hero:after {
  content:""; position:absolute; right:-80px; top:-80px; width:320px; height:320px;
  background: radial-gradient(circle, rgba(45,212,191,.22), transparent 65%);
}
.hero h1 {
  font-family:'Space Grotesk',sans-serif; font-size:2.15rem; font-weight:700; margin:0 0 .25rem;
  background: linear-gradient(90deg,#E6EAF2 0%, #5EEAD4 55%, #A78BFA 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent; padding:0;
}
.hero p { color:#9AA6BF; margin:0 0 .9rem; font-size:1rem; }
.chips { display:flex; flex-wrap:wrap; gap:.45rem; position:relative; z-index:1; }
.chip {
  display:inline-flex; align-items:center; gap:.35rem; padding:.28rem .7rem; border-radius:999px;
  font-size:.8rem; color:#D5DCEA; background:rgba(255,255,255,.04); border:1px solid #2A3756;
}
.chip b { color:#5EEAD4; font-weight:600; }

/* ---------- KPI cards ---------- */
.kpis { display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:.8rem; margin: .2rem 0 1.2rem; }
.kpi {
  border-radius:16px; padding:.9rem 1rem .85rem; position:relative; overflow:hidden;
  background: linear-gradient(160deg, rgba(22,32,58,.9), rgba(13,20,38,.9));
  border:1px solid #223050; transition: transform .15s ease, border-color .15s ease;
}
.kpi:hover { transform: translateY(-2px); border-color:#2DD4BF55; }
.kpi .bar { position:absolute; left:0; top:0; height:3px; width:100%; }
.kpi .lab { font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; color:#8B97B0; }
.kpi .val { font-family:'Space Grotesk',sans-serif; font-size:1.65rem; font-weight:700; color:#F1F5FB; margin-top:.15rem; }
.kpi .sub { font-size:.75rem; color:#6F7C96; }

/* ---------- navigation pills (segmented control) ---------- */
[data-testid="stButtonGroup"] { gap:.4rem; flex-wrap:wrap; }
[data-testid="stButtonGroup"] button {
  border-radius:999px !important; border:1px solid #243049 !important;
  background: rgba(19,27,46,.7) !important; color:#C3CCDD !important;
  padding: .45rem 1rem !important; transition: all .15s ease;
}
[data-testid="stButtonGroup"] button:hover { border-color:#2DD4BF !important; color:#fff !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] {
  background: linear-gradient(135deg, rgba(45,212,191,.22), rgba(124,58,237,.22)) !important;
  border-color:#2DD4BF !important; color:#fff !important;
  box-shadow: 0 0 0 1px rgba(45,212,191,.25), 0 8px 24px rgba(45,212,191,.12);
}

/* ---------- bordered containers become glass panels ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: linear-gradient(160deg, rgba(19,27,46,.72), rgba(12,18,34,.72));
  border-color:#1F2B47 !important; border-radius:18px !important;
}
.sec-title { font-family:'Space Grotesk',sans-serif; font-size:1.12rem; font-weight:600; color:#E6EAF2; margin:.1rem 0 .1rem; }
.sec-sub { color:#8B97B0; font-size:.85rem; margin-bottom:.4rem; }
.note {
  border-left:3px solid #2DD4BF; background:rgba(45,212,191,.06); padding:.6rem .85rem;
  border-radius:0 10px 10px 0; color:#AEB9CF; font-size:.86rem; margin-top:.4rem;
}

/* ---------- tables, inputs, scrollbars ---------- */
[data-testid="stDataFrame"] { border-radius:12px; overflow:hidden; }
div[data-baseweb="select"] > div { border-radius:12px !important; }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-thumb { background:#243049; border-radius:10px; }
::-webkit-scrollbar-track { background:transparent; }
.foot { color:#5F6B84; font-size:.8rem; text-align:center; margin-top:1.5rem; }
</style>
"""


# Logo: a small co-authorship graph (the project's core idea) inside a
# teal-to-violet tile. Pure SVG, so it stays sharp at any size.
LOGO_SVG = (
    "<svg width='24' height='24' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'>"
    "<g stroke='rgba(255,255,255,.85)' stroke-width='1.4' stroke-linecap='round'>"
    "<line x1='6' y1='7' x2='12' y2='12'/><line x1='18' y1='6' x2='12' y2='12'/>"
    "<line x1='12' y1='12' x2='8' y2='18.5'/><line x1='12' y1='12' x2='18' y2='17'/>"
    "<line x1='6' y1='7' x2='18' y2='6'/></g>"
    "<circle cx='12' cy='12' r='3' fill='#fff'/>"
    "<circle cx='6' cy='7' r='2' fill='#CCFBF1'/><circle cx='18' cy='6' r='2' fill='#DDD6FE'/>"
    "<circle cx='8' cy='18.5' r='2' fill='#CCFBF1'/><circle cx='18' cy='17' r='2' fill='#FBCFE8'/>"
    "</svg>")


def esc(s) -> str:
    return html.escape(str(s))


def brand() -> str:
    return ("<div class='side-brand'><div class='logo'>" + LOGO_SVG + "</div><div>"
            "<div class='t1'>Scholarly Pattern<br>Explorer</div>"
            "<div class='t2'>OpenAlex · research trends</div></div></div>")


def side_label(text: str) -> str:
    return f"<div class='side-label'>{esc(text)}</div>"


def hero(title: str, subtitle: str, chips: list[tuple[str, str]]) -> str:
    chip_html = "".join(f"<span class='chip'>{esc(k)} <b>{esc(v)}</b></span>" for k, v in chips)
    return (f"<div class='hero'><h1>{esc(title)}</h1><p>{esc(subtitle)}</p>"
            f"<div class='chips'>{chip_html}</div></div>")


def kpis(items: list[tuple[str, str, str]]) -> str:
    """items: (label, value, sub)."""
    cards = []
    for i, (lab, val, sub) in enumerate(items):
        c1 = CATEGORICAL[i % len(CATEGORICAL)]
        c2 = CATEGORICAL[(i + 1) % len(CATEGORICAL)]
        cards.append(
            f"<div class='kpi'><div class='bar' style='background:linear-gradient(90deg,{c1},{c2})'></div>"
            f"<div class='lab'>{esc(lab)}</div><div class='val'>{esc(val)}</div>"
            f"<div class='sub'>{esc(sub)}</div></div>")
    return f"<div class='kpis'>{''.join(cards)}</div>"


def section(title: str, sub: str = "") -> str:
    s = f"<div class='sec-title'>{esc(title)}</div>"
    if sub:
        s += f"<div class='sec-sub'>{esc(sub)}</div>"
    return s


def note(text: str) -> str:
    return f"<div class='note'>{esc(text)}</div>"


def styled(fig, height: int = 520):
    """Dark, borderless Plotly figure that sits inside the glass panels.
    The paper colour is opaque so exported PNGs keep the dark background."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=PANEL,
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, 'Segoe UI', sans-serif", size=13, color=INK),
        hoverlabel=dict(bgcolor="#1A2440", bordercolor="#2DD4BF",
                        font=dict(color="#F1F5FB", size=12)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#C3CCDD")),
        coloraxis_colorbar=dict(outlinewidth=0, thickness=10, tickfont=dict(color=MUTED)),
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     title_font=dict(size=12, color=MUTED),
                     tickfont=dict(size=11, color="#AEB9CF"), automargin=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID,
                     title_font=dict(size=12, color=MUTED),
                     tickfont=dict(size=11, color="#AEB9CF"), automargin=True)
    return fig
