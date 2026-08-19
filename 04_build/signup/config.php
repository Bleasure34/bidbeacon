<?php
// BidBeacon signup handler — settings.
// Upload this folder to your Hostinger public_html, then edit the values below.

return [
    // Shown to subscribers and used as the From: address. Must be a real
    // mailbox on your domain, or mail lands in spam.
    'from_email'   => 'bids@leasuredigital.com',
    'from_name'    => 'BidBeacon',

    // Where this folder ends up, no trailing slash. Used to build the
    // confirm and unsubscribe links inside emails.
    'base_url'     => 'https://leasuredigital.com/bidbeacon',

    // Where to send people after they act. Your GitHub Pages site.
    'site_url'     => 'https://bids.leasuredigital.com',

    // CAN-SPAM requires a real postal address in commercial email.
    'postal'       => '',

    // Reply-to / support address shown in emails.
    'support_email' => 'bids@leasuredigital.com',

    // Signups allowed per IP per hour. Cheap abuse brake.
    'rate_limit'   => 5,
];
