<?php
header('Content-Type: application/json');
$store = __DIR__ . '/entries.json';
function load_entries($f) {
    return is_file($f) ? json_decode(file_get_contents($f), true) : [];
}
$action = $_REQUEST['action'] ?? 'list';
if ($action === 'add' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $entries = load_entries($store);
    $entry = ['name' => trim($_POST['name'] ?? ''),
              'message' => trim($_POST['message'] ?? ''),
              'ts' => time()];
    $entries[] = $entry;
    file_put_contents($store, json_encode($entries));
    echo json_encode(['ok' => true, 'entry' => $entry]);
} else {
    echo json_encode(['ok' => true, 'entries' => load_entries($store)]);
}
