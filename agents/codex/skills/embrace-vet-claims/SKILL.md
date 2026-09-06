---
name: embrace-vet-claims
description: Discover and parse pending BluePearl veterinary invoices from Gmail, prepare confirmation-gated Embrace Pet Insurance claims for review, submit approved claims, and clean up matching invoice, receipt, and MFA email. Use when Thurston asks to handle another BluePearl or Embrace pet-insurance claim.
---

# Embrace Vet Claims

Treat this as a live insurance workflow. Confirm every review value before the first submission in a run. Never send the runner's `SUBMIT` token without explicit user approval.

## Discover the invoice

Search Gmail:

```text
from:clientcare.ga@bluepearlvet.com subject:Invoice has:attachment
```

Require the `INBOX` label. Pending messages may contain pre-payment and paid copies of the same invoice with the same filename. Parse every pending attachment before choosing one.

Prefer the Gmail attachment reader when it reports `read_attachment_supported: true`. The portal upload still requires a local path, so locate the attachment in Mimestream's cache:

```text
~/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Mimestream.sqlite
~/Library/Containers/com.mimestream.Mimestream/Data/Library/Application Support/Mimestream/Attachments
```

Query the relevant Gmail message IDs:

```sql
select m.ZSERVERID, m.ZISININBOX, a.Z_PK, a.ZFILENAME, a.ZDOWNLOADED
from ZMESSAGE m
join ZMESSAGECONTENT c on c.ZMESSAGE = m.Z_PK
join ZATTACHMENT a on a.ZCONTENT = c.Z_PK
where m.ZSERVERID in ('<gmail-message-id>');
```

The local path is `Attachments/p<attachment-pk>/<filename>`. If `ZDOWNLOADED = 0`, open the message in Mimestream to fetch it, then query again.

## Parse and normalize

Run:

```sh
uv run --with pdfplumber python /Users/thurstonsand/.codex/skills/embrace-vet-claims/scripts/parse_bluepearl_invoice.py <invoice.pdf>
```

Use the paid copy when duplicate messages represent the same invoice. A paid copy normally has `balance_due: "0.00"` and a non-null `amount_paid`. Use parsed `total` as the claim amount; BluePearl's separate `Invoice Total` is the undiscounted subtotal.

Archive an invoice without submitting only when `claim_action` is `archive_zero_invoice`. Do not treat a paid invoice's zero balance as a zero-dollar invoice.

Create a claim JSON file:

```json
{
  "invoice_path": "/absolute/path/Sandberg-MMDDYYYY.pdf",
  "pet": "Chance",
  "provider": "BluePearl - Georgia Veterinary Rehabilitation",
  "invoice_date": "MM/DD/YYYY",
  "total": "470.93",
  "diagnosis": "Intervertebral disc disease"
}
```

## Prepare and submit

Load the bundled workspace dependencies, then start the checkpointed Playwright runner using the returned Node executable and package path:

```sh
NODE_PATH=<workspace-node-modules> <workspace-node> /Users/thurstonsand/.codex/skills/embrace-vet-claims/scripts/run_claim.cjs <claim.json>
```

Keep the process running and respond to its JSON events:

1. On `mfa_required`, search Gmail for the newest message matching:

   ```text
   from:reply@e.embracepetinsurance.com subject:"Your verification code from Embrace Pet Insurance" newer_than:1d
   ```

   Wait for the newest timestamp, then write its eight-digit code to the runner's stdin.

2. On `review_ready`, verify the pet, provider, invoice date, invoice amount, diagnosis, and filename from the emitted review text. Show those exact values to the user and wait for explicit approval.

3. Only after approval, write exactly `SUBMIT` to stdin.

4. On `submitted`, record the emitted claim number.

The runner uses the live Nuxt app's existing Pinia instance for the disabled invoice-date input:

```js
document.querySelector('#__nuxt').__vue_app__.config.globalProperties.$pinia._s.get('submit-claim')
```

Do not rediscover the store by importing Nuxt chunks and invoking unknown exports. Those functions can navigate away from the claim.

## Clean up

After successful submission:

- Archive the submitted BluePearl invoice thread. This also archives duplicate pre-payment and paid messages in that thread.
- Delete MFA-code messages generated during the run.
- Search narrowly for an Embrace `We received your claim document(s)` receipt using the new claim number and current-day recency. Archive it if present. Do not archive EOB, payment, claim-complete, or medical-history-action messages.
- Do not archive positive invoices that were not submitted.

## Validation

Validate claim JSON without opening the portal:

```sh
NODE_PATH=<workspace-node-modules> <workspace-node> /Users/thurstonsand/.codex/skills/embrace-vet-claims/scripts/run_claim.cjs <claim.json> --validate-only
```

Validate the skill:

```sh
uv run --with pyyaml python /Users/thurstonsand/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/thurstonsand/.codex/skills/embrace-vet-claims
```

Known working submission: invoice `2031061`, date `07/22/2026`, total `$470.93`, claim `EC1272-4588`.
