Deploy the smart home system to colby (the home server). This command:

1. Verifies SSH control socket is active (ask user to establish if not)
2. Runs tests locally to ensure everything passes
3. Syncs code to colby via rsync/scp
4. Restarts the appropriate services on colby
5. Verifies services are running correctly

If a specific component is provided (e.g., "security-monitor"), only deploy that component.

**Requires:** SSH control socket at `/tmp/colby-ssh` (user must establish with 2FA)

$ARGUMENTS
