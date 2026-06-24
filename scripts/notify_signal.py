"""
notify_signal.py — Weekly monitor script for the BTC-USDT SMA 273 strategy.
Calculates the latest trend signal, generates a premium HTML dashboard, and sends Telegram notifications.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf

# Reconfigure stdout to support UTF-8 emojis on Windows terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output_btc"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Fetch Data from Yahoo Finance ──
def fetch_btc_data():
    print("Fetching latest BTC-USD daily prices from Yahoo Finance...")
    try:
        # Download 3 years of daily data
        df = yf.download("BTC-USD", period="3y", interval="1d")
        if df.empty:
            raise ValueError("No data returned from yfinance")
            
        # Reset index to get Date column
        df = df.reset_index()
        
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
            
        # Rename columns to lowercase
        df.columns = [col.lower() for col in df.columns]
        
        # Check if 'adj close' or 'close' should be used
        if "adj close" in df.columns:
            df = df.rename(columns={"adj close": "close"})
            
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        
        return df
    except Exception as e:
        print(f"Error fetching data from Yahoo Finance: {e}")
        # Fall back to local database if offline
        local_path = PROJECT_ROOT / "data" / "daily" / "BTC.csv"
        if local_path.exists():
            print("Falling back to local BTC.csv database...")
            df = pd.read_csv(local_path, parse_dates=["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df.set_index("date", inplace=True)
            return df
        else:
            raise RuntimeError("No historical BTC data available.")

# ── Send Telegram Message ──
def send_telegram_notification(token, chat_id, message):
    print("Sending Telegram notification...")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            if res.get("ok"):
                print("Telegram notification sent successfully.")
            else:
                print(f"Telegram API Error: {res}")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

# ── Generate HTML Dashboard ──
def generate_html_dashboard(df, close_price, sma_val, current_signal, prev_signal, last_update_str):
    # Prepare last 15 days data table
    df_tail = df.tail(15).copy().sort_index(ascending=False)
    table_rows = ""
    for date, row in df_tail.iterrows():
        p = float(row["close"])
        s = float(row["SMA_273"])
        diff = ((p / s) - 1.0) * 100
        diff_color = "text-emerald-600" if diff >= 0 else "text-rose-600"
        sig_badge = '<span class="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 text-emerald-800">BUY</span>' if p > s else '<span class="px-2 py-0.5 text-xs font-semibold rounded bg-rose-100 text-rose-800">CASH</span>'
        
        table_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
            <td class="px-6 py-4 text-sm font-medium text-slate-900">{date.strftime('%Y-%m-%d')}</td>
            <td class="px-6 py-4 text-sm text-slate-700 font-mono">${p:,.2f}</td>
            <td class="px-6 py-4 text-sm text-slate-500 font-mono">${s:,.2f}</td>
            <td class="px-6 py-4 text-sm font-semibold font-mono {diff_color}">{diff:+.2f}%</td>
            <td class="px-6 py-4 text-sm">{sig_badge}</td>
        </tr>
        """
        
    # Prepare trade log table
    trade_log_path = OUTPUT_DIR / "trade_log.csv"
    trade_rows = ""
    if trade_log_path.exists():
        trade_df = pd.read_csv(trade_log_path)
        trade_df = trade_df.sort_values("date", ascending=False)
        for _, row in trade_df.iterrows():
            side_badge = '<span class="px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 uppercase">BUY</span>' if row["side"].lower() == "buy" else '<span class="px-2.5 py-0.5 text-xs font-bold rounded-full bg-rose-100 text-rose-800 uppercase">SELL</span>'
            trade_rows += f"""
            <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                <td class="px-6 py-4 text-sm font-medium text-slate-900">{row['date']}</td>
                <td class="px-6 py-4 text-sm">{side_badge}</td>
                <td class="px-6 py-4 text-sm text-slate-700 font-mono">${float(row['raw_price']):,.2f}</td>
                <td class="px-6 py-4 text-sm text-slate-700 font-mono">${float(row['exec_price']):,.2f}</td>
                <td class="px-6 py-4 text-sm text-slate-500 font-mono">{float(row['quantity']):.6f}</td>
                <td class="px-6 py-4 text-sm text-slate-900 font-semibold font-mono">${float(row['usd_value']):,.2f}</td>
                <td class="px-6 py-4 text-sm text-slate-500 font-mono">${float(row['fee_usd']):,.2f}</td>
            </tr>
            """
    else:
        trade_rows = '<tr><td colspan="7" class="px-6 py-8 text-center text-sm text-slate-400">Nessun trade registrato nel log storico.</td></tr>'

    # Get recent history for chart (last 180 days)
    chart_df = df.tail(180)
    chart_dates = [d.strftime('%Y-%m-%d') for d in chart_df.index]
    chart_prices = [float(x) for x in chart_df["close"]]
    chart_sma = [float(x) for x in chart_df["SMA_273"]]

    # Status styling
    if current_signal == 1:
        status_title = "COMPRARE BTC / LONG"
        status_bg = "bg-emerald-500"
        status_card_bg = "bg-emerald-50 border-emerald-200"
        status_badge_color = "bg-emerald-100 text-emerald-800"
        status_text_color = "text-emerald-700"
        status_dot = "bg-emerald-500"
    else:
        status_title = "VENDERE BTC / CASH (USDT)"
        status_bg = "bg-rose-500"
        status_card_bg = "bg-rose-50 border-rose-200"
        status_badge_color = "bg-rose-100 text-rose-800"
        status_text_color = "text-rose-700"
        status_dot = "bg-rose-500"

    html_content = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BTC-USDT SMA 273 Dashboard</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Outfit', sans-serif;
            background-color: #F8FAFC;
        }}
        .font-mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
    </style>
</head>
<body class="min-h-screen text-slate-800 antialiased">

    <!-- Header -->
    <header class="border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div class="flex items-center gap-3">
                <div class="h-10 w-10 rounded-xl bg-slate-900 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-slate-900/20">
                    ₿
                </div>
                <div>
                    <h1 class="text-xl font-bold text-slate-900">BTC-USDT SMA 273</h1>
                    <p class="text-xs text-slate-500">Dashboard Tattica Trend-Following</p>
                </div>
            </div>
            <div class="flex items-center gap-2 text-xs text-slate-500 bg-slate-100 px-3 py-1.5 rounded-lg">
                <span class="relative flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 {status_dot}"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 {status_dot}"></span>
                </span>
                <span>Ultimo aggiornamento: <strong class="font-medium">{last_update_str}</strong></span>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        
        <!-- Status & Key Metrics Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Action Card -->
            <div class="lg:col-span-1 rounded-2xl border p-6 flex flex-col justify-between {status_card_bg} shadow-sm">
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold uppercase tracking-wider text-slate-500">Stato Strategia</span>
                        <span class="px-2.5 py-1 text-xs font-bold rounded-full {status_badge_color} uppercase">{status_title.split(' ')[0]}</span>
                    </div>
                    <div>
                        <h2 class="text-3xl font-extrabold text-slate-900 tracking-tight">{status_title}</h2>
                        <p class="text-sm {status_text_color} mt-1.5 font-medium">
                            {"Bitcoin si trova in fase rialzista sopra la SMA 273. Mantenere l'esposizione." if current_signal == 1 else "Bitcoin si trova in fase ribassista sotto la SMA 273. Mantenere la liquidità in USDT."}
                        </p>
                    </div>
                </div>
                <div class="pt-6 border-t border-slate-200/60 mt-6">
                    <div class="flex items-center justify-between text-sm">
                        <span class="text-slate-500">Incrocio di trend (Crossover):</span>
                        <span class="font-bold text-slate-900">{"ATTIVO ⚠️" if current_signal != prev_signal else "NO"}</span>
                    </div>
                </div>
            </div>

            <!-- Metric Card 1: BTC Price -->
            <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                <div class="space-y-2">
                    <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Prezzo BTC attuale</span>
                    <h3 class="text-4xl font-extrabold text-slate-900 font-mono tracking-tight">${close_price:,.2f}</h3>
                </div>
                <div class="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                    <span>Chiusura giornaliera (Yahoo Finance)</span>
                </div>
            </div>

            <!-- Metric Card 2: SMA 273 -->
            <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between">
                <div class="space-y-2">
                    <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Media Mobile SMA 273</span>
                    <h3 class="text-4xl font-extrabold text-slate-900 font-mono tracking-tight">${sma_val:,.2f}</h3>
                </div>
                <div class="pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span class="text-slate-500">Distanza percentuale:</span>
                    <span class="font-bold font-mono {'text-emerald-600' if close_price >= sma_val else 'text-rose-600'}">
                        {((close_price / sma_val) - 1.0) * 100:+.2f}%
                    </span>
                </div>
            </div>
        </div>

        <!-- Chart -->
        <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="text-lg font-bold text-slate-900">Andamento Recente (Ultimi 180 Giorni)</h3>
                    <p class="text-xs text-slate-400">Confronto tra prezzo di chiusura e linea di trend SMA 273</p>
                </div>
            </div>
            <div class="h-96 relative">
                <canvas id="trendChart"></canvas>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Historical Data Table -->
            <div class="lg:col-span-1 rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col">
                <div class="px-6 py-4 border-b border-slate-100">
                    <h3 class="text-base font-bold text-slate-900">Ultimi 15 Giorni</h3>
                    <p class="text-xs text-slate-400">Verifica i dati quotidiani storici</p>
                </div>
                <div class="overflow-x-auto flex-1">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-50/70 border-b border-slate-100 text-xs font-bold uppercase tracking-wider text-slate-400">
                                <th class="px-6 py-3 font-semibold">Data</th>
                                <th class="px-6 py-3 font-semibold">BTC Close</th>
                                <th class="px-6 py-3 font-semibold">SMA 273</th>
                                <th class="px-6 py-3 font-semibold">Diff %</th>
                                <th class="px-6 py-3 font-semibold">Stato</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Historical Trades Table -->
            <div class="lg:col-span-2 rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden flex flex-col">
                <div class="px-6 py-4 border-b border-slate-100">
                    <h3 class="text-base font-bold text-slate-900">Registro Storico delle Operazioni (Trade Log)</h3>
                    <p class="text-xs text-slate-400">Storico dei segnali di acquisto e vendita eseguiti dalla strategia</p>
                </div>
                <div class="overflow-x-auto flex-1">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-slate-50/70 border-b border-slate-100 text-xs font-bold uppercase tracking-wider text-slate-400">
                                <th class="px-6 py-3 font-semibold">Data</th>
                                <th class="px-6 py-3 font-semibold">Tipo</th>
                                <th class="px-6 py-3 font-semibold">Prezzo Close</th>
                                <th class="px-6 py-3 font-semibold">Prezzo Esec.</th>
                                <th class="px-6 py-3 font-semibold">Quantità</th>
                                <th class="px-6 py-3 font-semibold">Valore USD</th>
                                <th class="px-6 py-3 font-semibold">Fee USD</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {trade_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

    </main>

    <footer class="border-t border-slate-200 bg-white py-6 mt-12 text-center text-xs text-slate-400">
        <p>Progetto Momentum-trading-crypto • Modellato per scopi educativi ed operativi.</p>
    </footer>

    <!-- Chart Configuration Script -->
    <script>
        const ctx = document.getElementById('trendChart').getContext('2d');
        const chart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(chart_dates)},
                datasets: [
                    {{
                        label: 'Prezzo BTC',
                        data: {json.dumps(chart_prices)},
                        borderColor: '#0F172A',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.1,
                        fill: false
                    }},
                    {{
                        label: 'SMA 273',
                        data: {json.dumps(chart_sma)},
                        borderColor: '#F59E0B',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.1,
                        borderDash: [5, 5],
                        fill: false
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'top',
                        labels: {{
                            font: {{ family: 'Outfit', size: 12 }}
                        }}
                    }},
                    tooltip: {{
                        mode: 'index',
                        intersect: false,
                        titleFont: {{ family: 'Outfit' }},
                        bodyFont: {{ family: 'Outfit' }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{
                            font: {{ family: 'Outfit' }},
                            maxTicksLimit: 12
                        }}
                    }},
                    y: {{
                        grid: {{ color: '#E2E8F0', borderDash: [2, 2] }},
                        ticks: {{
                            font: {{ family: 'Outfit' }},
                            callback: function(value) {{ return '$' + value.toLocaleString(); }}
                        }}
                    }}
                }}
            }}
        }});
    </script>

</body>
</html>
"""
    
    dashboard_path = OUTPUT_DIR / "dashboard.html"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Generated HTML dashboard at: {dashboard_path}")

# ── Main ──
def main():
    print("================================================================================")
    print("  WEEKLY BTC-USDT STRATEGY SIGNAL CHECK")
    print("================================================================================")
    
    # 1. Fetch data
    try:
        df = fetch_btc_data()
    except Exception as e:
        print(f"Error fetching data: {e}")
        sys.exit(1)
        
    # 2. Calculate SMA 273
    df["SMA_273"] = df["close"].rolling(window=273).mean()
    
    if len(df) < 273:
        print("Error: Historical data has fewer than 273 days. Cannot compute SMA.")
        sys.exit(1)
        
    # 3. Get latest values
    latest_date = df.index[-1]
    prev_date = df.index[-2]
    
    close_price = float(df["close"].iloc[-1])
    sma_val = float(df["SMA_273"].iloc[-1])
    
    prev_close = float(df["close"].iloc[-2])
    prev_sma = float(df["SMA_273"].iloc[-2])
    
    # Current and previous signal
    current_signal = 1 if close_price > sma_val else 0
    prev_signal = 1 if prev_close > prev_sma else 0
    
    last_update_str = latest_date.strftime("%Y-%m-%d")
    
    # 4. Generate Dashboard
    generate_html_dashboard(df, close_price, sma_val, current_signal, prev_signal, last_update_str)
    
    # 5. Prepare Telegram notification message
    status = "🟢 COMPRARE BTC / LONG" if current_signal == 1 else "🔴 VENDERE BTC / CASH (USDT)"
    action_info = ""
    
    if current_signal != prev_signal:
        action_info = "⚠️ *CAMBIO DI SEGNALE RILEVATO!* ⚠️\n"
        if current_signal == 1:
            action_info += "👉 Azione: acquista BTC al prezzo corrente (Close)."
        else:
            action_info += "👉 Azione: vendi BTC e converti interamente in USDT."
    else:
        action_info = "Trend invariato. Nessuna operazione richiesta."
        
    distance_pct = ((close_price / sma_val) - 1.0) * 100
    
    telegram_msg = (
        f"📊 *REPORT SETTIMANALE BTC-USDT (SMA 273)* 📊\n\n"
        f"• *Stato Trend*: {status}\n"
        f"• *Prezzo BTC (Close)*: ${close_price:,.2f}\n"
        f"• *Media SMA 273*: ${sma_val:,.2f}\n"
        f"• *Distanza dalla Media*: {distance_pct:+.2f}%\n\n"
        f"💡 *Azione*: {action_info}\n\n"
        f"🔗 _Dettagli e storico consultabili nel dashboard locale:_ `output_btc/dashboard.html`"
    )
    
    print("\nCalculated Signal Status:")
    print(f"Date: {last_update_str}")
    print(f"BTC Close: ${close_price:,.2f}")
    print(f"SMA 273: ${sma_val:,.2f}")
    print(f"Signal: {'BUY' if current_signal == 1 else 'CASH'}")
    print(f"Action: {action_info}")
    print("--------------------------------------------------------------------------------")
    
    # 6. Send Telegram if keys exist
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if telegram_token and telegram_chat_id:
        send_telegram_notification(telegram_token, telegram_chat_id, telegram_msg)
    else:
        print("Telegram keys not set in environment (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID). Skipping notification.")
        print("You can set them in your terminal or GitHub Secrets.")
        print(f"\nMessage that would be sent:\n\n{telegram_msg}")
        
    print("================================================================================")

if __name__ == "__main__":
    main()
