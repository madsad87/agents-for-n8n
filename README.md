# agents-for-n8n

A structured repository for n8n blueprints. Each agent groups related workflows with documentation, sanitized exports, and diagrams.

## Layout
- `agents/lead-to-appointment/` — turns inbound leads into scheduled appointments.
  - `workflows/` — individual workflow folders that hold README files and exported JSON.
  - `diagram.mmd` — Mermaid diagram placeholder to visualize the flow.
  - `README.md` — agent-level overview and usage notes.
- `templates/` — README templates for agents and workflows to keep docs consistent.
- `scripts/sanitize_n8n_export.py` — utility to strip credentials from n8n exports before committing.
- `env.example` — sample environment variable file to copy into `.env`.

## Sanitizing Exports
Run the sanitize script before sharing or committing workflow exports:

```bash
python scripts/sanitize_n8n_export.py agents/lead-to-appointment/workflows/01-intake-and-qualification/workflow.json \
  -o agents/lead-to-appointment/workflows/01-intake-and-qualification/workflow.sanitized.json
```

## Adding Workflows
1. Duplicate the templates in `templates/` when documenting new agents or workflows.
2. Keep sensitive values out of JSON exports; rely on the sanitize script and n8n credential bindings.
3. Update the Mermaid diagram to reflect new steps and branching.
