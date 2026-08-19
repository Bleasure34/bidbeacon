# BidBeacon signup handler

Double opt-in email signup, running on ordinary PHP shared hosting. Deployed
to `public_html/bidbeacon/` on Hostinger.

## First-time setup, once

1. **Create the sending mailbox.** hPanel → Emails → create `bids@yourdomain`.
   Confirmation mail sent from an address that does not exist gets treated as
   spam.

2. **Create `config.local.php` on the server.** Copy
   `config.local.example.php` to `config.local.php` in this same folder and
   fill it in. This file holds the real settings and the export key. It is not
   in git and deploys never overwrite it, which is exactly why secrets live
   there and not in `config.php`.

3. **Generate an export key** and put it in `config.local.php`:

```bash
openssl rand -hex 32
```

   Store the same value as a GitHub Actions secret named `EXPORT_KEY`.

## Verify it works

1. Visit `/bidbeacon/join.php` directly — it should redirect to the site, not
   error. That proves PHP is running.
2. Sign up through the form with a real address. Confirmation mail should
   arrive within a minute.
3. Click the link. You should see "You are subscribed".
4. `/bidbeacon/export.php?key=YOUR_KEY` should list your address.
   `/bidbeacon/export.php` with no key must return `forbidden`. Check both.

## How consent works

Nothing is ever emailed to an address that has not clicked its confirmation
link. Unsubscribe is one click, immediate and permanent: the address is added
to a suppression list, so even a later signup cannot resurrect it. The signup
form returns an identical response whether an address is new, already
subscribed, or previously unsubscribed, so it cannot be used to test who is on
the list. A honeypot field and a per-IP hourly limit slow down bots.

The subscriber database sits in `data/`, which carries an `.htaccess` denying
all web access.

## Files

| File | Does |
|---|---|
| `join.php` | Accepts the form, stores a pending record, sends the confirm link |
| `confirm.php` | Validates the token, marks the address confirmed |
| `unsubscribe.php` | One-click removal plus permanent suppression |
| `export.php` | Serves the confirmed list to the daily job, secret-gated |
| `lib.php` | Storage, tokens, mail, shared page shell |
| `config.php` | Defaults only, no secrets, overwritten by deploys |
| `config.local.php` | Your real settings. Not in git. Create by hand. |
