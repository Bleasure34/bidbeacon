<?php
// Defaults only. NOTHING SECRET GOES IN THIS FILE — it lives in a public
// repository and is overwritten on every deploy.
//
// Real values go in config.local.php, which you create once by hand on the
// server. It is never in git and deploys never touch it.
// See config.local.example.php.

return [
    'from_email'    => 'bids@leasuredigital.com',
    'from_name'     => 'BidBeacon',
    'base_url'      => 'https://leasuredigital.com/bidbeacon',
    'site_url'      => 'https://bids.leasuredigital.com',
    'postal'        => '',
    'support_email' => 'bids@leasuredigital.com',
    'rate_limit'    => 5,

    // Empty means the export endpoint refuses every request, which is the
    // correct behaviour until a real key is set in config.local.php.
    'export_key'    => '',
];
