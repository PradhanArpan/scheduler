# Design Guide: Instrument, Not Stationery

> Locked design system for **Curriculum Scheduler** following the `ui-style-master` and `a11y-debugging` principles.

---

## 1. Visual Philosophy
- **Instrument, not stationery**: High utility, high information density, clear visual feedback.
- **Calibrated contrast**: All secondary text maintains a minimum 4.5:1 WCAG AA contrast ratio. No low-contrast faint grays on white.
- **Bespoke SVG iconography**: Stroke-based SVG icons throughout. Zero emojis used as interface icons.
- **Predictable layout**: 8px spatial grid with subtle hairline borders (`border-slate-200`) instead of heavy card elevation.

---

## 2. Color Palette & Design Tokens

| Token | Hex / Class | Purpose |
|---|---|---|
| `bg` | `#f8fafc` (`bg-slate-50`) | Global page canvas background |
| `surface` | `#ffffff` (`bg-white`) | Card & grid container surfaces |
| `surface-subtle` | `#f1f5f9` (`bg-slate-100`) | Header rows, subtle pill containers |
| `text-primary` | `#0f172a` (`text-slate-900`) | Headings, primary labels, table data |
| `text-secondary` | `#475569` (`text-slate-600`) | Secondary descriptions, timestamps |
| `text-muted` | `#64748b` (`text-slate-500`) | Micro-copy, metadata (min 4.5:1 ratio) |
| `border` | `#e2e8f0` (`border-slate-200`) | Hairline dividers, card outlines |
| `border-dark` | `#1e293b` (`border-slate-800`) | Dark navbar hairline border |
| `accent-primary` | `#4f46e5` (`bg-indigo-600`) | Primary actions, key callouts |
| `accent-hover` | `#4338ca` (`bg-indigo-700`) | Button hover state |
| `success` | `#047857` / `#ecfdf5` | Laboratory sessions, valid status |
| `warning` | `#b45309` / `#fffbeb` | Lunch recesses, soft constraint notes |
| `danger` | `#be123c` / `#fff1f2` | Conflict alerts, hard bottlenecks |

---

## 3. Typography Hierarchy

- **Display & UI**: `Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`, sans-serif
- **Code & Times**: `JetBrains Mono`, `ui-monospace`, monospace

| Level | Size | Weight | Line Height | Usage |
|---|---|---|---|---|
| H1 | 18px (`text-lg`) | Bold (`font-bold`) | Tight (`leading-tight`) | App Title, Page Section Titles |
| H2 | 14px (`text-sm`) | Bold (`font-bold`) | Normal | Card Titles, Modal Headers |
| Body | 12px (`text-xs`) | Medium / Regular | Normal | Grid Cells, Tables, Form Inputs |
| Caption | 11px / 10px | Medium / Semibold | Snug | Badges, Micro-labels, Subtitles |
| Code / Time | 10px / 11px | Mono Medium | Snug | Course Codes, Period Times, Room IDs |

---

## 4. Spacing Scale & Radius

- **Grid Step**: 4px base (4, 8, 12, 16, 24, 32, 48)
- **Border Radius**:
  - `small`: 6px (`rounded-md`) for badges, inputs, micro-buttons
  - `medium`: 8px (`rounded-lg`) for buttons, select dropdowns
  - `large`: 12px (`rounded-xl`) for cards, tables, modal containers

---

## 5. Component Standards

1. **Navigation Bar**:
   - Deep slate canvas (`bg-slate-900`) with hairline bottom divider (`border-slate-800`).
   - Integrated academic selectors (Academic Year, Semester Term) in subtle contrast capsules.
   - Clean SVG action buttons with consistent padding (`px-3 py-1.5`).
2. **Timetable Grid**:
   - High legibility, dark header (`bg-slate-900`), light subheadings (`bg-slate-100`).
   - Distinct cell states:
     - Theory: Indigo-tinted capsule (`bg-indigo-50 border-indigo-200 text-indigo-950`).
     - Laboratory: Emerald-tinted capsule (`bg-emerald-50 border-emerald-300 text-emerald-950`).
     - Lunch Break: Amber pill (`bg-amber-50/70 border-amber-300 text-amber-900`).
     - Closed Slot: Neutral muted slate (`bg-slate-100/60 text-slate-400`).
3. **Modal Dialogs**:
   - Backdrop: `bg-slate-900/60` with subtle blur.
   - Container: `rounded-2xl shadow-2xl border border-slate-200`.
   - Accessible roles (`role="dialog"`, `aria-modal="true"`) and keyboard `Escape` dismissal.
4. **Form Controls**:
   - Subtle background (`bg-slate-50`), crisp border (`border-slate-300`), active focus ring (`focus:ring-2 focus:ring-indigo-500`).
   - All inputs accompanied by an explicit label or accessible `aria-label`.

---

## 6. The Avoid List (Strictly Enforced)
- ❌ No purple-to-blue neon gradients.
- ❌ No emojis as interface icons (all replaced with bespoke SVGs).
- ❌ No low-contrast washed-out gray text.
- ❌ No centered layout on data-heavy tables.
- ❌ No bulky drop shadows.
- ❌ No unlabelled form inputs or non-keyboard accessible interactive elements.
