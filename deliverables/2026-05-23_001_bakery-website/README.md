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

The hero section references `bakery.jpg`. Replace it with your own photo or any public image URL.

---

## Deploy

### GitHub Pages (free)
1. Push this folder to a GitHub repo
2. Settings → Pages → Source: main branch → `/` (root)
3. Your site is live at `https://<username>.github.io/<repo>/`

### Vercel (free, recommended)
```bash
npx vercel
```
Or drag-and-drop the folder at [vercel.com](https://vercel.com).

### Local preview
Open `index.html` directly in your browser — no server needed.

---

## No API Keys Needed for the site itself

The site is 100% static HTML + Tailwind CDN. The only external dependency is Formspree for the contact form.
