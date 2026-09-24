---
version: alpha
name: Luma Android Events
description: Frosted-glass event cards over a pastel welcome wall, rounded Plus Jakarta Sans headings, a card-driven date-grouped feed, a warm pink-to-orange brand gradient and a deep indigo detail page. Covers the first batch (welcome, sign-in sheet, home feed, Discover, event detail, create form).
colors:
  surface: "#FFFFFF"
  canvas: "#F5F6F8"
  tabBar: "#F4F5F6"
  card: "#FFFFFF"
  ink: "#1A1A1A"
  inkStrong: "#4C4B4C"
  muted: "#9B9BA0"
  placeholder: "#B0B0B5"
  divider: "#ECECEE"
  brandStart: "#DA60BF"
  brandPink: "#F65A90"
  brandEnd: "#F3AB5A"
  buttonStart: "#F65991"
  buttonEnd: "#F79E5C"
  promoPink: "#FFE0E8"
  promoYellow: "#FEECD7"
  promoMint: "#E3F0EA"
  promoBlue: "#CEF0F5"
  detailBg: "#0A0922"
  detailMuted: "#9CA3AF"
  nearCapacity: "#D97706"
  nearCapacityBg: "#FEF3C7"
  waitlistBlue: "#2563EB"
  waitlistBg: "#EFF6FF"
typography:
  largeTitle:
    fontFamily: Plus Jakarta Sans
    fontSize: 34
    fontWeight: 800
  sectionTitle:
    fontFamily: Plus Jakarta Sans
    fontSize: 26
    fontWeight: 700
  cardTitle:
    fontFamily: Plus Jakarta Sans
    fontSize: 20
    fontWeight: 700
    lineHeight: 27
  body:
    fontFamily: Plus Jakarta Sans
    fontSize: 16
    fontWeight: 400
  meta:
    fontFamily: Plus Jakarta Sans
    fontSize: 14
    fontWeight: 400
  small:
    fontFamily: Plus Jakarta Sans
    fontSize: 12
    fontWeight: 400
  button:
    fontFamily: Plus Jakarta Sans
    fontSize: 26
    fontWeight: 600
spacing:
  page: 16
  row: 12
  card: 16
  section: 24
rounded:
  pill: 999
  card: 16
  cover: 14
  field: 24
  sheet: 28
  detailCover: 24
---

## Overview

Based on Luma Android 2.3, English, light theme, default font scale, on a 393 dp wide phone frame. This document covers the first release batch only — the welcome wall, the sign-in sheet, the home feed ("Picked for You"), Discover (popular events and categories), the dark event detail page and the create-event form. Notifications and Chat are empty states. It is not a complete system for every Luma screen.

## Colors

The home and discover surfaces are white; the create canvas is a light grey `#F5F6F8`; the tab bar is `#F4F5F6`. Text is `ink`, with `inkStrong`, `muted` and `placeholder` carrying hierarchy. The welcome wall lays a horizontal pastel gradient (pink `#FFE0E8` → peach → yellow `#FEECD7` → mint `#E3F0EA` → sky `#CEF0F5`) across the top third, fading to white. The brand gradient (magenta `#DA60BF` → pink `#F65A90` → orange `#F3AB5A`) is reserved for the welcome hero, the round get-started button and the sparkle; ordinary chrome stays neutral. The detail page is a deep indigo `#0A0922` gradient. Status badges use amber (`#D97706` on `#FEF3C7`) for Near Capacity and blue (`#2563EB` on `#EFF6FF`) for Waitlist Open.

## Typography

Every label uses Plus Jakarta Sans, the rounded geometric face Luma ships with. Screen titles are large and extra-bold (34 / 26), event titles are bold 20 with a 27 dp line, body copy is regular 16, metadata is regular 14, and the welcome primary button is a tall 26 medium. Hierarchy comes from weight and the greyscale ramp rather than colour.

## Layout

Everything is laid out on a 393 dp frame with 16 dp side margins. The welcome wall centers the wordmark and tagline around 45% height with a scattered collage of frosted-glass cards. The feed places a 44 dp avatar / wordmark / settings header, then section headers ("Your Events", "Picked for You"), a date divider, and rows of 73 dp square covers with a host marker, title and clock/pin metadata. Discover swaps the wordmark for a title plus map and search icons. The floating Create Event pill sits above the tab bar on the right; content scrolls beneath it.

## Elevation & Depth

The welcome cards are translucent white with a 1 dp white border and a blur over real artwork. The sign-in sheet rises with a 36 dp rounded top, covering the lower page. White cards and fields on the create page are flat, separated by background colour rather than borders. The floating Create Event pill carries a soft shadow. The detail page uses flat translucent circular controls over the cover.

## Shapes

Covers and cards use 14–16 dp radii; form fields and the create FAB are heavily rounded (24–26 dp); the sign-in sheet uses 36 dp at the top and the primary sign-in button 18 dp; the detail cover card uses 24 dp. The tab bar's active state is a soft `#E3E4E6` pill behind the icon only, with the label below it.

## Components

The home feed groups events by date with a bold date, a grey slash and a grey weekday; each row holds a square cover, a host marker (dotted brand mark, an overlapping avatar stack or a small square logo), a two-line title and clock / pin metadata, with optional status badges. Discover adds a "Popular Events" list with the same row grammar and a horizontally scrolling "Browse by Category" chip row of tinted line icons. The detail page shows a rounded cover card with a "Featured in San Francisco" bar, the event title, a host row with chevron, the time, four translucent action slots, and a Location section. The create form stacks a cover upload well with a circular black add button, an Event Name field, a start/end timeline (filled dot, dotted connector, hollow dot, horizontal divider) with date/time pills, location and description fields, a Ticketing heading and a Require Approval toggle.

## Do's and Don'ts

Use real text, local state and the bundled typeface. Never ship screenshots of the app as working UI or hotspot shells: covers are cropped artwork inside real image components, icons are inline SVG, and every navigation target renders a real screen. Keep the brand gradient rare; do not tint ordinary controls with it.

## Responsive Behavior

Mobile-first at 393 dp. The column is centred on wider screens with a max width of 480 dp; scrollable screens (feed, discover, detail, create) keep the tab bar / nav reachable at the bottom.

## Iteration Guide

Change a value in `src/tokens.ts`, rebuild, and recheck every screen that uses it; tokens are shared across screens, so one change moves several.

## Known Gaps

- Only the first batch of screens is refined; Notifications and Chat are empty states and ticketing/guests/calendar/profile are not built.
- Event data and artwork are a fixed local set; search, filters, maps, real host data and authentication are not modelled.
- Date/time pickers and image upload are visual only; the create timeline and toggle do not persist.
- A few small host marks and icons are close approximations; the profile avatar is a plain gradient.