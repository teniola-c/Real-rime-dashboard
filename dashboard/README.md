# Live Markets & Weather Dashboard — V2 (Streamlit)

Beautiful, interactive dashboard for **Stocks**, **Crypto**, and **Weather**, plus a **Portfolio** tab
with live P/L and allocation. Now includes **multi-location weather** picker.

## Highlights
- Stock tiles (auto-refresh) with sparklines
- Crypto prices via Binance WebSocket (true realtime)
- Weather: select **multiple cities** from presets or add custom
- Portfolio: editable table, live P/L, allocation donut
- Price alerts via JSON
- Clean, modern styling

## Quick Start
1) Create `.env` from `.env.example` and put your OpenWeatherMap key.
2) Install:
   ```bash
   pip install -r requirements.txt
   ```
3) Run:
   ```bash
   streamlit run app.py
   ```

## Tips
- In the sidebar, adjust refresh interval and alerts.
- Use Binance symbols for crypto (e.g., BTCUSDT, ETHUSDT).
