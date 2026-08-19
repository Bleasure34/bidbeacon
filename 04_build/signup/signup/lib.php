<?php
// Shared helpers: storage, tokens, mail, and page chrome.

function cfg(): array
{
    static $c = null;
    if ($c === null) {
        $c = require __DIR__ . '/config.php';
        // Local overrides hold the real settings and the export key. Absent
        // from git, untouched by deploys, so nothing secret is ever published.
        $local = __DIR__ . '/config.local.php';
        if (is_readable($local)) {
            $over = require $local;
            if (is_array($over)) {
                $c = array_merge($c, $over);
            }
        }
    }
    return $c;
}

function db(): PDO
{
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }
    $dir = __DIR__ . '/data';
    if (!is_dir($dir)) {
        mkdir($dir, 0700, true);
    }
    $pdo = new PDO('sqlite:' . $dir . '/subscribers.sqlite');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->exec("CREATE TABLE IF NOT EXISTS subscribers (
        email TEXT NOT NULL,
        list TEXT NOT NULL DEFAULT 'default',
        status TEXT NOT NULL DEFAULT 'pending',
        token TEXT NOT NULL UNIQUE,
        created TEXT NOT NULL,
        confirmed_at TEXT,
        unsubscribed_at TEXT,
        PRIMARY KEY (email, list)
    )");
    $pdo->exec("CREATE TABLE IF NOT EXISTS suppression (
        email TEXT PRIMARY KEY, reason TEXT, at TEXT
    )");
    $pdo->exec("CREATE TABLE IF NOT EXISTS attempts (
        ip TEXT NOT NULL, at INTEGER NOT NULL
    )");
    return $pdo;
}

function rate_limited(string $ip): bool
{
    $pdo = db();
    $cutoff = time() - 3600;
    $pdo->prepare("DELETE FROM attempts WHERE at < ?")->execute([$cutoff]);
    $n = $pdo->prepare("SELECT COUNT(*) FROM attempts WHERE ip = ? AND at >= ?");
    $n->execute([$ip, $cutoff]);
    if ((int)$n->fetchColumn() >= cfg()['rate_limit']) {
        return true;
    }
    $pdo->prepare("INSERT INTO attempts VALUES (?,?)")->execute([$ip, time()]);
    return false;
}

function make_token(): string
{
    return rtrim(strtr(base64_encode(random_bytes(24)), '+/', '-_'), '=');
}

function send_mail(string $to, string $subject, string $body): bool
{
    $c = cfg();
    $headers = [
        'From: ' . $c['from_name'] . ' <' . $c['from_email'] . '>',
        'Reply-To: ' . $c['support_email'],
        'Content-Type: text/plain; charset=UTF-8',
        'MIME-Version: 1.0',
        'Auto-Submitted: auto-generated',
    ];
    return @mail($to, $subject, $body, implode("\r\n", $headers));
}

// Minimal shared page shell so every response looks like the product.
function page(string $title, string $heading, string $body_html): string
{
    $c = cfg();
    $t = htmlspecialchars($title, ENT_QUOTES, 'UTF-8');
    $h = htmlspecialchars($heading, ENT_QUOTES, 'UTF-8');
    $site = htmlspecialchars($c['site_url'], ENT_QUOTES, 'UTF-8');
    return <<<HTML
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>$t</title><style>
body{font-family:Segoe UI,Arial,sans-serif;background:#fafbfd;color:#16213a;
margin:0;line-height:1.55}
.wrap{max-width:560px;margin:0 auto;padding:60px 20px}
h1{font-size:23px;margin:0 0 12px}
p{color:#5b6474}
a{color:#1f5eff}
.card{background:#fff;border:1px solid #e2e6ee;border-radius:12px;padding:24px 26px}
</style></head><body><div class="wrap"><div class="card">
<h1>$h</h1>
$body_html
<p style="margin-top:20px"><a href="$site">Back to BidBeacon</a></p>
</div></div></body></html>
HTML;
}
