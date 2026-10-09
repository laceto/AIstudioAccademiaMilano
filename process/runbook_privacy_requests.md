# Runbook — richieste privacy dei clienti (accesso / cancellazione)

Per Luigi. Vale per il bot Telegram `@AIStudioMilanoBot`. Non è consulenza legale. Tempo di risposta: **entro un mese**
dalla richiesta. Appena arriva, annota la data e il `chat_id` del cliente (compare nel messaggio o nei log come `chat=<id>`).

## 1. Identifica il cliente

Il cliente scrive nel bot (o a `PRIVACY_CONTACT`, se impostato). Prendi il suo ID di chat numerico: lo trovi nella
richiesta stessa, nella notifica che ricevi (riga "Utente (chat)") o in Cloud Logging cercando il testo della richiesta
(`chat=<id>`). Controlla che chi scrive sia davvero quel cliente: rispondi nella stessa chat Telegram.

## 2. Trova i suoi dati (console, nessun comando)

1. Firestore, progetto `aistudio-milano`, database `(default)`, collezione `jobs`:
   <https://console.cloud.google.com/firestore/databases/-default-/data/panel/jobs?project=aistudio-milano>
2. Filtra per il campo `metadata.chat_id` uguale all'ID (è salvato come testo).
3. Per ogni documento trovato: `text` (cosa ha scritto), `classification`, `result` (file generato), `status`.
4. **Accesso:** copia questi contenuti e mandali al cliente nella chat. Se chiede rettifica, correggi il campo nel documento.

## 3. Cancellazione

### 3a. Percorso principale: `/cancella` su Telegram (solo tu)

1. Scrivi al bot `/cancella chat <chat_id>` (tutti i job di quel cliente; gli ID dei gruppi sono negativi) oppure
   `/cancella <job_id>` (un solo job).
2. Il bot **non cancella**: ti mostra una scheda con quanti job, stato e data di creazione (mai il testo del cliente) e due
   bottoni, Conferma e Annulla. Solo Conferma cancella. Premerlo due volte non fa danni e te lo dice.
3. I job in `running` o `delivering` non si cancellano (un worker potrebbe usarli): aspetta che finiscano o lancia `/sweep`,
   poi ripeti `/cancella`. Lo stato viene riletto al momento della cancellazione.
   Per una chat, Conferma cancella esattamente i job della scheda: se nel frattempo il numero e' cambiato non cancella
   nulla e ti mostra una scheda nuova. Se qualche cancellazione fallisce, il bot dice quanti job sono stati cancellati e
   quali no (registra comunque quelli cancellati): ripeti.
   **Limite noto:** controllo dello stato e cancellazione non sono un'unica operazione atomica. Nel raro caso in cui un
   worker prenda un job `approved` proprio tra i due passaggi, la run finisce come "persa" e il risultato potrebbe comunque
   arrivare nella tua chat Telegram. Cancellare un job `approved` e' invece sicuro: il worker lo salta.
4. Dopo la cancellazione il bot ti manda l'elenco di ciò che resta da fare a mano: i punti 2, 3 e 4 qui sotto
   (e-mail, messaggi nella tua chat, righe di log che scadono da sole dopo 30 giorni).
5. Resta un registro durevole nella collezione Firestore `erasures`: data e ora, il tuo ID, `job` o `chat`, quanti job e i
   loro ID casuali. Non contiene l'ID di chat, il testo o il risultato. Non ha TTL (decisione tua, vedi
   `docs/cloud-run-setup.md`). Nei log dell'applicazione c'e' una riga `[erasure]` con ID e conteggi.

### 3b. Alternativa se il bot non risponde: console Firestore

1. Nella console Firestore elimina ogni documento trovato in `jobs`. La protezione dalla cancellazione del database non
   blocca l'eliminazione dei documenti.
   Annota tu a mano la cancellazione (il registro `erasures` lo scrive solo `/cancella`).
2. Elimina dalla tua chat Telegram con il bot i messaggi di revisione che riguardano il cliente (testo e file inviati a te).
3. Elimina dalla tua casella e-mail le copie `[AI Studio] Richiesta da rivedere - job <id>` di quel cliente
   (nel cestino e poi svuota il cestino).
4. **Cloud Logging:** le righe `[conv]` con `chat=<id>` non si cancellano una per una e scadono da sole dopo 30 giorni.
   Dillo al cliente nella risposta.
5. OpenAI e Telegram conservano dati secondo le loro condizioni; Telegram è titolare autonomo per la sua parte.

## 4. Chiudi

Rispondi al cliente nella chat: cosa hai trovato / cancellato, e che i log scadono da soli entro 30 giorni. Annota in un
file privato: data della richiesta, data della risposta, `chat_id`, cosa è stato cancellato. Non scrivere il testo del cliente
nelle note.

## Promemoria

- I job si cancellano comunque da soli dopo il periodo di conservazione indicato nell'informativa (`JOB_RETENTION_DAYS`,
  default 90 giorni; la cancellazione automatica può arrivare fino a un giorno dopo).
- Cosa viene detto ai clienti: `/privacy` (`gateway/privacy.py`), vedi `docs/cloud-run-setup.md`, sezione 4b.
