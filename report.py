"""Günlük otomatik rapor üretici (GitHub Actions için)."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data import fetch_ohlcv, normalize_ticker
from levels import build_level_table, build_trade_plan

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = REPO_ROOT / "reports"


def load_watchlist(path: Path) -> list[str]:
    if not path.exists():
        return ["PATEK"]
    lines = [ln.strip().upper() for ln in path.read_text(encoding="utf-8").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def render_ticker_md(ticker: str, levels_df: pd.DataFrame, plan_df: pd.DataFrame, meta: dict) -> str:
    price = meta["price"]
    out = [f"### {ticker} — {price:,.2f} TL\n"]

    top = levels_df.sort_values("Güç", ascending=False).head(8)
    out.append("**Öne çıkan seviyeler**\n")
    out.append("| Seviye (TL) | Tür | Güç | Kaynaklar |")
    out.append("|---:|---|---:|---|")
    for _, r in top.iterrows():
        out.append(f"| {r['Seviye (TL)']:.2f} | {r['Tür']} | {r['Güç']} | {r['Kaynaklar']} |")
    out.append("")

    out.append("**İşlem planı**\n")
    out.append("| Senaryo | Giriş | Stop | Hedef 1 | Hedef 2 | R/R | Lot |")
    out.append("|---|---|---|---|---|---:|---:|")
    for _, r in plan_df.iterrows():
        rr = f"{r['R/R']:.2f}" if pd.notna(r["R/R"]) else "-"
        out.append(
            f"| {r['Senaryo']} | {r['Giriş Bölgesi (TL)']} | "
            f"{r['Stop-Loss (TL)']:.2f} | {r['Hedef 1 (TL)']:.2f} | "
            f"{r['Hedef 2 (TL)']:.2f} | {rr} | {r['Önerilen Lot']} |"
        )
    out.append("")
    return "\n".join(out)


def build_report(watchlist: list[str]) -> tuple[str, dict]:
    now = datetime.now(timezone.utc)
    summary: dict[str, dict] = {}
    sections: list[str] = []

    for tk in watchlist:
        ticker = normalize_ticker(tk)
        try:
            df = fetch_ohlcv(ticker, interval="1d", period="2y")
        except Exception as e:
            sections.append(f"### {ticker}\n\n⚠️ Veri alınamadı: `{e}`\n")
            continue

        if df.empty or len(df) < 20:
            sections.append(f"### {ticker}\n\n⚠️ Yetersiz veri.\n")
            continue

        levels_df = build_level_table(df)
        plan_df, meta = build_trade_plan(df, levels_df)
        sections.append(render_ticker_md(ticker, levels_df, plan_df, meta))

        summary[ticker] = {
            "price": meta["price"],
            "primary_support": meta["primary_support"],
            "primary_resistance": meta["primary_resistance"],
            "next_resistance": meta["next_resistance"],
            "stop": meta["stop"],
        }

    header = (
        f"# 📈 Günlük BIST Destek/Direnç Raporu\n\n"
        f"**Tarih (UTC):** {now.strftime('%Y-%m-%d %H:%M')}  \n"
        f"**Semboller:** {', '.join(watchlist)}\n\n"
        f"> ⚠️ Yatırım tavsiyesi değildir. Seviyeler geçmiş fiyat verisinden türetilmiştir.\n\n---\n\n"
    )
    return header + "\n".join(sections), summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default=str(REPO_ROOT / "watchlist.txt"))
    ap.add_argument("--out", default=str(REPORTS_DIR))
    args = ap.parse_args()

    watchlist = load_watchlist(Path(args.watchlist))
    if not watchlist:
        print("Watchlist boş.", file=sys.stderr)
        sys.exit(1)

    md, summary = build_report(watchlist)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    (outdir / f"{today}.md").write_text(md, encoding="utf-8")
    (outdir / "latest.md").write_text(md, encoding="utf-8")

    if summary:
        pd.DataFrame(summary).T.to_csv(outdir / f"{today}_summary.csv", index=True)

    print(f"✅ Rapor yazıldı: {outdir / today}.md")


if __name__ == "__main__":
    main()
