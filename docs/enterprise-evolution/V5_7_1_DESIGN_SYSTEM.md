# BITORA V5.7.1 Design System

## V5.7.2 Admin Integration

V5.7.2 promotes this Design System from visual foundation to the authority for the real BITORA admin integration. It must be reused by V5.8+ instead of creating a second Enterprise visual language.

Admin integration tokens now live in the real frontend stylesheet:

- `--bt-arena: #D2B89A`
- `--bt-arena-dark: #C3A381`
- `--bt-arena-light: #E4D3BF`
- `--bt-ink: #102033`
- `--bt-ink-soft: #46586a`
- `--bt-surface: #ffffff`
- `--bt-surface-soft: #f6f8f8`
- `--bt-border: #d9e0e3`
- `--bt-radius: 8px`
- `--bt-radius-sm: 6px`

The Enterprise admin shell consists of:

- Sidebar with BITORA identity, grouped navigation and selected/hover states.
- Operational topbar with current event, phase, system state and freshness.
- Workspace with KPI row, Venue Map, activity stream, alerts, Projected/Access/Camera, devices and system health.
- Responsive desktop/tablet/mobile layouts.

Status must always be expressed with color, text and an outline icon. Emojis are not part of the BITORA Enterprise interface.

Data rules:

- No production path may hardcode demo values like `3.842`, `42/min` or `84%`.
- `PROJECTED`, `ACCESS` and `CAMERA` are separate sources.
- `CAMERA` without integration is `UNAVAILABLE`, never `0`.
- Failed secondary modules render `UNAVAILABLE` and do not break Command Center.

## Tokens

The Enterprise UI uses centralized CSS tokens in:

- `docs/enterprise-evolution/V5_7_1_DESIGN_SYSTEM.css`

Core token groups:

- brand colors;
- warm neutral surfaces;
- semantic status colors;
- text colors;
- borders;
- radius;
- shadows;
- spacing;
- icon sizes;
- font sizes.

## Visual Language

BITORA Enterprise should feel modern, operational, precise and calm. Brand sand/copper is an accent, not a full-page beige theme.

## Components

Foundation components represented in V5.7.1:

- AppShell;
- Sidebar;
- TopBar;
- EventPhaseBadge;
- MetricCard;
- AlertCard;
- VenueMap;
- MapToolbar;
- MapLegend;
- DeviceCard;
- Activity/summary panel;
- Unavailable semantics.

## Status Rules

Operational status must use color plus text. Color alone is not sufficient.

Semantic colors:

- green: normal / online;
- amber: warning;
- red: critical;
- gray: inactive / unavailable.

## Venue Map

The venue map is operational, not decorative. It supports:

- SVG/background foundation;
- overlays;
- layers;
- selected/hover states;
- drill-down data model;
- projected/access/camera separation.

## Responsive Rules

Desktop is primary. Tablet keeps operational capability. Mobile gives a condensed operational summary.
