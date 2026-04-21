# Remove Dead Layouts and Legacy NavBar

**Date:** 2026-04-21
**Status:** Approved

## Problem

Frontend contains dead code from layout evolution:

1. **`SidebarLayout.tsx`** — copy of `ClassicLayout.tsx`, never diverged, never used in production (default is `classic`)
2. **`NavBar.tsx`** — legacy navigation bar, replaced by `PageToolbar` on 2026-04-11, zero imports in codebase
3. **`AppLayout.tsx`** env-switcher — reads `VITE_LAYOUT` to pick between Classic/Sidebar, unnecessary with single layout

## Solution

### 1. Inline ClassicLayout into AppLayout

Replace the switcher in `AppLayout.tsx` with the actual layout code from `ClassicLayout.tsx`:
- AmbientBlobs + PageToolbar + Outlet + ToolbarSlots context
- Remove imports of ClassicLayout and SidebarLayout

### 2. Delete dead files

- `frontends/web/src/layouts/ClassicLayout.tsx`
- `frontends/web/src/layouts/SidebarLayout.tsx`
- `frontends/web/src/components/NavBar.tsx`

### 3. Clean up env config

- Remove `VITE_LAYOUT` from `.env.example`

### 4. Verify no remaining references

- Grep for `ClassicLayout`, `SidebarLayout`, `NavBar`, `VITE_LAYOUT` across codebase
- `npm run build` must pass
- UI must look identical (no visual changes)

## What stays unchanged

- `PageToolbar.tsx` — active toolbar
- `NavPill.tsx` — toolbar pill components (BackPill, CenterBrand)
- `useToolbarSlot.ts` — slot hook for page-specific toolbar content
- Theme system, AmbientBlobs, all page components
