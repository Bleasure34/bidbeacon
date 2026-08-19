<?php
// Step 2 of double opt-in: the click that creates consent.

require __DIR__ . '/lib.php';

$token = $_GET['token'] ?? '';
if ($token === '') {
    echo page('Link not valid', 'That link is not valid',
        '<p>Please sign up again to get a fresh confirmation link.</p>');
    exit;
}

try {
    $pdo = db();
    $sel = $pdo->prepare("SELECT email, status FROM subscribers WHERE token = ?");
    $sel->execute([$token]);
    $row = $sel->fetch(PDO::FETCH_ASSOC);

    if (!$row) {
        echo page('Link not valid', 'That link is not valid',
            '<p>It may have already been used. Please sign up again if you are
              not receiving the digest.</p>');
        exit;
    }

    if ($row['status'] === 'confirmed') {
        echo page('Already confirmed', 'You are already subscribed',
            '<p>Nothing more to do. The next digest will arrive in the morning.</p>');
        exit;
    }

    $upd = $pdo->prepare("UPDATE subscribers SET status='confirmed', confirmed_at=?
                          WHERE token = ? AND status='pending'");
    $upd->execute([gmdate('c'), $token]);

    echo page('Subscribed', 'You are subscribed',
        '<p>The next digest will be your first. Every issue has an unsubscribe
          link at the bottom, and it works immediately.</p>');
} catch (Throwable $e) {
    error_log('bidbeacon confirm: ' . $e->getMessage());
    echo page('Something went wrong', 'We could not confirm that just now',
        '<p>Please try the link again in a few minutes.</p>');
}
