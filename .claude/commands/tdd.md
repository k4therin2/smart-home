Start a TDD workflow to implement a work stream from the roadmap. Use the tdd-workflow-engineer agent to:

1. Read the roadmap at `plans/roadmap.md`
2. Identify the work stream to implement (if specified, use that; otherwise pick the next unclaimed stream)
3. Follow the TDD workflow: claim work, write tests first, implement, verify, document
4. Use NATS coordination to announce progress

$ARGUMENTS
