Claim a work stream from the roadmap for implementation. This command:

1. Reads `plans/roadmap.md` to find available work streams
2. Checks for blocking dependencies
3. Uses NATS chat to announce the claim in `#coordination`
4. Updates the roadmap to mark the work stream as "In Progress"
5. Commits the claim

If no specific work stream is provided, identify the highest priority unclaimed item.

$ARGUMENTS
