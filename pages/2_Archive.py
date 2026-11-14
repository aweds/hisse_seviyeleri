"""reports/ klasöründeki günlük raporları görüntüle."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Rapor Arşivi", page_icon="📚", layout="wide")

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"

st.title("📚 Günlük Rapor Arşivi")
st.caption("GitHub Actions'ın `reports/` klasörüne yazdığı günlük raporlar")


def list_reports() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    files = [p for p in REPORTS_DIR.glob("*.md") if p.name != "latest.md"]
    return sorted(files, reverse=True)  # en yeni önce


def extract_tickers(md: str) -> list[str]:
    """Rapor içindeki '### TICKER —' satırlarından sembol listesi çıkar."""
    return re.findall(r"^### ([A-Z0-9\.]+)\s*—", md, flags=re.MULTILINE)


reports = list_reports()

if not reports:
    st.warning(
        "Henüz rapor yok.\n\n"
        "**İlk raporu üretmek için:**\n"
        "1. Repo → Settings → Secrets and variables → Actions → Variables\n"
        "2. `PUSH_REPORT = true` ekle\n"
        "3. Actions → Daily Level Report → Run workflow\n\n"
        "5 dakika sonra bu sayfa otomatik dolar."
    )
    st.stop()

# --- Filtreler ---
col1, col2 = st.columns([2, 1])
with col1:
    secenekler = {p.stem: p for p in reports}
    secili = st.selectbox(
        "Rapor seç",
        options=list(secenekler.keys()),
        format_func=lambda x: f"{x}  ({_file_size(secenekler[x])})"
        if False
        else x,
    )
with col2:
    st.metric("Toplam Rapor", len(reports))

selected_path = secenekler[secili]
md_text = selected_path.read_text(encoding="utf-8")

# --- Üst bilgi kartları ---
tickers = extract_tickers(md_text)
meta_cols = st.columns(min(4, max(1, len(tickers))))
for i, tk in enumerate(tickers[:4]):
    meta_cols[i].metric(tk, "rapor var")

st.divider()

# --- Raporu göster ---
tab1, tab2 = st.tabs(["📄 Rendered", "📝 Markdown (ham)"])

with tab1:
    st.markdown(md_text)

with tab2:
    st.code(md_text, language="markdown")

st.divider()

# --- İndirme butonları ---
dl1, dl2 = st.columns(2)
with dl1:
    st.download_button(
        f"⬇️ {selected_path.name} indir",
        data=md_text.encode("utf-8"),
        file_name=selected_path.name,
        mime="text/markdown",
    )
with dl2:
    csv_candidate = REPORTS_DIR / f"{selected_path.stem}_summary.csv"
    if csv_candidate.exists():
        st.download_button(
            f"⬇️ {csv_candidate.name} indir",
            data=csv_candidate.read_bytes(),
            file_name=csv_candidate.name,
            mime="text/csv",
        )

# --- Tarihsel özet tablosu ---
st.subheader("📅 Tüm Raporlar")

rows = []
for p in reports:
    txt = p.read_text(encoding="utf-8")
    tks = extract_tickers(txt)
    rows.append({
        "Tarih": p.stem,
        "Sembol Sayısı": len(tks),
        "Semboller": ", ".join(tks) if tks else "-",
        "Boyut (KB)": round(p.stat().st_size / 1024, 1),
    })

st.dataframe(rows, use_container_width=True, hide_index=True)

# --- Karşılaştırma: iki rapor yan yana ---
if len(reports) >= 2:
    st.subheader("🔀 İki Raporu Karşılaştır")
    cc1, cc2 = st.columns(2)
    with cc1:
        a = st.selectbox("Rapor A", [p.stem for p in reports], index=0, key="cmp_a")
    with cc2:
        b = st.selectbox("Rapor B", [p.stem for p in reports], index=min(1, len(reports) - 1), key="cmp_b")

    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"**{a}**")
        st.markdown(secenekler[a].read_text(encoding="utf-8"))
    with colB:
        st.markdown(f"**{b}**")
        st.markdown(secenekler[b].read_text(encoding="utf-8"))
