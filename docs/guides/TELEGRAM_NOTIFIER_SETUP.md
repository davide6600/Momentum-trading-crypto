# Guida di Setup del Notificatore Telegram e Dashboard

Questo repository contiene un sistema automatico e gratuito per monitorare la strategia **BTC-USDT SMA 273**, ricevere segnali su Telegram e visualizzare lo stato su un dashboard web.

Ecco come configurarlo in 3 semplici passaggi.

---

## 1. Creare il Bot Telegram ed ottenere il Token

1. Apri Telegram e cerca **@BotFather** (l'account ufficiale per creare bot).
2. Avvia la chat e invia il comando:
   ```text
   /newbot
   ```
3. Segui le istruzioni: assegna un **nome** al bot (es. `BTC SMA Monitor`) e uno **username** univoco che deve terminare in `_bot` (es. `mio_btc_sma_monitor_bot`).
4. BotFather ti invierà un messaggio contenente il tuo **HTTP API Token** (avrà un aspetto simile a `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`). Questo è il tuo `TELEGRAM_TOKEN`.

---

## 2. Ottenere il tuo Chat ID Telegram

Per ricevere i messaggi, il bot deve sapere a quale chat o canale inviarli.

1. Avvia la chat con il bot appena creato cliccando sul link fornito da BotFather (es. `t.me/tuo_bot`) e clicca su **Avvia** (`/start`).
2. Per trovare il tuo ID utente personale:
   - Cerca su Telegram il bot **@userinfobot** o **@MissRose_bot**.
   - Avvia la chat o digita `/id`.
   - Il bot ti risponderà con un numero (es. `987654321`). Questo è il tuo `TELEGRAM_CHAT_ID`.

---

## 3. Inserire le Chiavi nei GitHub Secrets

Per permettere a GitHub Actions di inviare i messaggi in modo sicuro senza esporre i tuoi codici:

1. Vai sulla pagina del tuo repository su **GitHub**.
2. Clicca su **Settings** (Impostazioni) > **Secrets and variables** > **Actions**.
3. Clicca su **New repository secret** e aggiungi:
   - Nome: `TELEGRAM_TOKEN` | Valore: *Inserisci il token di BotFather*
   - Nome: `TELEGRAM_CHAT_ID` | Valore: *Inserisci il tuo Chat ID*

---

## 4. Visualizzare il Dashboard

Il dashboard viene generato automaticamente ogni domenica come file HTML statico in:
`output_btc/dashboard.html`

Puoi aprirlo localmente sul tuo computer facendo doppio clic sul file per consultare i grafici e lo storico.

### Opzionale: Pubblicare il Dashboard online gratis (GitHub Pages)
Se desideri consultare il dashboard dal telefono ovunque ti trovi tramite un link web protetto:
1. Vai in **Settings** del repository GitHub.
2. Clicca su **Pages** nella barra laterale sinistra.
3. Sotto **Build and deployment** > **Source**, seleziona **Deploy from a branch**.
4. Imposta la branch su `main` e la cartella su `/ (root)` o `/docs` (se sposti l'output lì), e clicca su **Save**.
5. GitHub ti fornirà un link pubblico (es. `https://tuonome.github.io/nome-repo/output_btc/dashboard.html`) per consultare lo stato in tempo reale.
