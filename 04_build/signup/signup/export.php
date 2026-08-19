<?php
// Lets the daily job fetch the confirmed list so it can send the digest.
// Returns subscriber addresses, so it is gated by a shared secret that lives
// only in config.local.php on the server — never in the repository.

require __DIR__ . '/lib.php';

$key   = (string)(cfg()['export_key'] ?? '');
$given = (string)($_GET['key'] ?? '');

// An unset key means "not configured yet", which must fail closed.
// hash_equals compares in constant time so the key cannot be guessed
// one character at a time by measuring response speed.
if ($key === '' || !hash_equals($key, $given)) {
    http_response_code(403);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'forbidden']);
    exit;
}

$list = preg_replace('/[^a-z0-9\-]/', '', strtolower($_GET['list'] ?? '')) ?: null;

try {
    $pdo = db();
    if ($list) {
        $q = $pdo->prepare("SELECT email, list, token FROM subscribers
                            WHERE status='confirmed' AND list = ?");
        $q->execute([$list]);
    } else {
        $q = $pdo->query("SELECT email, list, token FROM subscribers
                          WHERE status='confirmed'");
    }
    header('Content-Type: application/json');
    echo json_encode(['subscribers' => $q->fetchAll(PDO::FETCH_ASSOC)]);
} catch (Throwable $e) {
    error_log('bidbeacon export: ' . $e->getMessage());
    http_response_code(500);
    header('Content-Type: application/json');
    echo json_encode(['error' => 'server error']);
}
