---
name: Cinema Commons
colors:
  surface: '#f8f9ff'
  surface-dim: '#d0dbed'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e6eeff'
  surface-container-high: '#dee9fc'
  surface-container-highest: '#d9e3f6'
  on-surface: '#121c2a'
  on-surface-variant: '#3d4947'
  inverse-surface: '#27313f'
  inverse-on-surface: '#eaf1ff'
  outline: '#6d7a77'
  outline-variant: '#bcc9c6'
  surface-tint: '#006a61'
  primary: '#00685f'
  on-primary: '#ffffff'
  primary-container: '#008378'
  on-primary-container: '#f4fffc'
  inverse-primary: '#6bd8cb'
  secondary: '#006398'
  on-secondary: '#ffffff'
  secondary-container: '#5bb8fe'
  on-secondary-container: '#00476e'
  tertiary: '#006947'
  on-tertiary: '#ffffff'
  tertiary-container: '#00855b'
  on-tertiary-container: '#f5fff6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#89f5e7'
  primary-fixed-dim: '#6bd8cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#005049'
  secondary-fixed: '#cce5ff'
  secondary-fixed-dim: '#93ccff'
  on-secondary-fixed: '#001d31'
  on-secondary-fixed-variant: '#004b73'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f8f9ff'
  on-background: '#121c2a'
  surface-variant: '#d9e3f6'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: '0'
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system establishes an approachable, organized, and community-driven interface tailored for student groups, clubs, and social circles coordinating movie nights. The visual aesthetic balances utilitarian clarity with social warmth, adopting a refined Modern SaaS / Community Event style.

The emotional core evokes collaborative excitement without clutter: it feels as lightweight as a study tool and as engaging as an entertainment platform. Visual hierarchy is achieved through crisp card containers, deliberate micro-interactions, distinct category tagging, and rich graphical media anchors (movie posters and backdrops). High contrast, precise layout grids, and restrained ornamentation allow community content—polls, RSVPs, screening schedules, and film artwork—to take center stage.

## Colors

The palette relies on high-legibility neutrals offset by ocean-leaning jewel tones, establishing a crisp and dependable visual environment.

- **Canvas & Surfaces**: The base page canvas rests on `#f4f6f8` (soft cool-gray), providing soft contrast against interactive containers. Card, dialog, and dropdown surfaces use pure `#ffffff` to elevate visual hierarchy.
- **Brand Accents**: The primary anchor is Teal (`#0d9488`), applied to primary actions, interactive focus rings, active tab states, and key navigational highlights. Ocean Blue (`#0284c7`) functions as a secondary accent for secondary controls, voting indicators, and links.
- **Borders & Dividers**: Subdued outline `#e2e8f0` provides soft structural boundaries without visual heaviness. Hover states on interactive cards elevate this border to `#cbd5e1`.
- **Typography & Text Hierarchy**: Slate-900 (`#1f2937`) drives high-contrast primary text and headings. Muted secondary metadata (dates, runtimes, ratings) uses `#64748b`, while placeholder text uses `#94a3b8`.
- **System Feedback**:
  - Success / Confirmed: Emerald Green (`#10b981`) for confirmed RSVPs, voted winners, and available seats.
  - Danger / Destructive: Crimson Red (`#ef4444`) for cancellations, event removals, and error states.

## Typography

The type hierarchy is powered by Inter across all levels to maintain systematic neutrality, geometric precision, and superior screen legibility. 

- Large titles adopt tighter letter-spacing (`-0.02em` to `-0.01em`) to create dense, confident editorial anchors suitable for film titles and event banners.
- Body text utilizes relaxed line-heights (`1.45` to `1.5`) for rapid parsing of screening details, synopsis snippets, and discussion threads.
- Label and tag tokens leverage semi-bold weights (`600`) with subtle positive tracking (`0.01em` to `0.03em`) to keep small metadata tags (PG-13, 118m, Sci-Fi) sharp and legible at a glance.

## Layout & Spacing

The layout is built on an adaptable 12-column fluid grid system bounded by a maximum desktop container width of `1280px`. 

- **Desktop (>= 1024px)**: 12-column layout, `1.5rem` (`24px`) gutters, `2rem` (`32px`) canvas page margins. Poster card grids scale in 4 or 6 columns depending on section density.
- **Tablet (768px - 1023px)**: 8-column layout, `1.5rem` gutters, `1.5rem` canvas margins. Film grids reflow to 3 or 4 columns; horizontal event sidebars wrap underneath main stage views.
- **Mobile (< 768px)**: 4-column layout, `1rem` (`16px`) gutters, `1rem` (`16px`) canvas margins. Film listings collapse into 2-column poster grids or stacked single-column listing rows with fluid horizontal overflow rails for quick genre browsing.
- **Rhythm**: All layout gaps, gutters, and inner paddings conform strictly to a base 4px/8px incremental scale (`0.25rem`, `0.5rem`, `1rem`, `1.5rem`, `2rem`).

## Elevation & Depth

This system avoids heavy drop shadows, relying primarily on subtle ambient elevation paired with low-contrast structural borders to ground content against the light-gray canvas.

- **Level 0 (Flat / Canvas)**: Background canvas (`#f4f6f8`), zero shadow, no border.
- **Level 1 (Card & Section Containers)**: `#ffffff` surface, bounded by a 1px solid `#e2e8f0` outline, accompanied by a diffused ambient shadow: `0 1px 3px 0 rgba(15, 23, 42, 0.05), 0 1px 2px -1px rgba(15, 23, 42, 0.05)`.
- **Level 2 (Interactive Hover / Floating Panels)**: Applied when hovering over movie cards, open filter popovers, or dropdowns. Outline transitions to `#cbd5e1`, paired with `0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.05)`.
- **Level 3 (Modals & Overlays)**: Event creation dialogs, film detail modals, and mobile bottom sheets. Uses `0 20px 25px -5px rgba(15, 23, 42, 0.1), 0 8px 10px -6px rgba(15, 23, 42, 0.06)`, anchored over a backdrop of `rgba(15, 23, 42, 0.45)` with a 4px blur.

## Shapes

The geometric signature uses unified, balanced radii to establish an inviting, modern community aesthetic.

- Base inputs, buttons, and badges feature `0.5rem` (`8px`) corner rounding.
- Standard content cards, movie media blocks, and event containers feature `0.75rem` (`12px`) corner rounding (`rounded-lg`).
- Modal windows, large callout panels, and sheet drawers utilize `1rem` (`16px`) corner rounding (`rounded-xl`).
- Status indicators and genre/certification chips use full pill shapes (`rounded-full` / `9999px`) to create clear geometric contrast against rectilinear cards.

## Components

### Buttons
- **Primary**: Solid teal background (`#0d9488`), white text (`#ffffff`), `0.5rem` radius, semi-bold typography (`label-md`). Hover state transitions to `#0f766e`. Active state scales subtly (`0.98`).
- **Secondary**: Crisp white background (`#ffffff`), 1px border `#e2e8f0`, dark slate text (`#1f2937`). Hover introduces `#f8fafc` surface and `#cbd5e1` border.
- **Destructive**: Pale red background (`#fef2f2`), `#ef4444` border and text. Hover darkens to `#dc2626` text with solid red fill accents.

### Badges & Chips
- **Certification Badges (PG, PG-13, R)**: Monospaced or tracked bold label typography (`label-sm`), 1px solid border (`#cbd5e1`), subtle neutral background (`#f1f5f9`), uppercase text, `4px` corner radius.
- **Genre & Tag Chips**: Pill-shaped (`rounded-full`), padding `4px 12px`. Light ocean background (`#f0f9ff`), ocean blue text (`#0284c7`), with hover support for filterable genres (`#e0f2fe`).

### Movie Poster Cards
- Built with a 2:3 aspect ratio image container. Rounded corners (`12px`) with `overflow: hidden`.
- Bottom overlay features an integrated dark gradient (`rgba(15, 23, 42, 0.85)` to `transparent`) for overlaying runtimes and community ratings (`★ 8.4`).
- Body section contains film title in `headline-sm`, screening host metadata, and a voting/RSVP CTA button. 
- Interactive cards elevate smoothly on hover with a `-2px` translateY transform and Level 2 shadow.

### Input Fields & Structured Forms
- Base surface `#ffffff`, 1px solid `#e2e8f0`, height `40px`, padding `0 12px`, `8px` radius.
- Focus state removes default browser outlines and sets a crisp 2px border in `#0d9488` with a matching 3px diffused outer halo (`rgba(13, 148, 136, 0.15)`).
- Error inputs swap the border to `#ef4444` and append an inline helper text in `body-sm`.

### Checkboxes & Voting Radios
- Size `18px x 18px`, border 1.5px `#cbd5e1`, radius `4px` (checkbox) or circular (radio).
- Checked state uses solid `#0d9488` background with an enclosed white checkmark icon or radial dot, animating with a gentle scale transition.

### Event Schedule Lists
- Stacked white cards separated by `0.75rem` vertical margins.
- Divided into three distinct zones: left-aligned time block (bold teal digits), central event details (movie title, location, host avatar), and right-aligned RSVP attendance stack.