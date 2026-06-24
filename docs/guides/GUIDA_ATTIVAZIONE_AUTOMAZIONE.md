# Guida Passo-Passo: Attivazione dell'Automazione e Dashboard

Questa guida ti spiega esattamente dove cliccare e cosa inserire per attivare il monitoraggio automatico della strategia **BTC-USDT SMA 273** con notifiche Telegram e dashboard online su GitHub Pages.

---

## INDICE
0. [Fase 0: Caricamento dei file su GitHub (Push)](#fase-0-caricamento-dei-file-su-github-push)
1. [Fase 1: Creazione del Bot su Telegram](#fase-1-creazione-del-bot-su-telegram)
2. [Fase 2: Recupero del tuo Chat ID Personale](#fase-2-recupero-del-tuo-chat-id-personale)
3. [Fase 3: Configurazione delle Chiavi Segrete su GitHub](#fase-3-configurazione-delle-chiavi-segrete-su-github)
4. [Fase 4: Configurazione dei Permessi di Scrittura su GitHub](#fase-4-configurazione-dei-permessi-di-scrittura-su-github)
5. [Fase 5: Test di Funzionamento Manuale](#fase-5-test-di-funzionamento-manuale)
6. [Fase 6: Pubblicazione Online del Dashboard (GitHub Pages)](#fase-6-pubblicazione-online-del-dashboard-github-pages)

---

## Fase 0: Caricamento dei file su GitHub (Push)

Tutti i file dell'automazione (lo script `notify_signal.py`, la cartella `.github/workflows` con il file `run_weekly_check.yml` e la prima versione del dashboard) sono già stati creati sul tuo computer locale all'interno della cartella di questo progetto.

Finché non fai l'upload (il **push**) dei file su GitHub, i server di GitHub non conoscono l'esistenza del workflow e non possono avviarlo. 

Apri il terminale del tuo computer all'interno della cartella di questo progetto ed esegui i seguenti comandi:

```bash
# 1. Aggiungi i nuovi file creati, la cartella docs e il readme al tracciamento di git
git add scripts/notify_signal.py
git add .github/workflows/run_weekly_check.yml
git add config/strategy_btc.yaml
git add output_btc/dashboard.html
git add docs/
git add README.md

# 2. Registra la modifica locale
git commit -m "feat: aggiunta automazione notifiche, dashboard e riorganizzazione cartelle docs"

# 3. Invia i file al tuo repository online su GitHub
git push
```

Una volta eseguito il push, GitHub rileverà il file sotto `.github/workflows` e abiliterà il monitoraggio automatico. Puoi quindi procedere con la creazione del bot.

---

## Fase 1: Creazione del Bot su Telegram

1. Apri Telegram sul tuo telefono o computer.
2. Cerca **@BotFather** nella barra di ricerca (assicurati che abbia la spunta blu di account verificato) e avvia la chat cliccando su **Avvia** o digitando `/start`.
3. Invia il comando:
   ```text
   /newbot
   ```
4. Il bot ti chiederà un nome. Digita:
   ```text
   BTC SMA Monitor
   ```
5. Ora ti chiederà uno username univoco che deve terminare obbligatoriamente con `_bot`. Digita ad esempio:
   ```text
   il_tuo_nome_btc_monitor_bot
   ```
6. BotFather ti risponderà confermando la creazione e mostrandoti il **Token API**. Ha questo aspetto:
   ```text
   123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   ```
   **Copia questo codice**. Sarà il tuo `TELEGRAM_TOKEN`.
7. Clicca sul link del tuo bot appena creato (es. `t.me/il_tuo_nome_btc_monitor_bot`) e clicca su **Avvia** o digita `/start`. *Nota: Se non lo avvii, il bot non potrà inviarti messaggi.*

---

## Fase 2: Recupero del tuo Chat ID Personale

Il bot ha bisogno del tuo identificativo numerico per sapere a chi inviare i messaggi.

1. Nella barra di ricerca di Telegram cerca **@userinfobot**.
2. Avvia la chat.
3. Il bot ti risponderà immediatamente mostrando i tuoi dati.
4. Trova la riga **Id:** (è un numero composto da 9 o 10 cifre, es. `987654321`).
5. **Copia questo numero**. Sarà il tuo `TELEGRAM_CHAT_ID`.

---

## Fase 3: Configurazione delle Chiavi Segrete su GitHub

Per fare in modo che lo script su GitHub possa connettersi al tuo bot senza mostrare pubblicamente i tuoi codici:

1. Apri il browser e vai sul tuo repository GitHub di questo progetto.
2. Nel menu in alto del repository, clicca sulla scheda **Settings** (Impostazioni, icona dell'ingranaggio ⚙️).
3. Nella barra laterale sinistra, scorri verso il basso fino alla sezione **Security** e clicca su **Secrets and variables** > **Actions**.
4. Clicca sul pulsante verde **New repository secret** (in alto a destra).
5. Configura il primo segreto:
   * **Name**: `TELEGRAM_TOKEN`
   * **Secret**: *Incolla il token API che ti ha dato BotFather (Fase 1)*
   * Clicca su **Add secret**.
6. Clicca di nuovo su **New repository secret** per il secondo parametro:
   * **Name**: `TELEGRAM_CHAT_ID`
   * **Secret**: *Incolla il numero di ID che hai preso da @userinfobot (Fase 2)*
   * Clicca su **Add secret**.

---

## Fase 4: Configurazione dei Permessi di Scrittura su GitHub

L'automazione deve poter salvare ed aggiornare il file `output_btc/dashboard.html` all'interno del tuo repository ogni settimana. Per fare questo, dobbiamo abilitare i permessi di scrittura per i bot di GitHub.

1. Rimanendo in **Settings** (Impostazioni) del tuo repository GitHub.
2. Nella barra laterale sinistra, sotto la voce **Code and automation**, clicca su **Actions** > **General**.
3. Scorri la pagina fino in fondo fino alla sezione **Workflow permissions** (Permessi dei workflow).
4. Seleziona l'opzione **Read and write permissions** (Permessi di lettura e scrittura).
5. Spunta anche la casella **Allow GitHub Actions to create and approve pull requests** (se presente).
6. Clicca sul pulsante verde **Save** (Salva).

---

## Fase 5: Test di Funzionamento Manuale

Non devi aspettare domenica per verificare se tutto funziona. Puoi forzare un'esecuzione di prova immediata:

1. Nel menu in alto del tuo repository GitHub, clicca sulla scheda **Actions** (icona del play ▶️).
2. Nella barra laterale sinistra sotto *Workflows*, clicca su **Weekly BTC-USDT Strategy Monitor**.
3. Sulla destra apparirà una barra grigia con un menu a discesa chiamato **Run workflow** (Esegui workflow).
4. Clicca su **Run workflow** e poi sul pulsante verde **Run workflow** che compare nel popup.
5. Attendi circa 30-45 secondi. Vedrai apparire un cerchio verde di completamento con successo.
6. **Controlla il tuo Telegram**: dovresti aver appena ricevuto il primo report settimanale dal tuo bot!

---

## Fase 6: Pubblicazione Online del Dashboard (GitHub Pages)

Per poter consultare il grafico e lo storico delle transazioni direttamente dal browser del telefono tramite un link web pubblico e protetto:

1. Ritorna in **Settings** (Impostazioni) del tuo repository GitHub.
2. Nella barra laterale sinistra, sotto la sezione **Code and automation**, clicca su **Pages** (icona del browser 🌐).
3. Nella sezione **Build and deployment**:
   * Sotto **Source**, seleziona **Deploy from a branch** dal menu a discesa.
   * Sotto **Branch**, seleziona **main** (o la tua branch principale).
   * Lascia la cartella impostata su **/(root)**.
   * Clicca su **Save** (Salva).
4. Attendi circa 1-2 minuti.
5. Ricarica la pagina di GitHub Pages: in alto apparirà un box con il tuo link personalizzato, simile a:
   `https://tuo-username.github.io/nome-del-repository/`
6. Per vedere il dashboard specifico della strategia, aggiungi `output_btc/dashboard.html` alla fine del link, ad esempio:
   `https://tuo-username.github.io/nome-del-repository/output_btc/dashboard.html`

*D'ora in poi, ogni domenica alle 13:00 UTC, GitHub aggiornerà questo link e ti invierà la notifica su Telegram in automatico!*
