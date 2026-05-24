# Deliverable 001 — Forno di Marta Website

> Purpose: Deployable static website for a bakery. Tailwind CSS, hero/about/contact form.
> Owner Agent: Chiara
> Status: active

## Credentials Required

| Credential | Required | Where to get it |
|---|---|---|
| Formspree Form ID | **Yes** — contact form won't work without it | [formspree.io](https://formspree.io) |

---

## Setup

### 1. Get a Formspree Form ID

1. Go to [formspree.io](https://formspree.io) and sign up (free tier: 50 submissions/month)
2. Create a new form → set the destination email
3. Copy your Form ID — it looks like `xpzgkrjb`

### 2. Replace the placeholder in `index.html`

Open `index.html` and find:
```html
action="https://formspree.io/f/YOUR_FORM_ID"
```
Replace `YOUR_FORM_ID` with your actual ID:
```html
action="https://formspree.io/f/xpzgkrjb"
```

### 3. (Optional) Replace the hero image

The hero section references `bakery-placeholder.svg` — an honest "Foto da sostituire" placeholder. Replace it with your own photo (any name) and update the `src` in `index.html`.

---

## Warranty fix (2026-05-24, request 011, ISS-016)

Two defects from the original delivery were fixed at no charge by the V2 Team's recommendation:

1. **Placeholder image**: `bakery.jpg` (which never existed and produced a broken-image icon) was replaced with a local `bakery-placeholder.svg` that visibly reads "Foto da sostituire con vetrina reale". Visitors now see an honest placeholder instead of a broken icon.
2. **Form sentinel**: a small JS guard in `index.html` intercepts form su