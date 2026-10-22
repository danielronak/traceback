# Deploying PyMentor

PyMentor is a static site: no server code, no database, no accounts. Every
learner's browser downloads the app once (about 5.5 MB compressed, mostly the
Python runtime) and then runs everything itself, offline. Hosting it costs
nothing on any free static host.

## Recommended: Cloudflare Pages

Cloudflare Pages is free, serves files from a global network, and honours the
`app/public/_headers` file. That file sends the cross-origin isolation headers
that `input()` needs (D9).

One-time setup, in the Cloudflare dashboard:

1. **Workers & Pages → Create → Pages → Connect to Git**, and pick the
   `traceback` repository.
2. Build settings:

   | Setting | Value |
   | --- | --- |
   | Production branch | `main` |
   | Framework preset | None |
   | Root directory | `app` |
   | Build command | `npm ci && npm run build` |
   | Build output directory | `dist` |

3. **Environment variables → Production and Preview:** set `NODE_VERSION` to
   `22`.
4. Save and deploy. Every push to `main` deploys to production, and every PR
   gets its own preview address.

The build reads `../engine` and `../curriculum` from the repository. That
works because Cloudflare clones the whole repository; the root directory only
sets where the commands run.

### Checking a deploy

Open the site and check:

- The status shows **Python 3.14 ready** within a few seconds.
- A program with `input()` asks for an answer in the console. If it says
  "can't read input()", the headers aren't arriving; check that `_headers`
  is in the build output.
- After one visit, the app still opens and runs code with the network off.

## Other hosts

Any static host works. The service worker adds the isolation headers itself,
so on hosts that can't send them (GitHub Pages, for example) `input()` works
after a single automatic reload on the first visit (D26).

- **Netlify:** the same settings (base directory `app`, build
  `npm ci && npm run build`, publish `dist`). Netlify reads `_headers` too.
- **GitHub Pages:** build `app/dist` in a workflow and publish it. If the site
  lives under a sub-path (`/traceback/`), set Vite's `base` to that path.

## What a deploy never includes

No analytics, no error reporting, no third-party scripts or fonts. Learner
progress and feedback stay in the browser (IndexedDB) unless a learner
downloads their feedback themselves (Settings → Download feedback). Keep it
that way: it's principle 3 in `docs/vision.md`.
