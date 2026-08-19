# Signup handler (upload to Hostinger)

Five PHP files that turn an email address into a confirmed subscriber. Runs on
your existing Business hosting, so it costs nothing and adds no accounts.

## Upload

Put this whole `signup` folder inside `public_html`, renamed `bidbeacon`, so
the files end up at:

```
public_html/bidbeacon/join.php
public_html/bidbeacon/confirm.php
public_html/bidbeacon/unsubscribe.php
public_html/bidbeacon/export.php
public_html/bidbeacon/lib.php
public_html/bidbeacon/config.php
public_html/bidbeacon/data/.htaccess
```

Use hPanel's File Manager, drag the folder in. The `data` folder will create
itself on first use; the `.htaccess` inside it stops the subscriber database
from ever being served over the web.

## Then edit two files

**`config.php`** — set `from_email` to a real mailbox on your domain (create
it in hPanel → Emails first, otherwise mail lands in spam), set `postal` to
the address you want in email footers, and check `base_url` matches where you
actually uploaded this.

**`export.php`** — replace `CHANGE-ME-to-a-long-random-string` with a long
random string. Store the same string as a GitHub Actions secret called
`EXPORT_KEY`. This is what lets the daily job read the confirmed list; without
it, the endpoint refuses every request.

## Check it works

1. Visit `https://leasuredigital.com/bidbeacon/join.php` directly. It should
   redirect you to the site, not show an error. That means PHP is running.
2. Sign yourself up through the form on the site. You should get a
   confirmation email within a minute or two.
3. Click the link. You should see "You are subscribed".
4. Check `https://leasuredigital.com/bidbeacon/export.php?key=YOUR_KEY` shows
   your address. Then check it without the key and confirm you get
   `forbidden`.

## How consent works here

Nothing is ever emailed to an address that has not clicked the confirmation
link. Unsubscribe is one click, immediate, and permanent: the address goes on
a suppression list, so even a later signup with the same address will not
resurrect it. The signup form gives the same response whether an address is
new, already subscribed, or previously unsubscribed, so it cannot be used to
test who is on the list.
