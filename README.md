# 📈 BIST Destek/Direnç & İşlem Planı
# YATIRIM TAVSİYESİ DEĞİLDİR #
Streamlit tabanlı, BIST hisseleri için otomatik **destek/direnç** ve **alım-satım planı** üreten uygulama.

## Özellikler
- `yfinance` ile BIST verisi (`.IS` otomatik eklenir)
- Günlük / Haftalık / Aylık zaman dilimi
- Pivot Klasik, Pivot Fibonacci, Camarilla, Swing High/Low, SMA20-50-100-200, Hacim POC, 52H Zirve/Dip
- ATR tabanlı kümeleme + güç skoru
- Plotly mum grafiği üzerinde seviyeler
- Pullback ve breakout senaryolu işlem planı
- Risk yüzdesine göre otomatik lot hesabı
- CSV dışa aktarma

## 📊 Backtest

Streamlit'te **Pages → 📊 Backtest** üzerinden geçmiş seviyelerin tutma oranını görebilirsiniz.

CLI:
```bash
python -c "from data import fetch_ohlcv, normalize_ticker; from backtest import run_backtest, summarize; \
df=fetch_ohlcv(normalize_ticker('PATEK')); r=run_backtest(df); print(summarize(r)['Tür'])"

- 
## Kurulum
```bash
git clone https://github.com/<kullanici>/patek-levels-app.git
cd patek-levels-app
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
