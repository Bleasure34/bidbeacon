<?php
// Lets the daily job fetch the confirmed list so it can send the digest.
// Protected by a shared secret, because this returns subscriber addresses.
//
// Set BIDBEACON_EXPORT_KEY below to a long random string, and store the same
// value as a GitHub Actions secret named EXPORT_KEY.

require __DIR__ . '/lib.php';

const BIDBEACON_EXPORT_KEY = 'CHANGE-ME-to-a-long-random-string';

$given = $_GET['key'] ?? '';
// hash_equals avoids leaking the key one character at a time via timing.
if (!is_string($given) || !hash_equals(BIDBEACON_EXPORT_KEY, $given)
    || BIDBEACON_EXPORT_KEY === 'CHANGE-ME-to-a-long-random-string') {
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
