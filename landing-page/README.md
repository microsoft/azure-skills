# Azure Skills landing page maintenance

This directory contains the Astro app that powers the public landing page:

- **Production URL:** https://microsoft.github.io/azure-skills/
- **Source root:** `landing-page/`

## Prerequisites

- Node.js 22+ (or a version compatible with the lock file)
- npm

## Local development

From the repository root:

```bash
cd landing-page
npm ci
npm run dev
```

Open `http://localhost:4321/azure-skills/` (or the port Astro prints).

Local npm commands use your environment and user-level npm configuration. To match
CI when installing or updating dependencies, pass
`--registry=https://packagefeedproxy.microsoft.io/npm/ --omit-lockfile-registry-resolved=true`
to `npm ci` or `npm install`. The second option keeps registry package URLs out of
generated lockfiles.

## Build and preview

```bash
cd landing-page
npm run build
npm run preview
```

Build output is written to `landing-page/dist/`.

## Where to make changes

- **Page structure/content composition:** `landing-page/src/pages/index.astro`
- **Reusable UI pieces:** `landing-page/src/components/`
- **Theme/layout/meta tags:** `landing-page/src/layouts/BaseLayout.astro`
- **Styles:** `landing-page/src/styles/global.css`
- **Brand assets (logo, favicon, OG image):** `landing-page/public/`
- **Data-driven skill/install/workflow content:** `landing-page/src/lib/site-data.ts`

`site-data.ts` reads these repository-level files to keep the landing page aligned with plugin data:

- `skills/**/SKILL.md`
- `plugin.json`
- `gemini-extension.json`

## Deployment

GitHub Pages deployment is handled by `.github/workflows/pages.yml`.

The build job sets `NPM_CONFIG_REGISTRY` to Microsoft's package proxy and
`NPM_CONFIG_OMIT_LOCKFILE_REGISTRY_RESOLVED` to `"true"` through environment variables.

- On **pull requests**, the workflow runs install/build validation only.
- On **push to `main`**, it builds and deploys to GitHub Pages.

Workflow triggers include:

- `landing-page/**`
- `skills/**`
- `plugin.json`
- `gemini-extension.json`
- `.github/workflows/pages.yml`

## Updating screenshots for PRs

PR screenshots currently live in:

- `assets/site-preview/azure-skills-light.png`
- `assets/site-preview/azure-skills-dark.png`

Capture fresh full-page screenshots from a local preview when visual changes are introduced.
