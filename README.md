# OneKey Store Bot

Telegram MODS store bot (Khmer UI).

## Files
- `main.py` — bot code
- `requirements.txt` — Python dependencies
- `aba_qr.png` — add your ABA KHQR image using this filename

## Environment variables
Set these in your hosting provider (do not commit secrets):
- `BOT_TOKEN` — fresh token from @BotFather
- `OWNER_ID` — `8824603452`
- `DB_PATH` — optional, defaults to `onekey_store.db`

## Run
```bash
pip install -r requirements.txt
python main.py
```

## Add stock keys (send these commands to your bot as the admin)
```text
/addkey ios 1h YOUR-KEY
/addkey ios 3h YOUR-KEY
/addkey ios 1d YOUR-KEY
/addkey android 1h YOUR-KEY
/addkey android 3h YOUR-KEY
/addkey android 1d YOUR-KEY
```

## Payment note
The bot displays your KHQR and forwards receipt screenshots to the admin.
An admin must verify the payment in the bank app before approving. A QR image alone
does not provide automatic payment verification. Use a payment provider API for that.

## Security
Never put the bot token in source code or a public GitHub repository. If a token was
shown in a screenshot or committed publicly, revoke it with @BotFather and use a new one.
