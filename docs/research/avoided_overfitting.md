Viewed ANALISI_OTTIMIZZAZIONE_LOOKBACK.md:14-56

Ecco una spiegazione approfondita su come abbiamo evitato l'overfitting, seguita da una proposta pratica e semplice per mettere in produzione la strategia ricevendone i segnali in tempo reale.

---

## 1. Come abbiamo evitato l'Overfitting (e in cosa consiste)

### Cos'è l'Overfitting (Sovradattamento)?
L'**overfitting** si verifica quando un modello di trading viene ottimizzato così tanto sui dati del passato (dati *in-sample*) da iniziare a memorizzare il **rumore casuale** del mercato invece di catturare una reale inefficienza o trend strutturale. 
* Un sistema "overfitted" mostrerà profitti straordinari nei backtest storici, ma fallirà non appena verrà messo in funzione con denaro reale (dati *out-of-sample*), poiché le condizioni di mercato e il rumore casuale cambiano continuamente.

### Come lo abbiamo evitato in questa analisi:

1. **Analisi di Stabilità del Vicinato (Neighbor Stability Analysis)**:
   Invece di selezionare semplicemente il singolo valore di lookback con il rendimento più alto (che potrebbe essere un picco fortunato dovuto al perfetto tempismo di una singola candela storica), abbiamo calcolato lo **Sharpe Ratio medio dei vicini (intorno di ±5 giorni)**.
   * La **SMA 273** si trova al centro di un *plateau* stabile (da 273 a 277 giorni) dove i risultati sono identici. Questo dimostra che la performance è guidata dal trend macro e non da una micro-calibrazione fortunata.

2. **Limite di Frequenza Settimanale (Regularization)**:
   La decisione di verificare i segnali **solo una volta alla settimana (la domenica)** agisce come regolarizzatore naturale. Elimina il rumore dei movimenti giornalieri di BTC, riducendo drasticamente il rischio di sovradattamento ai movimenti intraday.

3. **Parsimonia Parametrica (Rasoio di Occam)**:
   La nostra strategia ha **un solo parametro**: il periodo della media mobile (273). Non abbiamo stop-loss rigidi ottimizzati, filtri di volumi ad-hoc o indicatori secondari. Meno parametri ci sono, minore è lo spazio matematico per l'overfitting.

4. **Penalizzazione Realistica dei Costi**:
   Applicare commissioni e slippage pesanti (0.20% a trade) ha eliminato sul nascere i parametri a breve termine (es. lookback a 10-30 giorni) che sembrano profittevoli senza commissioni ma che nella realtà vengono distrutti dai costi operativi.

