"""Outgoing communication blocker: this system is a test copy of production data,
so no email or SMS may ever reach a real user.

- Email: `mute_emails` is forced on for every web request, background job and
  scheduled job (plus `mute_emails: 1` in site_config for CLI). Mails still get
  queued, so you can inspect them in Email Queue; they stay "Not Sent".
- SMS (Frappe / ERPNext): Frappe's `send_sms` hook routes every SMS to `block_sms`.
- SMS (telephony app, Twilio incl. OTP): `telephony.twilio.sms.dispatch_sms` is
  replaced with `_blocked_twilio_sms` on every request and job.
Every blocked SMS is written to logs/test_studio.blocked_sms.log.
"""

import json

import frappe
from frappe import _


def mute_emails():
	"""before_request / before_job: mute email and stub every SMS path."""
	frappe.flags.mute_emails = True
	_block_twilio_sms()


def _log_blocked(to, message, via):
	log = frappe.logger("test_studio.blocked_sms", allow_site=True)
	log.setLevel("INFO")  # frappe loggers default to ERROR outside developer mode
	log.info({"via": via, "to": to, "message": frappe.safe_decode(message), "user": frappe.session.user})


def block_sms(receiver_list, msg, sender_name="", success_msg=True):
	if isinstance(receiver_list, str):
		try:
			receiver_list = json.loads(receiver_list)
		except ValueError:
			receiver_list = [receiver_list]
	if not isinstance(receiver_list, list):
		receiver_list = [receiver_list]
	_log_blocked(receiver_list, msg, "frappe send_sms")
	if success_msg:
		frappe.msgprint(_("SMS blocked: this is a test system. Nothing was sent to {0}.").format(", ".join(map(str, receiver_list))))
	return []


def _block_twilio_sms():
	try:
		from telephony.twilio import sms
	except ImportError:
		return  # telephony not installed
	if sms.dispatch_sms is not _blocked_twilio_sms:
		sms.dispatch_sms = _blocked_twilio_sms


def _blocked_twilio_sms(to, message, purpose="General"):
	from telephony.twilio import sms

	_log_blocked([to], message, f"telephony twilio ({purpose})")
	from_number = sms.get_sms_settings().sms_from_number or ""
	# keep telephony's own audit trail; callers read .name and .status from the log
	return sms.create_sms_log(
		sms.clean_phone_number(to) or to, from_number, message, purpose, "Failed", error="Blocked: test system, not sent"
	)
