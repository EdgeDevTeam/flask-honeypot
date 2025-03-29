
# 🛡️ Flask Honeypot

Flask Honeypot is a Flask extension that injects invisible honeypot fields into forms to trap bots. It features optional IP banning, webhook alerts, admin UI for monitoring and management, and several layers of bot detection stealth.

---

## 🚀 Features

- Injects decoy fields (text, checkbox, dropdown)
- Triggers on:
  - Filling honeypot fields
  - Submitting forms too fast
  - No interaction with real inputs
- IP banning with configurable duration
- Discord/webhook alerts (rate-limited)
- Admin panel to view/unban/ban IPs + export CSV
- JS-based or static honeypot injection
- Configurable field types, names, and behavior

---

## 📦 Installation

```bash
pip install flask
```

Include `flask_honeypot.py` in your project or install it as a package.

---

## 🔧 Basic Usage

```python
from flask import Flask
from flask_honeypot import FlaskHoneypot

app = Flask(__name__)
app.secret_key = 'secret'

honeypot = FlaskHoneypot(app)
```

In your HTML:

```html
<form method="POST">
    {{ honeypot_input() }}
    <input name="email">
    <textarea name="message"></textarea>
    <button type="submit">Send</button>
</form>
```

---

## ⚙️ Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `field_name` | Single decoy field | `'hp_field'` |
| `redirect_on_trigger` | Redirect to `/` instead of 403 | `False` |
| `ban_ip` | Enable IP bans | `False` |
| `ban_duration` | Ban time in seconds | `3600` |
| `require_field_interaction` | Require focus before submit | `False` |
| `webhook_urls` | List of Discord/webhook URLs | `[]` |
| `debug_log` | Print headers/form data on trap | `False` |
| `enable_admin` | Enables `/honeypot/admin` route | `False` |

---

## 👮 Admin Panel

Visit `/honeypot/admin` to:
- View banned IPs
- Unban IPs
- Manually ban IPs
- Export ban logs as CSV

**Note:** 127.0.0.1 can always access the admin route.

---

## 📡 Webhook Alerts

Send alerts to Discord/webhooks with:
```python
webhook_urls=["https://discord.com/api/webhooks/..."]
```

Includes IP, path, reason, and User-Agent. Rate-limited (60s per IP).

---

## 🧪 Testing Traps

Try:
- Submitting the form instantly
- Filling hidden fields via DevTools
- Leaving everything blank

---

## 🪛 Customizing Decoys

```python
decoys = [
  {"type": "text", "name": "contact_name"},
  {"type": "checkbox"},
  {"type": "select", "options": ["", "US", "CA", "UK"]}
]
FlaskHoneypot(app, decoys=decoys)
```

If no `name` is provided, it auto-generates a realistic one.

---

## 📁 Example

See the included `run.py` for a working test case.

---

## 🧠 Ideas for Enhancement

- Password protection for `/honeypot/admin`
- IP whitelist or JWT override
- Store logs in Redis/SQLite
- Honeypot decorator for views

---

## ✅ License

MIT – Use freely, credit appreciated!
