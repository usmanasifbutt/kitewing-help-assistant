Skip to main content
The Perch  |  Home  |  People  |  IT  |  Finance  |  Search
Home > IT > Support > IT Support Guide

# IT Support Guide

Last edited by Jordan Okafor on 10 April 2025 · 12 min read

On this page: Getting help | Error codes | Request forms | Laptops and equipment | Passwords

## Getting help

The IT Helpdesk is open Monday to Friday, 08:00 to 18:00 Central Time in the US and 08:00 to 18:00 UK time. Raise a ticket in the KiteDesk portal, email it-help@kitewing.example, or call extension 4357 (it spells HELP). For urgent security issues outside these hours, call extension 4357 and choose option 9.

Tickets are prioritised like this:

- P1 (critical - many people cannot work): response within 30 minutes
- P2 (one person cannot work): response within 4 working hours
- P3 (something is broken but there is a workaround): response within 1 working day
- P4 (requests and questions): response within 3 working days

[Back to top](#top)

## Error code reference

The Kitewing Compliance Agent and the VPN client show a KSW error code when something is wrong. Find your code below. If your code isnâ€™t listed, raise a P3 ticket and include a screenshot.

### KSW-1043: MFA token expired

Your multi-factor authentication token has expired, or the Kitewing Authenticator app was reinstalled. Open KiteDesk Self Service, choose "Reset MFA", and re-enrol the app on your phone. If you cannot reach Self Service, call the Helpdesk.

### KSW-1107: VPN certificate not trusted

The VPN client cannot verify your device certificate. This usually happens just after the certificate renews. Open Self Service, run "Reinstall VPN certificate", then restart the VPN client.

### KSW-2210: Disk encryption check failed

The Compliance Agent found that full-disk encryption (FileVault on Mac, BitLocker on Windows) is switched off or has not finished. Your laptop is blocked from the corporate network until encryption is complete. Turn encryption back on, leave the laptop plugged in until encryption finishes, then open the Compliance Agent and click "Re-check now". If the code is still showing after 24 hours, raise a P2 ticket.

### KSW-2214: Endpoint protection out of date

The Compliance Agent found that your endpoint protection (antivirus) definitions are more than 7 days old. Stay connected to the internet for 30 minutes so the updates can download, then click "Re-check now". You can keep working while this code is showing, but it becomes a network block after 3 days.

### KSW-3302: SSO session conflict

You are signed in to Single Sign-On with two different accounts in the same browser. Sign out of all Kitewing apps, clear your browser cookies for kitewing.example, and sign in again using only your work account.

### KSW-4471: Software licence limit reached

The application you are trying to open has no free licences. Ask your manager to submit Form IT-311 so that a licence can be assigned to you, or ask IT whether an unused licence can be reclaimed.

Was this page helpful? Yes / No

## Request forms

All forms are in KiteDesk under Forms.

- **Form IT-207 - Hardware Request.** Use this for a new monitor, keyboard, headset or docking station, or for a laptop replacement outside the normal refresh cycle. Your manager approves the request, and standard items ship within 5 working days.
- **Form IT-311 - Software Access Request.** Use this to request access to a SaaS application or a new software licence. The applicationâ€™s data owner must approve it. Access is usually granted within 2 working days of approval.
- **Form IT-412 - Security Incident Report.** Use this to report a lost or stolen device, a phishing email you clicked, or any other security incident. Submit it within 1 hour of noticing the problem. The Information Security Policy has the full steps.
- **Form IT-509 - Leaver Equipment Return.** Your manager submits this when someone leaves Kitewing, to arrange the return of their laptop and accessories.

## Connecting to the VPN

Install the Kitewing VPN client from KiteDesk Self Service. It connects automatically when your laptop starts. You must be connected to the VPN to reach internal systems such as PeopleHub and The Perch from outside an office. If the VPN shows an error code, look it up in the error code reference above.

## Wi-Fi in the offices

There are two Wi-Fi networks in every office. KW-Corp is for Kitewing laptops only and connects automatically using your device certificate. KW-Guest is for visitors and personal devices; reception gives out a new guest password every day. Never connect a Kitewing laptop to KW-Guest.

## Printing

Kitewing uses follow-me printing. Send your document to the "Kitewing-Print" queue, then tap your building badge on any printer to release it. Printers are on the 3rd floor in Austin and the 2nd floor in Leeds. Jobs that aren't released within 24 hours are deleted.

## Company phones

Company phones are issued to roles that need one, such as on-call engineers and sales staff. Ask your manager to submit Form IT-207. You can also read work email on your personal phone by installing the Kitewing Work Profile from KiteDesk Self Service; this keeps work data separate from your personal data. A lost phone that has work data on it must be reported with Form IT-412.

## Software catalogue

KiteDesk Self Service has a catalogue of pre-approved software that you can install yourself, such as Zoom, Slack, the Microsoft Office apps and the approved Kitewing AI Assistant. Anything that isn't in the catalogue needs a Software Access Request, Form IT-311.

## Laptops and equipment

Kitewing replaces laptops every 3 years. You will get an email from IT about 4 weeks before your refresh date. The standard laptop is a 14-inch MacBook Pro for engineering and design roles, and a 14-inch Windows laptop for all other roles. If you need a different machine for a medical or accessibility reason, raise Form IT-207 and explain in the notes.

Kitewingâ€™s loaner pool keeps spare laptops at the Austin and Leeds offices for short-term use while yours is being repaired.

## Passwords

Your password must be at least 14 characters long. We recommend a passphrase of four or more random words. Store your passwords in the company password manager, and never reuse your Kitewing password on another website. Passwords no longer expire on a schedule, but you must change your password straight away if you think it has been exposed.

Was this page helpful? Yes / No

[Back to top](#top)

---
© 2025 Kitewing Software. All rights reserved.  |  Privacy  |  Cookie settings  |  Accessibility
