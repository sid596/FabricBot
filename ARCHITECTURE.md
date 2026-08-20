# FabricBot Architecture
Version: 1.0

Author: Siddhant Fursule

---

# 1. Introduction

FabricBot is an AI-powered WhatsApp assistant built for a curtain and furnishing business.

Unlike traditional chatbots that rely on rigid decision trees, FabricBot uses Large Language Models (LLMs) to understand natural language and convert customer requests into structured data which can then be processed by deterministic business logic.

FabricBot is designed around one philosophy:

> AI understands.
> Python calculates.

The AI should never perform quotation calculations.

The AI's only responsibility is understanding the customer's intent and extracting structured information.

Everything mathematical is performed by Python.

---

# 2. Product Vision

FabricBot aims to become an AI employee rather than a chatbot.

The end goal is not to have long conversations with customers.

Instead, customers should be able to naturally describe everything they want in one message, and FabricBot should understand it immediately.

Example:

"I have two bedrooms and one living room.

The master bedroom has one balcony window and one normal window.

The balcony window needs main + sheer.

The normal window needs only main curtains.

Use NuHome Luna for all the main curtains.

Use Oreo Sheer for all the sheers.

Premium track everywhere.

Height is 8 feet.

The balcony is 10 feet wide.

The normal window is 6 feet."

FabricBot should convert this into structured quotation data and immediately calculate a complete quotation.

The customer should not need to answer twenty follow-up questions.

---

# 3. Product Philosophy

FabricBot intentionally separates understanding from calculation.

LLMs are extremely good at:

• understanding language
• interpreting incomplete sentences
• correcting spelling mistakes
• identifying products
• extracting dimensions
• recognising business terminology

LLMs are not reliable calculators.

Therefore the project follows one strict rule.

AI extracts.

Python calculates.

Every quotation must be reproducible without AI.

If the AI returns the same structured JSON twice,
the quotation engine must always produce the exact same quotation.

This guarantees deterministic behaviour.

---

# 4. Evolution of the Project

FabricBot has gone through multiple architectural stages.

Understanding these stages is important because many design decisions exist due to lessons learned during development.

---

## Stage 1

Simple price lookup.

Customer sends

"What is the price of Luna?"

↓

Gemini extracts

intent = price_lookup

↓

Python searches Google Sheets

↓

WhatsApp returns price.

This stage worked reliably.

---

## Stage 2

Single window quotation.

Customer sends

"Quotation Luna 84 x 96"

↓

Gemini extracts

height

width

fabric

↓

Quotation engine calculates.

This also worked reliably.

---

## Stage 3

Conversational quotation.

Originally FabricBot attempted to become conversational.

Example

Customer:

"I want curtains."

↓

Bot:

"What fabric?"

↓

Customer:

"Luna."

↓

Bot:

"What size?"

↓

Customer:

"84 x 96"

↓

Bot calculates.

This architecture was abandoned.

---

## Why conversational mode was abandoned

The conversational architecture introduced many problems.

Examples included

• Gemini confusing quotation context with price lookup.

• Previous conversations leaking into new conversations.

• State management becoming increasingly complex.

• Slot filling becoming unreliable.

• Difficult handling of edits.

• Significant increase in code complexity.

The amount of engineering required to maintain conversational state outweighed its benefits.

---

## Current direction

FabricBot now prioritises rich-message understanding.

The preferred interaction is

Customer writes one detailed message.

↓

AI extracts everything.

↓

Python calculates immediately.

↓

Reply returned.

This architecture is significantly simpler, easier to maintain, and scales much better.

Conversation may still exist in the future, but it is no longer the primary design goal.

---

# 5. High-Level System Architecture

Customer

↓

WhatsApp Cloud API

↓

Webhook

↓

Flask Server

↓

AI Extraction

↓

Structured JSON

↓

Quotation Engine

↓

Formatted Reply

↓

WhatsApp Response

Notice that AI is only one stage of the pipeline.

Everything after AI is deterministic Python code.

---

# 6. Core Design Principles

FabricBot follows several important engineering principles.

---

## Principle 1

Business logic must never exist inside prompts.

Prompt:

Understand customer.

Python:

Calculate quotation.

---

## Principle 2

No mathematical reasoning inside AI.

Incorrect

AI calculates GST.

Correct

AI extracts price.

Python calculates GST.

---

## Principle 3

Business rules belong inside Python.

Examples

Track pricing

Fabric calculation

Panel calculation

GST

Fitting

Discounts

Stitching

These should never be embedded inside prompts.

---

## Principle 4

Default values should reduce unnecessary conversation.

Examples

Default Main Fabric Price

₹590

Default Sheer Price

₹490

Default Track

MTrack Premium

Default Curtain Style

Pleated

These defaults allow FabricBot to produce quotations without repeatedly asking the customer unnecessary questions.

---

## Principle 5

AI should make safe assumptions only.

Safe assumption

Customer omitted curtain style.

↓

Use Pleated.

Unsafe assumption

Customer omitted dimensions.

↓

Never invent dimensions.

---

# 7. Folder Structure

FabricBot/

ai.py

database.py

images.py

quotation.py

search.py

server.py

vision.py

whatsapp.py

config.json

requirements.txt

README.md

ARCHITECTURE.md

Each file has a single responsibility.

Responsibilities should not overlap.

---

# 8. Module Responsibilities

## server.py

Entry point of the application.

Responsibilities

• Receive WhatsApp webhook

• Determine message type

• Call AI

• Call quotation engine

• Format response

• Send WhatsApp reply

server.py should remain orchestration code only.

Business calculations should never live here.

---

## ai.py

Responsible for language understanding.

Responsibilities

• Prompt engineering

• Gemini API

• Structured JSON

• Intent extraction

• Parsing multiline quotation requests

ai.py should never calculate quotations.

---

## quotation.py

Most important file in the project.

Contains every quotation formula.

Responsible for

• Fabric calculation

• Track calculation

• Stitching

• Fitting

• GST

• Discounts

• Line items

• Grand totals

Every calculation should be reproducible without AI.

---

## search.py

Searches catalogue data.

Responsible for

• Fabric lookup

• Width lookup

• Price lookup

Should never contain quotation logic.

---

## vision.py

Image understanding.

Responsible for

• OCR

• Catalogue recognition

• Product code extraction

Returns structured data only.

---

## images.py

Responsible for downloading images from WhatsApp.

No AI logic belongs here.

---

## whatsapp.py

Responsible only for communication with WhatsApp Cloud API.

No quotation logic.

No AI.

Only messaging.

---

## database.py

Stores persistent information.

Future responsibilities include

Conversation history

Customers

Saved quotations

CRM integration

Lead management

---

# 9. Request Flow

A typical quotation request follows this pipeline.

Customer

↓

WhatsApp

↓

Webhook

↓

server.py

↓

ai.py

↓

Structured quotation object

↓

quotation.py

↓

Reply formatter

↓

WhatsApp API

↓

Customer

Every stage has exactly one responsibility.

If a bug occurs, debugging should identify which stage failed rather than modifying unrelated modules.
# 10. Quotation Architecture

The quotation engine is the core of FabricBot.

Everything else exists only to collect the information required by the quotation engine.

Unlike a traditional chatbot, FabricBot is fundamentally a quotation generation system.

The quotation engine is completely deterministic.

Given the same inputs, it will always produce the exact same quotation.

No AI reasoning should ever affect quotation mathematics.

---

# 11. Quotation Philosophy

FabricBot intentionally models quotations the same way the business currently works.

The existing quotation spreadsheet is considered the source of truth.

Instead of inventing a completely new architecture, FabricBot mirrors the spreadsheet's design.

This decision dramatically simplifies future maintenance because the business already understands the spreadsheet model.

---

# 12. Spreadsheet Model

The quotation spreadsheet is row-based.

Each row represents ONE TRACK.

NOT one room.

NOT one window.

NOT one quotation.

One physical track.

Examples

Living Room

Window A

Main Curtain

↓

Track 1

Living Room

Window A

Sheer Curtain

↓

Track 2

Living Room

Window B

Main Curtain

↓

Track 3

Bedroom

Window

Main Curtain

↓

Track 4

Every one of these rows is calculated independently.

The spreadsheet later sums every row into the grand total.

FabricBot intentionally follows the exact same architecture.

---

# 13. Line Item Architecture

Inside FabricBot, every spreadsheet row becomes one Line Item.

Example

Customer message

"I have one living room.

It has two windows.

First window needs Main + Sheer.

Second window needs only Main."

AI extracts

Room

↓

Windows

↓

Tracks

↓

Line Items

Result

LineItem 1

Living Room

Window 1

Main

LineItem 2

Living Room

Window 1

Sheer

LineItem 3

Living Room

Window 2

Main

Notice

Each Line Item is completely independent.

Each Line Item can be calculated independently.

This greatly simplifies quotation logic.

---

# 14. Why Tracks are Line Items

The business sells tracks.

Tracks determine

• Fabric quantity

• Track length

• Stitching

• Installation

• Hardware

Therefore every track naturally becomes one quotation row.

This architecture also supports

Main Curtain

Sheer Curtain

Motorised Track

Roman Blind

Roller Blind

Ripple Curtain

without changing the quotation engine.

Every future product simply becomes another line item.

---

# 15. Data Flow

Customer

↓

Gemini

↓

Structured JSON

↓

List[LineItem]

↓

Quotation Engine

↓

List[CalculatedLineItem]

↓

Formatter

↓

WhatsApp Reply

The quotation engine never receives natural language.

It only receives structured objects.

---

# 16. Rich Message Parsing

FabricBot no longer relies on conversations.

Instead the customer is encouraged to provide everything inside one message.

Example

"I have

Master Bedroom

2 windows

Window 1

Main + Sheer

8 x 10

Window 2

Main

8 x 6

Living Room

Balcony

Main + Sheer

8 x 12"

Gemini's responsibility is to convert this story into structured quotation data.

The quotation engine does not know the customer wrote paragraphs.

It only knows it received Line Items.

---

# 17. AI Responsibilities

Gemini performs

Natural language understanding

Extraction

Normalisation

Unit conversion

Grouping

Structure generation

Gemini does NOT

Calculate GST

Calculate fabric

Calculate panels

Calculate stitching

Calculate fitting

Calculate totals

Any mathematical reasoning performed by Gemini should be considered a bug.

---

# 18. Structured Objects

FabricBot should gradually move toward strongly typed objects.

Example

Quotation

contains

Multiple Rooms

Room

contains

Multiple Windows

Window

contains

Multiple Tracks

Track

contains

QuotationInput

QuotationInput

↓

calculate_quote()

↓

QuotationResult

This hierarchy mirrors how customers naturally think.

Customers think in

Rooms

↓

Windows

↓

Curtains

NOT

Rows.

Rows only exist internally.

---

# 19. Internal vs External Representation

Customer View

House

↓

Rooms

↓

Windows

↓

Curtains

Internal View

Line Item

↓

Calculation

↓

Line Item

↓

Calculation

↓

Grand Total

This separation is intentional.

Customers should never need to think about quotation rows.

---

# 20. Default Values

FabricBot attempts to reduce unnecessary conversation by supplying safe defaults.

Current defaults

Main Fabric

₹590/m

Sheer Fabric

₹490/m

Track

MTrack Premium

Curtain Style

Pleated

Order Type

Full

These defaults should only be applied when the customer has not explicitly specified a value.

Dimensions should NEVER be assumed.

Dimensions are required inputs.

---

# 21. Catalogue Resolution

Whenever possible, catalogue information should override defaults.

Priority

Customer specifies catalogue

↓

Search catalogue

↓

Price found

↓

Use catalogue price

Otherwise

↓

Use default price

If the catalogue cannot be found, quotation generation should continue using default pricing rather than failing completely.

This prevents unnecessary customer interaction.

---

# 22. Future Line Item Expansion

The quotation engine should never assume every line item represents curtains.

Future line item types may include

Curtains

Roller Blinds

Roman Blinds

Motorised Curtains

Wallpaper

PVC Blinds

Wooden Blinds

Venetian Blinds

Tracks only

Accessories

Each line item should carry its own product type.

The quotation engine should dispatch calculations based on product type.

---

# 23. Reply Formatting Philosophy

FabricBot replies should be easy to read on WhatsApp.

The reply should be divided into sections.

Recommended hierarchy

Quotation Header

↓

Room

↓

Window

↓

Track

↓

Cost Breakdown

↓

Grand Total

The customer should never receive one giant paragraph.

Future versions should support expandable PDFs while keeping WhatsApp replies concise.

---

# 24. Separation of Responsibilities

Gemini

↓

Understand

Search Engine

↓

Resolve catalogue

Quotation Engine

↓

Calculate

Formatter

↓

Present

WhatsApp

↓

Deliver

Each module has exactly one responsibility.

This separation makes debugging significantly easier.

---

# 25. Why This Architecture Scales

The current architecture is intentionally designed so that increasing quotation complexity does not increase calculator complexity.

Adding

10 rooms

↓

100 windows

↓

250 tracks

does not require any new quotation mathematics.

The quotation engine simply calculates

250 independent Line Items

↓

Combines totals

↓

Returns grand total.

This architecture scales naturally from a single bedroom quotation to an entire villa without requiring major changes.
# 26. AI Pipeline

FabricBot uses AI as a language understanding engine rather than a decision-making engine.

The AI layer is responsible only for converting human language into structured data.

Current pipeline:

Customer Message

↓

Gemini

↓

Structured Pydantic Objects

↓

Python Business Logic

↓

Quotation Engine

↓

Formatted WhatsApp Reply

The AI layer should remain stateless whenever possible.

Persistent business logic belongs inside Python.

---

# 27. OCR Pipeline

FabricBot supports quotations from images.

Example:

Customer uploads a catalogue image.

↓

WhatsApp Webhook

↓

images.py downloads image

↓

vision.py sends image to Gemini Vision

↓

Gemini extracts catalogue code

↓

search.py searches catalogue

↓

Quotation proceeds normally

The OCR system should return structured data only.

It should never calculate prices or quotations.

---

# 28. Search Pipeline

search.py is responsible for resolving business data.

Inputs may include

• Catalogue name

• Fabric name

• Supplier name

Outputs include

• Price

• Width

• Collection

• Supplier

The search module should never perform quotation calculations.

Future improvements may include

• Fuzzy search

• Synonym matching

• OCR typo correction

• Embedding search

• Supplier ranking

without affecting the quotation engine.

---

# 29. Business Logic

Business rules must remain inside Python.

Examples

Correct

if track_type == "MTrack Premium":
    ...

Incorrect

Prompt:

"If customer says premium track, charge ₹180."

Business knowledge belongs inside configuration or Python.

Prompt engineering should never replace business logic.

---

# 30. Configuration

Business constants should eventually live inside configuration files.

Examples

config.json

Default Prices

GST

Track Rates

Fullness

Pleated allowances

Roman Blind constants

Motorised Track constants

Future goal:

Changing business rules should require editing configuration rather than Python code.

---

# 31. Database Philosophy

The database exists to store state.

Not business logic.

Future responsibilities

Customer history

Saved quotations

CRM IDs

Lead status

Follow-ups

Previous projects

The database should never contain quotation mathematics.

---

# 32. Deployment Architecture

Development Environment

MacBook

↓

VS Code

↓

Git

↓

GitHub

↓

VPS

↓

Gunicorn

↓

Flask

↓

WhatsApp Cloud API

The VPS should always run a stable branch.

Experimental development should occur in separate Git branches.

---

# 33. Git Workflow

FabricBot follows a branch-based workflow.

main

↓

Stable production

rich-quotation

↓

Experimental quotation improvements

Future features should each receive their own branch.

Examples

feature/pdf-export

feature/zoho-crm

feature/wallpaper

feature/appointment-booking

Never develop major features directly on main.

---

# 34. Development Philosophy

Every new feature should answer three questions.

1.

Does this belong inside AI?

2.

Does this belong inside business logic?

3.

Does this belong inside presentation?

Mixing these responsibilities should be avoided.

---

# 35. Error Handling Philosophy

Failures should degrade gracefully.

Examples

Catalogue not found

↓

Use default price.

OCR failed

↓

Ask customer to type catalogue.

Image unreadable

↓

Request clearer image.

Webhook timeout

↓

Retry safely.

FabricBot should avoid crashing wherever possible.

---

# 36. Logging Philosophy

Every important stage should be logged.

Recommended stages

Webhook received

↓

Message type

↓

AI request

↓

AI response

↓

Search result

↓

Quotation object

↓

Reply generated

↓

WhatsApp sent

Logs should describe

What happened

rather than

How the code works.

---

# 37. Coding Standards

Prefer

Small functions.

Readable code.

Explicit variable names.

Typed objects.

Deterministic calculations.

Avoid

Magic numbers.

Huge functions.

Nested conditionals.

Duplicate logic.

Hidden business rules.

Premature optimisation.

---

# 38. Things Future AI Must NEVER Do

This section is intentionally strict.

Future AI assistants should NEVER

❌ Rewrite quotation mathematics unless explicitly requested.

❌ Replace deterministic Python calculations with AI reasoning.

❌ Move business logic into prompts.

❌ Remove OCR functionality.

❌ Remove price lookup.

❌ Hardcode prices inside prompts.

❌ Make FabricBot conversational again unless explicitly requested.

❌ Break backwards compatibility.

❌ Rewrite working code for stylistic reasons.

❌ Introduce unnecessary abstractions.

Future AI should prefer minimal, safe, incremental improvements.

---

# 39. Current Limitations

The current system intentionally accepts several limitations.

It assumes

• Rich messages contain sufficient information.

• Dimensions are required.

• One quotation request is processed at a time.

The following are not yet implemented

• PDF quotations

• CRM integration

• Appointment booking

• Customer quotation history

• Wallpaper calculator

• Roller blind calculator

• Multi-product quotations

• Inventory integration

These are planned future features rather than architectural flaws.

---

# 40. Future Architecture

The long-term architecture is expected to evolve as follows.

Natural Language

↓

AI Extraction

↓

Structured Project

↓

Room Objects

↓

Window Objects

↓

Track Objects

↓

Product-Specific Calculators

↓

Line Item Results

↓

Grand Total

↓

PDF

↓

WhatsApp

This allows FabricBot to support hundreds of quotation line items without changing the overall architecture.

---

# 41. Long-Term Product Vision

FabricBot is intended to become an AI employee for a furnishing business.

The vision extends far beyond quotations.

Potential future capabilities include

• Customer quotations

• OCR catalogue lookup

• Wallpaper quotations

• Blind quotations

• Motorised curtain quotations

• CRM integration

• Lead management

• Appointment scheduling

• Installation planning

• Quotation PDFs

• Supplier database

• Inventory lookup

• Customer history

• Analytics dashboard

The architecture should always favour modularity so these features can be added without major rewrites.

---

# 42. Final Design Philosophy

FabricBot follows one simple principle.

Understand naturally.

Calculate deterministically.

Present beautifully.

Every future architectural decision should reinforce these three goals.

If a proposed feature violates this philosophy, reconsider the design before implementing it.