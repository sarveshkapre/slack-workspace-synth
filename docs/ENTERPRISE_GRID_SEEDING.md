# Enterprise Grid Seeding (Real Users + Messages)

This project (`swsynth`) generates a synthetic Slack-like workspace in SQLite. Many enterprises want more:

- A real **Slack Enterprise Grid** workspace created for testing.
- **Fake users** (with realistic profiles) provisioned via **Microsoft Entra ID**.
- Messages that are authored by those fake users (not “posted by a bot that looks like them”).
- Optional “bulk history” seeding for channels and DMs so the workspace feels lived-in on day one.

This doc describes what’s possible with Slack APIs, what is *not* possible, and a practical hybrid approach
that enterprises can run with 50–100 synthetic users.

## The key constraint: no admin impersonation

Slack does **not** provide an API that lets an admin mint a token and “post as any user”.

To post a message as user `U`, you must have a **user token** for `U` obtained via that user completing
an OAuth install/authorization flow for your Slack app.

This means:

- You can always post as an **app/bot** with a bot token.
- You can post as a **specific user** only after you collect and store that user’s token.
- There is no supported “skip the per-user OAuth step” shortcut.

## Two seeding modes (support both)

### Mode A: Bulk history import (fastest “lived in” day-0)

Best for: large backfills (10k–1M+ messages), realistic authorship across many users, realistic DM history.

How it works:

1. Generate the org graph + channels + messages with `swsynth` (SQLite).
2. Export a Slack-compatible import bundle (JSON + assets).
3. Use Slack’s import tooling to import the bundle into the new workspace.

Pros
- Authorship appears as the synthetic users.
- DMs and MPIMs can look real from day one.
- Much less “online posting” time (rate limits matter less).

Cons
- Import is operationally more manual (workspace-admin workflow).
- Import format and limitations vary by plan and org configuration.
- Slack does not support importing directly into an Enterprise Grid organization; the typical workaround
  is to import into a separate workspace, then migrate it into the org.

### Mode B: Live posting via per-user OAuth tokens (most API-realistic)

Best for: ongoing simulation and “agents interacting with Slack” where identity and permissions matter.

How it works:

1. Provision users into Slack via Entra SCIM (so they exist as real Slack accounts).
2. Create workspace + channels via Enterprise Grid Admin APIs.
3. Collect a **user token per synthetic user** using ClickOps:
   - open an authorization URL
   - complete SSO/MFA
   - approve app access
4. Use each user token to post messages as that user.

Pros
- Uses Slack Web API end-to-end; looks like real human activity.
- Works for “agent testing” where the author identity is critical.

Cons
- Requires N OAuth approvals for N synthetic users.
- Token storage/refresh lifecycle is operational work.

### Mode C (recommended): Hybrid

- Use **Mode A** to create a realistic “existing history” on day 0.
- Use **Mode B** for a smaller active subset (e.g., 10–30 actors) for live traffic and agent testing.

This yields realism without requiring you to OAuth 100 users on day one (unless you want to).

## Token / credential inventory

### Slack

You typically need:

1. **Enterprise Grid admin token** (org-installed app; admin scopes) to:
   - create workspace(s)
   - create channels in the right workspace(s)
   - assign users into the workspace
2. **SCIM token** to read user identities and verify provisioning.
3. **Bot token** for app-owned actions (optional; only if you also want bot activity).
4. **User tokens** (one per synthetic user) if you want to post as those users (Mode B/C).

### Microsoft Entra ID

You need an Entra app registration with Graph permissions to:

- Create users (synthetic identities).
- Assign them to the Slack enterprise app / group(s) that enable provisioning.

You also need Entra SCIM provisioning configured from Entra → Slack so that the Entra users appear in Slack.

## Avoid redundancy: choose a source of truth for users

If the enterprise uses Entra provisioning:

- Treat **Entra** as the “create/update users” source of truth.
- Use Slack SCIM primarily to **verify** and map Entra identities to Slack `user_id`s.

Avoid having the CLI *also* create/update users directly in Slack SCIM as a second authority.

## Proposed CLI shape (future work)

Keep it explicit and composable:

1. `swsynth plan`:
   - Generates an “org blueprint” (users, teams, channels, memberships, DM graph, message schedule).
   - Deterministic by `--seed`.
2. `swsynth provision entra`:
   - Creates Entra users for the blueprint and assigns them so SCIM provisions them to Slack.
3. `swsynth provision slack`:
   - Creates a new Grid workspace and channels, assigns provisioned users.
4. `swsynth seed-import` (available now):
   - Builds a Slack export-style import bundle from the SQLite DB output.
5. `swsynth oauth-pack` (available now):
   - Generates per-user OAuth URLs + `state_map.json` for clickops token collection.
6. `swsynth oauth-callback` (available now):
   - Runs a local callback server to exchange OAuth codes for user tokens.
7. `swsynth channel-map` (available now):
   - Generates a synthetic channel id -> Slack channel id mapping (by name, or via API).
8. `swsynth seed-live` (available now):
   - Uses collected user tokens to post messages as users, respecting rate limits and idempotency.
   - Can auto-build the channel map from Slack channel export/API if no map is provided.
9. `swsynth provision-slack` (available now):
   - Creates missing channels and optionally invites members using Slack APIs.

## Operational notes

- **Secrets**: never send Slack/Entra tokens to an LLM. Generate the blueprint via the LLM, then apply it
  locally using your tokens.
- **Idempotency**: persist a stable mapping file `{synthetic_user_id -> entra_object_id -> slack_user_id}`
  plus `{synthetic_channel_id -> slack_channel_id}` so reruns do not duplicate entities.
- **Rate limiting**: posting 100k messages live will be slow. Prefer bulk import for large day-0 histories.
