# Report Strategia di Trend-Following BTC-USDT

Questo documento fornisce una spiegazione dettagliata della strategia di Trend-Following su **BTC** e **USDT**, della sua esecuzione operativa e dei risultati delle simulazioni confrontati con i principali benchmark di mercato (BTC Buy & Hold, QQQ e SPY).

---

## 1. Logica della Strategia

La strategia si basa su un principio fondamentale della finanza sistematica: il **trend following** (inseguimento del trend). Bitcoin (BTC) è un asset altamente volatile e ciclico, soggetto a mercati rialzisti (bull market) parabolici e mercati ribassisti (bear market) devastanti (con ribassi storici spesso superiori al 70-80%).

Per massimizzare il rendimento corretto per il rischio (Sharpe e Sortino ratio), la strategia utilizza un **filtro di trend a lungo termine** per regolare l'esposizione:
- **Fase Rialzista (Uptrend)**: Quando il prezzo di chiusura di BTC è superiore alla sua **Media Mobile Semplice a 273 giorni (273-day SMA)**, il portafoglio è allocato al **100% in BTC**.
- **Fase Ribassista (Downtrend)**: Quando il prezzo di chiusura di BTC scende al di sotto della **Media Mobile Semplice a 273 giorni (273-day SMA)**, il portafoglio liquida la posizione in BTC e si alloca al **100% in USDT (cash)**.

Questo approccio mira a catturare la maggior parte dei guadagni durante i cicli espansivi del mercato crypto, proteggendo interamente il capitale durante i prolungati mercati ribassisti.

---

## 2. Esecuzione Operativa e Dettagli Tecnici

Per garantire che la strategia sia robusta, realistica e replicabile nella realtà, sono state implementate le seguenti regole di esecuzione:

### A. Assenza di Look-Ahead Bias (Bias di Anticipazione)
I segnali operativi vengono calcolati al sabato sera in base al prezzo di chiusura di BTC e alla sua media mobile 273. L'operazione viene eseguita durante il rebalance settimanale della domenica. Il codice sposta il segnale di 1 giorno indietro (`signals = raw_signals.shift(1)`), simulando fedelmente il fatto che l'operatore decida ed esegua la domenica basandosi esclusivamente sui dati storici consolidati del giorno precedente.

### B. Frequenza di Rebalance Settimanale
Invece di negoziare quotidianamente (cosa che aumenterebbe esponenzialmente i costi di transazione e il rumore di fondo), la strategia verifica ed esegue i segnali solo **una volta alla settimana (la domenica alle ore 13:00 UTC)**. Questo riduce drasticamente i falsi segnali (whipsaws) che si verificano quando il prezzo oscilla attorno alla media mobile.

### C. Modellizzazione dei Costi di Transazione
Ogni trade (acquisto o vendita di BTC) include un modello di costo conservativo:
- **Taker Fee**: **0.10%** (commissione standard per ordini market su Binance).
- **Slippage**: **0.10%** (stima dell'impatto sul prezzo dovuto alla liquidità del book).
- **Costo Totale**: **0.20% per singolo lato** (0.40% per un ciclo completo di acquisto e vendita).

### D. USDT gestito come Cash
Nel simulatore, detenere USDT equivale a detenere `cash` sul conto denominato in USD. Questo evita commissioni di transazione fittizie per l'acquisto di una stablecoin ancorata a 1.0 e mantiene intatta la stima del capitale reale.

---

## 3. Risultati della Simulazione (Report)

La simulazione copre il periodo dal **26 Giugno 2021 al 23 Giugno 2026** (5 anni di dati storici giornalieri), partendo da un capitale iniziale di **$2.000,00**.

### Tabella Comparativa dei Risultati

| Metrica | Strategia (SMA 273) | BTC Buy & Hold | QQQ Buy & Hold | SPY Buy & Hold |
| :--- | :---: | :---: | :---: | :---: |
| **Capitale Iniziale** | $2.000,00 | $2.000,00 | $2.000,00 | $2.000,00 |
| **Capitale Finale** | **$8.490,49** | $3,886.46 | $4,157.93 | $3,672.25 |
| **Rendimento Totale** | **+324.5%** | +94.3% | +107.9% | +83.6% |
| **CAGR (Tasso Annuo)** | **+33.6%** | +14.2% | +15.8% | +13.0% |
| **Volatilità Annualizzata** | 34.9% | 53.0% | 27.3% | **20.7%** |
| **Sharpe Ratio** | **0.96** | 0.27 | 0.58 | 0.63 |
| **Sortino Ratio** | **1.13** | 0.38 | 0.82 | 0.87 |
| **Max Drawdown (Ribasso)** | -28.1% | -76.6% | -35.1% | **-24.5%** |
| **Numero di Trade** | 4 | - | - | - |
| **Commissioni Totali** | $40.29 | - | - | - |

I dati della simulazione mostrano una sovraperformance netta e sistematica della strategia SMA 273 rispetto a tutti i benchmark considerati (sia crypto che azionari classici).

---

## 4. Analisi delle Performance e Conclusioni

### A. Conservazione del Capitale (Mitigazione del Drawdown)
Il grafico della simulazione evidenzia come il Buy & Hold di BTC sia andato incontro ad un crollo del **-76.6%** durante il mercato ribassista del 2022. La strategia SMA 273 ha chiuso le posizioni in BTC alla fine del 2021/inizio 2022, conservando il capitale in USDT ed evitando l'intero bear market. Il drawdown massimo è stato limitato al **-28.1%**, persino inferiore a quello dell'indice Nasdaq-100 (QQQ, -35.1%).

### B. Efficienza dei Costi (Turnover Minimo)
Il rischio principale delle strategie basate su medie mobili è il costo dovuto a frequenti inversioni di rotta (whipsaw). Filtrando i segnali su base settimanale ed impostando un lookback ampio (273 giorni), la strategia ha effettuato solo **4 operazioni in 5 anni**. Le commissioni totali pagate sono state di soli **$40.29** (circa il 2.0% del capitale iniziale in 5 anni), rendendo la strategia estremamente efficiente e facilmente replicabile.

### C. Effetto Compounding (Capitalizzazione)
Uscendo dal mercato a livelli elevati e proteggendo i profitti, la strategia inizia il bull market successivo con una base monetaria notevolmente superiore rispetto al semplice accumulo passivo. Ad esempio, l'uscita da BTC a circa $104k a Novembre 2025 ha salvato il portafoglio dal successivo calo di BTC fino a $67k a Giugno 2026, consolidando un saldo finale di **$8.490,49** contro i **$3.886,46** del Buy & Hold di BTC.
