<?php
// Step 1 of double opt-in: take an address, send it a confirmation link.
// Nothing is ever mailed to an address that has not clicked that link.

require __DIR__ . '/lib.php';
$c = cfg();

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: ' . $c['site_url']);
    exit;
}

$email = strtolower(trim($_POST['email'] ?? ''));
$list  = preg_replace('/[^a-z0-9\-]/', '', strtolower($_POST['list'] ?? 'default')) ?: 'default';
$trap  = trim($_POST['company'] ?? '');   // honeypot: humans never see this field
$ip    = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';

// Bots fill every field. Answer normally so they learn nothing.
$looks_like_a_bot = $trap !== '';

if (!$looks_like_a_bot && !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    echo page('Check that address', 'That address does not look right',
        '<p>Please go back and re-enter your email address.</p>');
    exit;
}

if (!$looks_like_a_bot && rate_limited($ip)) {
    echo page('Try again shortly', 'Too many attempts',
        '<p>Please wait a few minutes and try again.</p>');
    exit;
}

// The response below is identical whether the address is new, already
// subscribed, or previously unsubscribed. That is deliberate: it stops the
// form being used to test whether an address is on the list.
$generic = page(
    'Check your inbox',
    'One more step',
    '<p>If that address can be subscribed, a confirmation email is on its way.
      Click the link inside it and the next digest will be your first.</p>
     <p>Nothing is sent until you confirm. If the email does not arrive within
      a few minutes, check your spam folder.</p>'
);

if ($looks_like_a_bot) {
    echo $generic;
    exit;
}

try {
    $pdo = db();

    $sup = $pdo->prepare("SELECT 1 FROM suppression WHERE email = ?");
    $sup->execute([$email]);
    if ($sup->fetchColumn()) {
        echo $generic;   // previously unsubscribed: stay gone, silently
        exit;
    }

    $row = $pdo->prepare("SELECT status, token FROM subscribers WHERE email = ? AND list = ?");
    $row->execute([$email, $list]);
    $existing = $row->fetch(PDO::FETCH_ASSOC);

    if ($existing && $existing['status'] === 'confirmed') {
        echo $generic;   // already on the list: do not re-mail
        exit;
    }

    $token = $existing['token'] ?? make_token();
    if (!$existing) {
        $ins = $pdo->prepare("INSERT INTO subscribers (email, list, status, token, created)
                              VALUES (?,?,'pending',?,?)");
        $ins->execute([$email, $list, $token, gmdate('c')]);
    }

    $confirm = $c['base_url'] . '/confirm.php?token=' . urlencode($token);
    $body = "Confirm your BidBeacon subscription.\n\n"
          . "Click to confirm:\n$confirm\n\n"
          . "You will then get a daily digest of new federal contract "
          . "opportunities matching your trade.\n\n"
          . "If you did not request this, ignore this email. Nothing will be "
          . "sent to you.\n\n"
          . ($c['postal'] ? "\n" . $c['postal'] . "\n" : "");
    send_mail($email, 'Confirm your BidBeacon subscription', $body);

    echo $generic;
} catch (Throwable $e) {
    error_log('bidbeacon signup: ' . $e->getMessage());
    echo page('Something went wrong', 'We could not save that just now',
        '<p>Please try again in a few minutes.</p>');
}
