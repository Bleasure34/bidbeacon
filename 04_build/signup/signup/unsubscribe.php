<?php
// One click, immediate, permanent. No confirmation step, no "are you sure",
// no login. The address also goes on a suppression list so a later signup
// cannot quietly resurrect it.

require __DIR__ . '/lib.php';

$token = $_GET['token'] ?? '';
if ($token === '') {
    echo page('Link not valid', 'That link is not valid',
        '<p>If you are still receiving mail you did not ask for, reply to any
          issue and it will be handled.</p>');
    exit;
}

try {
    $pdo = db();
    $sel = $pdo->prepare("SELECT email FROM subscribers WHERE token = ?");
    $sel->execute([$token]);
    $email = $sel->fetchColumn();

    if (!$email) {
        // Already gone, or a stale link. Say the reassuring true thing.
        echo page('Unsubscribed', 'You are unsubscribed',
            '<p>That address will not receive further emails.</p>');
        exit;
    }

    $pdo->prepare("UPDATE subscribers SET status='unsubscribed', unsubscribed_at=?
                   WHERE token = ?")->execute([gmdate('c'), $token]);
    $pdo->prepare("INSERT OR IGNORE INTO suppression (email, reason, at)
                   VALUES (?,?,?)")->execute([$email, 'unsubscribe', gmdate('c')]);

    echo page('Unsubscribed', 'You are unsubscribed',
        '<p>Done, effective immediately. No further emails will be sent to
          that address.</p>');
} catch (Throwable $e) {
    error_log('bidbeacon unsubscribe: ' . $e->getMessage());
    // Never leave someone stuck on a list because of a server error.
    echo page('Unsubscribed', 'You are unsubscribed',
        '<p>Your request was received. If anything further arrives, reply to
          it and it will be stopped manually.</p>');
}
