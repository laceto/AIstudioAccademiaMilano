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

1. Nella console Firestore elimina ogni documento trovato in `jobs`. La protezione dalla cancellazione del database non
   blocca l'eliminazione dei documenti.
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
