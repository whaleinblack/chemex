# ChemEx delivery workflow

The project owner requires every completed implementation change to be delivered to both GitHub and the live web app.

1. Update the relevant backend and web UI, and run checks appropriate to the change.
2. Commit and push the changes to `https://github.com/whaleinblack/chemex.git` before deployment.
3. Deploy the verified changes to `https://chemex.space/`, rebuilding the frontend when it changes.
4. Verify service health and the affected workflow after deployment, then report the pushed commit and deployment result.

Preserve existing server changes and other applications on the shared host. Keep a recoverable deployment backup. Never commit credentials, private keys, private runtime fonts, or calculation uploads. If authentication or another external dependency blocks a delivery step, clearly report which step remains incomplete.

Read `docs/GUIDELINE.md` and `docs/HANDOFF.md` for project conventions and deployment details.
