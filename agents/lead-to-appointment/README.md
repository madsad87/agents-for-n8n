# Lead-to-Appointment Agent

This agent turns inbound leads into scheduled meetings by orchestrating qualification, enrichment, and calendar booking workflows. It is designed to be imported into n8n without bundled credentials.

## Workflows
- **01 Intake and Qualification** (`workflows/01-intake-and-qualification`): Ingests lead payloads, enriches contact data, and determines whether the lead meets booking criteria.
- **02 Appointment Scheduling** (`workflows/02-appointment-scheduling`): Creates calendar invites for qualified leads and sends confirmations to stakeholders.

## How to Use
1. Copy `env.example` to `.env` and populate endpoint URLs, API keys, and webhook secrets.
2. Place the exported n8n workflow JSON files into their respective workflow folders.
3. Run `scripts/sanitize_n8n_export.py <export.json> -o <sanitized.json>` before committing to ensure credentials are stripped.
4. Import the sanitized workflows into your n8n instance and bind credentials through the UI.

## Diagram
See `diagram.mmd` for the Mermaid diagram placeholder. Update it as the workflows evolve.
