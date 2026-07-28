# Call Time — hosted version with login

This is the same app you've been using in chat, wired up to a real database (Supabase) with
email/password login, so it can live at a real URL instead of a chat artifact.

## 1. Create a Supabase project
1. Go to https://supabase.com → sign up (free tier is plenty) → "New project"
2. Once it's created, go to **Project Settings → API** and copy:
   - **Project URL**
   - **anon public** key

## 2. Set up the database
1. In Supabase, open **SQL Editor → New query**
2. Paste in everything from `supabase-schema.sql` and click **Run**
3. This creates the table, locks it down so only signed-in users can read/write it, and turns on
   realtime sync (so teammates see each other's changes live).

## 3. Add your team as users
1. In Supabase, go to **Authentication → Users → Add user**
2. Add one entry per teammate with their email + a password (they can change it later)
3. No public sign-up page is exposed — only people you add here can log in

## 4. Plug your project into the app
1. Open `index.html`
2. Near the top, find:
   ```js
   const SUPABASE_URL = 'YOUR_SUPABASE_PROJECT_URL';
   const SUPABASE_ANON_KEY = 'YOUR_SUPABASE_ANON_KEY';
   ```
3. Replace both with the values from step 1

## 5. Deploy it
Easiest free option — Vercel:
1. Push this folder to a GitHub repo
2. Go to https://vercel.com → New Project → import that repo
3. Leave settings as default (it's a static site) → Deploy
4. You'll get a URL like `call-time-yourteam.vercel.app` — share that with your team instead of
   the chat artifact link

Netlify works the same way if you prefer it.

## What's different from the chat version
- Data lives in a real Postgres database instead of the artifact's storage
- Access requires signing in — no more "anyone with the link can edit"
- Changes sync live between teammates
- Everything else (multiple candidate lists, CSV import, categories, call logging, the skip
  button) works exactly the same

## If you want a custom domain
Once deployed on Vercel or Netlify, both let you attach a domain you own under
**Project Settings → Domains** — useful if you'd rather share something like
`calltime.yourcampaign.com`.
