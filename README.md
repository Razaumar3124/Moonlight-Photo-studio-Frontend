# Moonlight Photo Studio

A web app for Moonlight Photo Studio (est. 1985). Customers create an account, then use the
**Memory Wall Planner** to lay out a gallery wall of framed photos and request a quote.

| Layer    | Stack                                                     | Owner    |
| -------- | --------------------------------------------------------- | -------- |
| Frontend | React 19, TypeScript, Tailwind CSS v4, Vite, React Router | Frontend |
| Backend  | Python, FastAPI, MongoDB                                  | Backend  |

## Repository layout

```
Moonlight Studio Project/
├── frontend/            React + TS + Tailwind app (this is where UI work happens)
├── backend/             FastAPI service (added by the backend teammate)
├── docs/                Project documentation — start here
└── reference_designs/   Source-of-truth mockups (login, register, memory_wall)
```

## Quick start (frontend)

Requires **Node.js 20.19+** (developed on Node 24).

```bash
cd frontend
npm install
cp .env.example .env.local   # then fill in values
npm run dev                  # http://localhost:5173
```

| Script              | What it does                                              |
| ------------------- | --------------------------------------------------------- |
| `npm run dev`       | Dev server with HMR; proxies `/api` → FastAPI             |
| `npm run build`     | Type-check, then production build to `dist/`              |
| `npm run preview`   | Serve the production build locally                        |
| `npm run lint`      | Lint with oxlint                                          |
| `npm run typecheck` | TypeScript check only                                     |
| `npm run format`    | Format with Prettier (sorts Tailwind classes)             |
| `npm run test`      | Unit tests (Vitest)                                       |
| `npm run check`     | **Quality gate:** typecheck + lint + tests + format check |

## Documentation

| Doc                                            | Read it when…                                           |
| ---------------------------------------------- | ------------------------------------------------------- |
| [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | Styling anything — colours, type, spacing, components   |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)   | Adding files, components, routes, or API calls          |
| [docs/RESPONSIVE.md](docs/RESPONSIVE.md)       | Building a screen — per-breakpoint layout rules         |
| [docs/ASSETS.md](docs/ASSETS.md)               | Adding images, SVGs, icons, or the logo                 |
| [docs/API_CONTRACT.md](docs/API_CONTRACT.md)   | Looking up an endpoint (backend-owned source of truth)  |
| [docs/API_ALIGNMENT.md](docs/API_ALIGNMENT.md) | Contract ↔ design mismatches and open backend questions |
| [docs/SECURITY.md](docs/SECURITY.md)           | Deploying (required headers) or touching auth/tokens    |
| [docs/ROADMAP.md](docs/ROADMAP.md)             | Checking what each phase delivers                       |
