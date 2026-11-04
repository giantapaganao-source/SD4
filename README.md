# SD4

## Database configuration

The app uses the local `studybuddy.db` file when run outside Vercel and no
Turso credentials are set. On Vercel, configure both environment variables:

- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`

The app selects the `libsql` or `turso_serverless` Python driver based on the
database URL, then creates or upgrades its tables when it starts. Set
`SECRET_KEY` in Vercel as well so Flask sessions use a private, persistent
signing key. Keep all tokens and keys out of source control.

Existing data in the local `studybuddy.db` is not automatically copied to
Turso; it remains in that file until explicitly migrated.

## Sharing planner items

On the My Tasks page and Study Schedule page, use **Share** on an item and
enter an existing recipient nickname. The app creates an independent copy
under the recipient's matching subject, creating that subject if necessary.
Unknown nicknames are rejected; edits to the copy do not change the sender's
original item.

Tasks require both a deadline date and time. Existing tasks are migrated with
a default deadline time of 23:59.