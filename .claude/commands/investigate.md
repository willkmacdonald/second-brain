Ask a question about the deployed Second Brain system's telemetry.
Uses the local `second-brain-telemetry` MCP tools to query App Insights
directly -- no network hop to the deployed API.

## How to execute

Use the `second-brain-telemetry` MCP tools to answer `$ARGUMENTS`.

Route the question to the appropriate tool:
- Errors/failures --> `recent_errors`
- Trace a capture --> `trace_lifecycle`
- System health --> `system_health`
- Usage/distribution --> `usage_patterns`
- Admin agent activity --> `admin_audit`
- Custom KQL --> `run_kql`

Present results naturally -- format JSON into readable tables, summaries,
or bullet points.

## Error handling

- `{"error": true, "type": "ClientAuthenticationError"}` --> suggest `! az login`
- `{"error": true, "type": "config_error"}` --> workspace ID not set in MCP server config
- Other errors --> show message, suggest retrying or simplifying

## Important

- Pass the user's question through as-is for intent detection
- MCP tools are stateless -- use conversation context for follow-ups
- Do NOT shell out to Python scripts -- use MCP tools exclusively
