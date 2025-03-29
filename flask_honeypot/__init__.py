import functools
import time
import random
import string
import requests
import csv
import io
from flask import request, session, abort, g, current_app, redirect, render_template_string, url_for, send_file
from markupsafe import Markup

class FlaskHoneypot:
	DEFAULT_DECOYS = [
		{"type": "text"},
		{"type": "checkbox"},
		{"type": "select", "options": ["", "us", "ca", "uk"]}
	]

	DEFAULT_NAMES = [
		"email", "username", "name", "subscribe", "newsletter",
		"country", "region", "phone", "zipcode", "referrer"
	]

	def __init__(self, app=None, field_name='hp_field', redirect_on_trigger=False, ban_ip=False, ban_duration=3600, decoys=None, webhook_urls=None, require_field_interaction=False, debug_log=False, enable_admin=False):
		self.field_name = field_name
		self.redirect_on_trigger = redirect_on_trigger
		self.ban_ip = ban_ip
		self.ban_duration = ban_duration
		self.banned_ips = {}
		self.ban_history = []
		self.webhook_urls = webhook_urls if isinstance(webhook_urls, list) else ([webhook_urls] if webhook_urls else [])
		self.last_webhook_sent = {}
		self.require_field_interaction = require_field_interaction
		self.debug_log = debug_log
		self.enable_admin = enable_admin
		self.decoys = self._prepare_decoys(decoys if decoys is not None else self.DEFAULT_DECOYS)
		if app:
			self.init_app(app)

	def _prepare_decoys(self, decoys):
		used_names = set()
		for decoy in decoys:
			if "name" not in decoy or not decoy["name"]:
				name = random.choice([n for n in self.DEFAULT_NAMES if n not in used_names])
				used_names.add(name)
				decoy["name"] = name + '_' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
			else:
				used_names.add(decoy["name"])
		return decoys

	def init_app(self, app):
		app.context_processor(self.context_processor)
		app.before_request(self._check_honeypot)
		app.jinja_env.globals['honeypot_input'] = self.honeypot_input

		if self.enable_admin:
			@app.route("/honeypot/admin", methods=["GET", "POST"])
			def honeypot_admin():
				now = time.time()
				if request.method == "POST":
					ip_to_unban = request.form.get("unban_ip")
					manual_ban_ip = request.form.get("manual_ban_ip")
					if ip_to_unban and ip_to_unban in self.banned_ips:
						del self.banned_ips[ip_to_unban]
					elif manual_ban_ip:
						self.banned_ips[manual_ban_ip] = now + self.ban_duration
					return redirect(url_for('honeypot_admin'))

				banned = {ip: int(expiry - now) for ip, expiry in self.banned_ips.items() if expiry > now}
				history = self.ban_history[-50:]
				return render_template_string("""
					<h2>🚨 Honeypot Admin</h2>
					<p>Banned IPs (seconds remaining):</p>
					<form method="POST">
						<ul>
						{% for ip, ttl in banned.items() %}
							<li>{{ ip }} - {{ ttl }}s
								<button name="unban_ip" value="{{ ip }}">Unban</button>
							</li>
						{% endfor %}
						</ul>
						<p>Manually ban an IP:</p>
						<input name="manual_ban_ip" placeholder="Enter IP"> <button type="submit">Ban IP</button>
					</form>
					<p><a href="{{ url_for('honeypot_export') }}">Download Ban History (CSV)</a></p>
					<h3>Ban History</h3>
					<ul>
					{% for entry in history %}
						<li>{{ entry }}</li>
					{% endfor %}
					</ul>
				""", banned=banned, history=history)

			@app.route("/honeypot/export")
			def honeypot_export():
				output = io.StringIO()
				writer = csv.writer(output)
				writer.writerow(["Timestamp", "IP", "Path", "Reason"])
				for entry in self.ban_history:
					parts = entry.split(" | ")
					ip = parts[0].split(": ")[-1].strip()
					path = parts[1].split(": ")[-1].strip()
					reason = parts[2].split(": ")[-1].strip()
					writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), ip, path, reason])
				output.seek(0)
				return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name="honeypot_ban_history.csv")

	def context_processor(self):
		return {'honeypot_input': self.honeypot_input}

	def honeypot_input(self):
		timestamp = str(time.time())
		session['_hp_time'] = timestamp
		fields = [f'<input type="hidden" name="_hp_time" value="{timestamp}">']

		if self.require_field_interaction:
			fields.append('<input type="hidden" id="_hp_focus" name="_hp_focus" value="0">')
			fields.append('<script>document.addEventListener("DOMContentLoaded", function() {\n  document.querySelectorAll("input, textarea, select").forEach(el => {\n    el.addEventListener("focus", () => {\n      document.getElementById("_hp_focus").value = 1;\n    });\n  });\n});</script>')

		fields.append(self._generate_decoy_fields())
		return Markup('\n'.join(fields))

	def _generate_decoy_fields(self):
		decoy_html = []
		if self.field_name:
			decoy_html.append(f'<input class="real-field" type="text" name="{self.field_name}" style="display:none" tabindex="-1" autocomplete="off">')
		for decoy in self.decoys:
			name = decoy.get("name")
			type_ = decoy.get("type")
			cls = "required-input"
			if type_ == "text":
				dc = f'<input class="{cls}" type="text" name="{name}" style="display:none" tabindex="-1" autocomplete="off">'
			elif type_ == "checkbox":
				dc = f'<input class="{cls}" type="checkbox" name="{name}" style="display:none" tabindex="-1">'
			elif type_ == "select":
				options = decoy.get("options", [""])
				opt_html = ''.join([f'<option value="{o}">{o}</option>' for o in options])
				dc = f'<select class="{cls}" name="{name}" style="display:none" tabindex="-1">{opt_html}</select>'
			decoy_html.append(dc)
		return ''.join(decoy_html)

	def _check_honeypot(self):
		ip = request.remote_addr or 'unknown'
		if self.enable_admin and request.path.startswith('/honeypot/admin') and ip.startswith('127.'):
			return

		now = time.time()
		self.banned_ips = {ip: expiry for ip, expiry in self.banned_ips.items() if expiry > now}

		if ip in self.banned_ips:
			abort(403)

		if request.method == 'POST':
			form_time = float(request.form.get('_hp_time', 0))
			if now - form_time < 1.0:
				return self._trigger(ip, reason="suspiciously fast submit")

			if self.require_field_interaction and request.form.get('_hp_focus') != '1':
				return self._trigger(ip, reason="no field focus")

			if self.field_name in request.form and request.form[self.field_name].strip():
				return self._trigger(ip, reason=f"legacy field '{self.field_name}' filled")

			for decoy in self.decoys:
				name = decoy.get("name")
				if name in request.form and request.form[name].strip():
					return self._trigger(ip, reason=f"decoy field '{name}' filled")

	def _trigger(self, ip, reason="honeypot triggered"):
		now = time.time()
		msg = f"[HONEYPOT] Triggered by IP: {ip} | Path: {request.path} | Reason: {reason}"
		current_app.logger.warning(msg)
		self.ban_history.append(msg)

		if self.debug_log:
			current_app.logger.debug(f"Headers: {dict(request.headers)}")
			current_app.logger.debug(f"Form data: {request.form.to_dict()}")

		if ip not in self.last_webhook_sent or now - self.last_webhook_sent[ip] > 60:
			payload = {
				"content": None,
				"embeds": [{
					"title": "🚨 Honeypot Triggered",
					"color": 15158332,
					"fields": [
						{"name": "IP", "value": ip, "inline": True},
						{"name": "Path", "value": request.path, "inline": True},
						{"name": "Reason", "value": reason, "inline": False},
						{"name": "User-Agent", "value": request.headers.get('User-Agent', 'N/A'), "inline": False}
					]
				}]
			}
			for url in self.webhook_urls:
				try:
					requests.post(url, json=payload)
				except Exception as e:
					current_app.logger.error(f"Failed to send webhook to {url}: {e}")
			self.last_webhook_sent[ip] = now

		if self.ban_ip:
			self.banned_ips[ip] = now + self.ban_duration

		if self.redirect_on_trigger:
			return redirect('/')
		else:
			abort(403)

	def protect(self, func):
		@functools.wraps(func)
		def wrapper(*args, **kwargs):
			return func(*args, **kwargs)
		return wrapper
