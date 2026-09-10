# Chat history, subject marks and backend observability

## Dashboard scoring

The dashboard now includes all available dataset subject labels, including hackathon skills. Recorded scores are displayed as `obtained / maximum * 100`. This is a normalization to 100, not a claim that each examination had 100 full marks. Existing full marks are preserved; the existing demo assumption of 2 marks per question applies where the importer lacked full marks.

Hackathon marks are aggregated once per source question and skill, excluding pending review, invalid and unscored questions. Multiple topic tags cannot inflate a subject score. Hackathon scores take precedence over course MCQ scores for an identical subject label. No speculative mapping from “Coding” to a named course is made. Missing scores remain null, not zero.

Progress is the mean of available course progress values for that subject. It remains an engagement proxy. Ambiguous duplicate course snapshots are excluded from the subject aggregate. The line chart compares subjects alphabetically, not time. Missing values are gaps; hover/focus points and the expandable table expose exact values and score sources.

## Saved conversations

`chat_conversations` in PostgreSQL stores each conversation's title, selected student ID, messages and last-updated time. The table is created on first use (or by the existing importer schema setup). `GET /api/conversations` lists the most recent 50 conversations for the active student. `POST /api/conversations/{id}/open` restores one after verifying ownership. Starting a new conversation clears only the active session; it preserves saved chats. Successful turns update the same conversation.

The last 200 messages per conversation are retained; the last 20 are used for model context. Saved chats survive sign-out and server restarts. Sessions themselves remain in-memory, so the student must be reselected after a restart. This is still a demo picker, not production authentication. Chats from before this feature were not retroactively reconstructed from diagnostic logs.

## Operational metrics

- `backend/logs/metrics.jsonl`: rotating structured JSON logs (5 MB each, three backups).
- Each response includes a generated `X-Request-ID`, also attached to related chat, tool and provider events.
- `GET /api/metrics` requires an active demo session. It returns process uptime, event counts/errors, mean/max latency, noncumulative latency histogram buckets, cache hits, and input/output token totals reported by the provider.
- HTTP events use route templates, status and method. Model events capture completion duration and errors. Provider HTTP events capture each attempt/status, including rate-limit retries. Tool events track latency and cache hits; chat events record outcome and tool count.
- Metrics logs omit prompts, answers, cookies, API keys and student identities. The pre-existing `turns.jsonl` diagnostic trace still contains conversation content/tool evidence and should be treated as private development data.
- Metrics reset on process restart, and each worker has its own counters. This demo does not estimate monetary cost or expose a production monitoring service. Missing provider token usage is not estimated.

## Verification

66 backend tests passed, including persisted history across sessions, cross-student access denial, greeting behavior, subject normalization, duplicate topic tags, pending marks, missing marks, and request metrics. Production frontend build passed. Desktop/mobile browser checks cover the tooltip, chat layout/history and chart.
