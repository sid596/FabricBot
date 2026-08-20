# AI_CONTEXT.md

Version: 1.0

Author: Siddhant Fursule

---

# Purpose

This document exists specifically for AI coding assistants.

Unlike README.md, this document does not explain how to run the project.

Unlike ARCHITECTURE.md, this document does not explain every module.

Instead, it explains how FabricBot should evolve.

Any AI modifying this repository should read this document before writing code.

---

# What is FabricBot?

FabricBot is an AI-powered quotation engine for a curtain and furnishing business.

It is NOT a general-purpose chatbot.

It is NOT an LLM experiment.

It is a production business tool whose primary responsibility is generating accurate quotations.

Accuracy is more important than cleverness.

Deterministic behaviour is more important than AI behaviour.

---

# Product Philosophy

FabricBot follows one principle:

AI understands.

Python calculates.

Never reverse these responsibilities.

---

# Current Development Direction

The project originally attempted to become conversational.

This approach has been abandoned.

Reasons include

- unreliable state management

- Gemini confusing slots

- excessive complexity

- poor maintainability

Current philosophy:

Customer sends ONE rich message.

↓

Gemini extracts structured data.

↓

Python calculates quotation.

↓

Reply returned.

Future development should optimise this workflow.

---

# What the AI should optimise

Future code should optimise

- better extraction

- better formatting

- faster search

- modular calculators

- maintainability

Future code should NOT optimise

- making conversations longer

- unnecessary follow-up questions

- remembering previous chats

- chat-like behaviour

---

# Preferred Customer Experience

Good interaction

Customer

"I have one bedroom.

Two windows.

Main curtains.

8 feet x 10 feet.

Premium track.

NuHome Luna."

↓

Quotation immediately.

Bad interaction

"What room?"

"What window?"

"What track?"

"What style?"

"What width?"

Avoid unnecessary conversations whenever possible.

---

# Missing Information

FabricBot should only ask for information that cannot safely be assumed.

Safe defaults

Main Fabric Price

₹590

Sheer Fabric Price

₹490

Curtain Style

Pleated

Track

MTrack Premium

Unsafe assumptions

Window dimensions

Fabric width if unavailable

Custom discounts

Never invent these values.

---

# AI Responsibilities

Gemini should perform

Natural language understanding

Intent detection

Room extraction

Window extraction

Track extraction

Catalogue extraction

Supplier extraction

Unit conversion

JSON generation

Gemini should NEVER perform

GST

Track pricing

Fabric mathematics

Panel calculations

Stitching calculations

Grand totals

Discount calculations

Those belong inside Python.

---

# Rich Message Philosophy

FabricBot assumes customers describe projects naturally.

Example

"I have

Master Bedroom

2 windows

Living Room

1 balcony

Use Luna everywhere

Use Oreo sheer

Premium tracks."

AI should convert this into structured quotation objects.

Python should never parse raw English.

---

# Internal Representation

Customer thinks

House

↓

Rooms

↓

Windows

↓

Curtains

Python thinks

Line Items

↓

Calculator

↓

Grand Total

Never expose internal representation to customers.

---

# Existing Features

Currently implemented

✅ Price lookup

✅ OCR

✅ Vision

✅ Google Sheets search

✅ Multi-line quotations

✅ WhatsApp integration

Future code should preserve all existing features.

---

# Existing Branches

main

Production branch.

Must always remain stable.

rich-quotation

Current development branch.

Contains multiline quotation work.

Future experimental work should occur on separate branches.

Never develop directly on main.

---

# Code Philosophy

Prefer

Readable code.

Simple code.

Explicit code.

Small functions.

Typed models.

Avoid

Nested conditionals.

Magic numbers.

Repeated logic.

Massive files.

Overengineering.

---

# Module Responsibilities

server.py

Coordinates everything.

Should not contain business logic.

quotation.py

Owns every quotation calculation.

Most important module.

ai.py

Language understanding only.

search.py

Catalogue resolution only.

vision.py

OCR only.

database.py

Persistence only.

Never mix responsibilities.

---

# Business Rules

Business rules belong in Python.

Examples

Track pricing

GST

Panel calculations

Allowances

Default prices

Never hide business rules inside prompts.

---

# Backwards Compatibility

Existing functionality should continue working after every change.

Examples

Price lookup

OCR

Vision

Single quotation

Multi-line quotation

Never remove a working feature while implementing a new one.

---

# Preferred Refactoring Style

Small changes.

Incremental improvements.

Minimal code movement.

Preserve interfaces where possible.

Avoid rewriting working modules without explicit reason.

---

# Error Handling

Graceful failure is preferred over crashes.

Catalogue missing

↓

Default pricing.

OCR failed

↓

Ask for clearer image.

Unknown fabric

↓

Continue quotation if defaults exist.

Unhandled exceptions should be logged.

---

# Logging

Important pipeline stages should always be logged.

Webhook

↓

AI

↓

Search

↓

Quotation

↓

Reply

↓

WhatsApp

Logging should explain what happened.

---

# Future Architecture

Future features should plug into the existing pipeline.

Customer

↓

AI

↓

Structured Objects

↓

Calculator

↓

Formatter

↓

WhatsApp

Do not bypass this architecture.

---

# Things Future AI Must NEVER Do

Never rewrite quotation mathematics without explicit instruction.

Never replace deterministic Python calculations with LLM reasoning.

Never remove OCR.

Never remove catalogue lookup.

Never make FabricBot conversational again.

Never move business logic into prompts.

Never hardcode configuration values.

Never rewrite code solely for style.

Never introduce unnecessary abstractions.

Never optimise prematurely.

---

# What Future AI SHOULD Do

Improve readability.

Reduce duplication.

Increase modularity.

Improve extraction.

Improve formatting.

Improve maintainability.

Keep public behaviour stable.

Document architectural decisions.

Always prefer deterministic behaviour over clever behaviour.

---

# Final Guiding Principle

Every code change should improve one of the following

Understanding

Calculation

Presentation

If it improves none of these,

it probably should not be implemented.