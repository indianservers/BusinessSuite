# Site email through Amazon SES

The shared backend mail facade and existing transactional outbox use the same transport. Site identity comes from the operator-owned `EMAIL_SITE`, never a request Host header, incoming From header, or tenant-editable settings.

For BestERP set `EMAIL_SITE=besterp` and `FRONTEND_PUBLIC_URL=https://besterp.app`. For a deployment using this shared transport for BestSchool set `EMAIL_SITE=bestschool` and `FRONTEND_PUBLIC_URL=https://bestschool.app`. Canonical www variants are accepted; deployment aliases must use the same explicit site identity and canonical public URL. The sender mapping is fixed to `BestERP <info@besterp.app>` or `BestSchool <info@bestschool.app>`. A blank site preserves existing behavior. Production BestSchool has its own application repository and adapter; its deployment instructions live there.

Private backend environment settings for branded delivery:

```dotenv
EMAIL_SITE=besterp
FRONTEND_PUBLIC_URL=https://besterp.app
SITE_SES_SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SITE_SES_SMTP_PORT=587
SITE_SES_SMTP_USERNAME=<SES SMTP username>
SITE_SES_SMTP_PASSWORD=<SES SMTP password>
```

Port 587 requires STARTTLS with certificate validation before login. Existing `SES_*` and `INTERN_HUB_SES_*` settings remain in place for explicit legacy senders such as Interns Hub at `noreply@indianservers.com`; do not replace those credentials with the new site credentials. SMTP credentials are distinct from AWS API keys. Preserve existing notification flags, recipient authorization, tenant boundaries, outbox retry/idempotency rules, and Reply-To settings. Plain branded messages gain an escaped HTML alternative with a canonical HTTPS link. Existing HTML/plain MIME content and attachments are retained.

On the current BestERP server, runtime settings are `/srv/business-suite/shared/backend.env`, loaded by the API and its in-process email worker. Keep this file private and restart `business-suite.service` after updating it. Source rollback and private environment backup for the 10 November 2026 SES change are in `/root/ses-besterp-20261110-retry`. Reapply the five new configuration fields and transport changes when releasing a different checkout; do not deploy unrelated uncommitted files.

Validation: run the site transport/identity, SMTP, shared email, and Interns Hub confirmation tests with mocked providers. Authenticate against SES using the existing SMTP library without debug logging; this sends no email. SMTP authentication does not prove identity-specific sending permission, provider acceptance, or inbox delivery. No live integration email is authorized solely by this configuration change. After explicit owner authorization, send at most one labeled integration message per site to the owner's designated address. Do not send to customers, change DNS, or create credentials/IAM grants.
