<?php
// COPY THIS FILE TO config.local.php ON THE SERVER AND EDIT IT.
//
// config.local.php is deliberately not in git. Deploys overwrite everything
// else in this folder but never this file, so your settings and your export
// key survive every deploy and never appear in a public repository.
//
// Anything you list here overrides the matching value in config.php.

return [
    // A real mailbox on your domain. Create it in hPanel > Emails first,
    // otherwise confirmation emails land in spam.
    'from_email'    => 'bids@leasuredigital.com',
    'support_email' => 'bids@leasuredigital.com',

    // CAN-SPAM requires a real postal address in commercial email.
    'postal'        => 'Your Business Name, 123 Street, City FL 33000',

    // Long random string. Store the SAME value as a GitHub Actions secret
    // named EXPORT_KEY so the daily job can read the confirmed list.
    // Generate one: openssl rand -hex 32
    'export_key'    => '',
];
