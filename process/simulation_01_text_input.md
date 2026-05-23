# Simulation 01 — Text Input to Final Output

> **Purpose:** Trace a real user request step by step through the full `User_Request_to_Delivery.md` pipeline to verify the process works end to end.

---

## User Input

```
Create a one-page website for my bakery. Name: "Forno di Marta".
I want a warm colour palette, a short about section, and a contact form.
```

**Input type:** Text (typed at dispenser / chat interface)  
**Timestamp:** 2026-05-23 10:04

---

## Step 1 — Stacy captures and routes the input

**Agent:** Stacy (Input-Orchestrator)

| Field | Value |
|-------|-------|
| Input type detected | Text |
| Language | Italian/English mixed |
| Voice-to-text needed | No |
| Intent extracted | Build a static website |
| Product type | Landing page (single page) |
| Key entities | Name: Forno di Marta · Style: warm colours · Sections: About, Contact form |

**Stacy output → routes to Gianni:**
```json
{
  "intent": "website_creation",
  "product_type": "static_landing_page",
  "specs": {
    "name": "Forno di Marta",
    "palette": "warm",
    "sections": ["hero", "about", "contact_form"]
  }
}
```

---

## Step 2 — Gianni analyses requirements

**Agent:** Gianni (Request-Analyzer)

| Check | Result |
|-------|--------|
| Complexity | Low — static HTML/CSS/JS |
| External dependencies | Contact form (needs backend or Formspree) |
| Estimated build time | < 5 min (AI-generated) |
| Stack selected | HTML + Tailwind CSS + Alpine.js |
| Deployment target | Vercel (free static hosting) |
| Blockers | None |

**Gianni output → routes to Chiara:**
```json
{
  "stack": "html-tailwind-alpine",
  "deploy": "vercel",
  "form_handler": "formspree",
  "ready_to_design": true
}
```

---

## Step 3 — Chiara generates the product

**Agent:** Chiara (Product-Generator)

Chiara calls the AI generation pipeline with Gianni's spec.

**Design decisions made:**
- Colour palette: `amber-50` background, `orange-700` accent, `stone-800` text
- Typography: Google Fonts — *Playfair Display* (headings) + *Inter* (body)
- Hero: full-width banner with bakery name + tagline
- About: 2-column layout, placeholder image + 3 sentences
- Contact: name / email / message fields → Formspree endpoint

**Output: `index.html`** (excerpt)
```html
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <title>Forno di Marta</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-amber-50 text-stone-800 font-sans">

  <!-- Hero -->
  <section class="bg-orange-700 text-white py-24 text-center">
    <h1 class="text-5xl font-serif">Forno di Marta</h1>
    <p class="mt-4 text-xl">Pane e dolci artigianali dal 1987</p>
  </section>

  <!-- About -->
  <section class="max-w-4xl mx-auto py-16 px-6 grid md:grid-cols-2 gap-12">
    <img src="bakery.jpg" class="rounded-xl shadow-lg" alt="Il forno">
    <div>
      <h2 class="text-3xl font-serif mb-4">Chi siamo</h2>
      <p>Siamo una piccola bakery artigianale nel cuore di Milano.
      Ogni giorno sforniamo pane fresco, croissant e torte fatte a mano.</p>
    </div>
  </section>

  <!-- Contact -->
  <section class="bg-orange-50 py-16 px-6 text-center">
    <h2 class="text-3xl font-serif mb-8">Contattaci</h2>
    <form action="https://formspree.io/f/YOUR_ID" method="POST"
          class="max-w-lg mx-auto space-y-4">
      <input name="name" placeholder="Nome" required
             class="w-full border border-orange-300 rounded-lg p-3">
      <input name="email" type="email" placeholder="Email" required
             class="w-full border border-orange-300 rounded-lg p-3">
      <textarea name="message" placeholder="Messaggio" rows="4" required
                class="w-full border border-orange-300 rounded-lg p-3"></textarea>
      <button type="submit"
              class="bg-orange-700 text-white px-8 py-3 rounded-lg hover:bg-orange-800">
        Invia
      </button>
    </form>
  </section>

</body>
</html>
```

**Chiara → routes to Stacy (QA):**
```json
{ "file": "index.html", "status": "generated", "ready_for_qa": true }
```

---

## Step 4 — Stacy runs QA

**Agent:** Stacy (QA-Agent)

| Check | Result |
|-------|--------|
| HTML valid | ✅ |
| All 3 sections present (hero, about, contact) | ✅ |
| Warm colour palette applied | ✅ |
| Contact form has all required fields | ✅ |
| Mobile responsive (Tailwind grid) | ✅ |
| No broken links or missing assets | ⚠️ `bakery.jpg` is a placeholder — noted for user |
| Accessibility (alt text, labels) | ✅ |

**QA verdict:** PASS (1 minor note on placeholder image)

**Stacy → routes to Marco:**
```json
{ "qa_passed": true, "notes": "bakery.jpg is placeholder", "ready_for_payment": true }
```

---

## Step 5 — Marco handles payment

**Agent:** Marco (Transaction-Manager)

| Item | Value |
|------|-------|
| Product | Static landing page, 1 page |
| Price | €9.90 |
| Payment method | Tap card / QR code payment |
| Status | ✅ Confirmed |
| Receipt | Digital — sent to user email |

**Marco → routes to Francesca:**
```json
{ "payment_confirmed": true, "receipt_id": "REC-20260523-001" }
```

---

## Step 6 — Francesca delivers the output

**Agent:** Francesca (Delivery-Agent)

**Delivery method:** Online link + dispenser printout

**Actions taken:**
1. Deployed `index.html` to Vercel → live URL generated
2. Sent URL to user via email / SMS
3. Printed QR code at dispenser pointing to the live site
4. Collected post-delivery feedback prompt

---

## Final Output

```
✅ CONSEGNA COMPLETATA

Sito web: https://forno-di-marta.vercel.app
Ricevuta: REC-20260523-001

Nota: sostituisci bakery.jpg con una foto reale
per personalizzare il sito.

Feedback? → bit.ly/aisma-feedback
```

---

## Process Summary

| Step | Agent | Time | Status |
|------|-------|------|--------|
| 1. Input capture & routing | Stacy | ~2 sec | ✅ |
| 2. Requirements analysis | Gianni | ~5 sec | ✅ |
| 3. Product generation | Chiara | ~40 sec | ✅ |
| 4. Quality assurance | Stacy | ~10 sec | ✅ (1 minor note) |
| 5. Payment | Marco | ~15 sec | ✅ |
| 6. Delivery | Francesca | ~8 sec | ✅ |
| **Total** | | **~80 sec** | **✅ DONE** |

---

> **Simulation result:** Process works end to end. From raw text input to live deployed website in under 2 minutes.
