# Local Telegram auto-reply

Open `/power-apps/automations?environment=development`. The **Telegram auto-reply** panel belongs to Power Apps Automations. It creates a normal versioned automation with three modules:

1. Telegram · Message received
2. Telegram · Check enquiry
3. Telegram Bot · Send message

Connect a BotFather token using **Connect Telegram bot**. Setup verifies the bot and checks for an existing webhook before enabling replies. Credentials use the existing encrypted backend vault; tokens never enter workflow definitions, browser storage, or execution output.

Keep the backend and the local automation worker running. From the `backend` directory:

```powershell
.\venv\Scripts\python.exe -m app.apps.power_apps.worker --poll-seconds 1
```

The worker polls roughly every five seconds. Use only one polling listener for a bot. Telegram polling cannot operate alongside that bot's webhook; setup refuses an existing webhook rather than deleting it. See the [Telegram Bot API](https://core.telegram.org/bots/api#getupdates).

Send `/start` privately to the bot, then `Sales`, `Support`, or `Order status`. The conversation collects the sender's name and requirement (or order number/question), records the enquiry, and acknowledges receipt. `/cancel` resets the conversation. This scenario records enquiries only in the automation; it does not claim to retrieve order status or create CRM leads.

Only new private text messages from human senders are processed. Messages older than setup are skipped. The worker persists Telegram update offsets and uses a bot/update idempotency key to prevent duplicate runs. Pause/enable is available on the Automations page. Enquiry history shows the planned reply; open execution history for actual delivery status. External sends use the existing connector operation journal, including its handling of uncertain deliveries.

The workflow retains the originating branch and delegated owner's current permissions. Revoked credentials, company membership, or module permissions prevent execution. Message payloads follow the workflow's normal retention policy (30 days by default). The offline conversation preview neither stores enquiries nor sends messages.

Validation: `tests/test_power_telegram.py`, `tests/test_power_telegram_automations.py`, and `playwright/power-telegram-automations.spec.ts` cover encrypted credentials, setup, conversation state, replies, update deduplication, access checks, pause controls, and desktop/mobile UI. Provider calls in automated tests are mocked; live setup verifies identity and polling without sending unsolicited test messages.
