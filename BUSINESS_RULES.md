# BUSINESS_RULES.md

Version: 1.0

Author: Siddhant Fursule

---

# Purpose

This document defines every business rule used by FabricBot.

It is the single source of truth for quotation behaviour.

If the Python implementation ever disagrees with this document, the code should eventually be updated to match this document.

Business knowledge belongs here.

Implementation belongs in Python.

---

# Business Overview

FabricBot generates quotations for furnishing products.

Current supported products

• Curtains

Future supported products

• Roller Blinds

• Roman Blinds

• Zebra Blinds

• Wooden Blinds

• Venetian Blinds

• Wallpapers

• Motorised Curtains

• Accessories

Every product should eventually have its own calculator while sharing the same quotation architecture.

---

# Core Quotation Philosophy

FabricBot mirrors the quotation spreadsheet currently used inside the business.

The spreadsheet is considered the business source of truth.

Rather than inventing a different quotation model, FabricBot intentionally follows the spreadsheet structure.

This makes validation easier and reduces operational mistakes.

---

# Spreadsheet Philosophy

Every spreadsheet row represents ONE TRACK.

Not one room.

Not one window.

Not one quotation.

One physical curtain track.

Examples

Living Room

Window 1

Main Curtain

↓

Row 1

Living Room

Window 1

Sheer Curtain

↓

Row 2

Bedroom

Window

Main Curtain

↓

Row 3

Every quotation is simply a collection of rows.

---

# Terminology

## Room

Examples

Living Room

Master Bedroom

Kitchen

Dining

Study

Rooms exist only to organise quotations.

Rooms do not affect calculations.

---

## Window

A physical opening.

A room may contain multiple windows.

Each window may contain multiple tracks.

---

## Track

The smallest billable quotation unit.

Every quotation calculation occurs at the track level.

Examples

Main Curtain

Sheer Curtain

Motorised Curtain

Ripple Curtain

Roman Blind

Roller Blind

Each track becomes one line item.

---

# Line Item

A Line Item represents one independently calculated quotation row.

Every Line Item contains

Product

Dimensions

Track Type

Fabric

Curtain Style

Pricing

The calculator operates on Line Items.

---

# Room → Window → Track Hierarchy

Customer View

House

↓

Rooms

↓

Windows

↓

Tracks

Internal View

Line Items

↓

Quotation Results

Customers never see line items.

Line items exist only for calculation.

---

# Required Inputs

Every quotation requires

Window Height

Window Width

Product Type

Everything else may have defaults.

If required information is missing, the quotation cannot be calculated.

---

# Default Values

Default Main Fabric Price

₹590 per meter

Default Sheer Fabric Price

₹490 per meter

Default Curtain Style

Pleated

Default Track

MTrack Premium

Default Order Type

Full

These defaults reduce unnecessary conversations.

---

# Fabric Rules

Fabric may be supplied in two ways.

Method 1

Customer specifies catalogue.

Example

NuHome Luna

↓

Search catalogue

↓

Use catalogue price.

Method 2

Customer does not specify catalogue.

↓

Use default pricing.

Quotation generation should continue whenever possible.

---

# Fabric Width

Fabric width should always come from catalogue data.

If unavailable

↓

Use configured default width.

Hardcoded widths should be avoided.

---

# Main Curtain

Main curtains are the decorative curtains.

They normally use premium furnishing fabric.

Default price

₹590/m

---

# Sheer Curtain

Sheers are lightweight translucent curtains.

Default price

₹490/m

---

# Curtain Styles

Currently supported

Pleated

Eyelet

Arabian

Ripple

Future styles should be added through configuration rather than code changes.

---

# Track Types

Current supported tracks

MTrack Premium

MTrack Silent

Standard Track

Golden Rod

SS Rod

I Track

Ripple Track

Motorised Track

Flat Track

Coloured Track

Every track type should eventually have configurable pricing.

---

# Fullness

Fullness controls fabric quantity.

It is a multiplier.

Examples

1.5×

2×

2.5×

3×

Higher fullness

↓

More fabric

↓

Higher quotation.

Fullness calculations belong entirely inside quotation.py.

---

# Fabric Calculation

Fabric quantity depends on

Window Width

↓

Fullness

↓

Fabric Width

↓

Panels

↓

Cut Length

↓

Total Fabric

This calculation must remain deterministic.

---

# Panel Calculation

Panel calculation determines how many curtain panels are required.

Panel calculations are entirely mathematical.

Gemini should never calculate panels.

---

# Cut Length

Cut length represents the fabric required for one panel.

It includes

Finished height

+

Allowances

Allowances should remain configurable.

---

# Stitching

Stitching cost depends on

Product

Style

Fabric

Business rules

Stitching calculations belong inside quotation.py.

---

# Track Calculation

Track cost depends on

Track Type

Track Length

Business pricing

Track calculations should remain configurable.

---

# Installation

Installation charges are determined separately from product costs.

Future versions may support

Location-based pricing

Minimum charges

Installer scheduling

---

# GST

GST is always calculated after all pre-tax costs.

GST calculations belong inside quotation.py.

Never inside AI prompts.

---

# Discounts

Discounts should always be applied after subtotal calculations.

Future versions may support

Percentage discounts

Fixed discounts

Room discounts

Quotation discounts

Customer-specific discounts

---

# Grand Total

Grand Total equals

All Line Item Totals

+

Installation

+

GST

−

Discounts

Grand Total should always be calculated after every line item has been completed.

---

# Catalogue Search Rules

Catalogue search should

Prefer exact match

↓

Supplier + Fabric

↓

Fabric only

↓

Fuzzy search

↓

Default pricing

Quotation generation should not fail because catalogue lookup failed.

---

# AI Rules

AI should

Extract

Normalise

Convert units

Generate JSON

AI should never

Calculate prices

Calculate GST

Calculate panels

Calculate stitching

Calculate totals

---

# Future Product Calculators

Every future product should receive its own calculator.

Examples

calculate_curtain()

calculate_roller_blind()

calculate_wallpaper()

calculate_motorised()

calculate_roman_blind()

Every calculator should produce the same output structure.

This allows reply formatting to remain generic.

---

# Configuration Philosophy

Business values should eventually move into config files.

Examples

GST

Default Prices

Track Pricing

Allowances

Fullness

Stitching Rates

The calculator should read configuration rather than hardcoding constants.

---

# Non-Negotiable Rules

These rules should never be violated.

✓ Every calculation must be deterministic.

✓ AI never performs mathematics.

✓ Every track equals one line item.

✓ Customers think in rooms and windows.

✓ Python thinks in line items.

✓ Business knowledge belongs in configuration or Python.

✓ The spreadsheet remains the operational reference.

✓ Defaults should reduce unnecessary customer interaction.

✓ Missing dimensions must never be invented.

✓ FabricBot should always prefer completing a quotation over rejecting one whenever safe defaults exist.