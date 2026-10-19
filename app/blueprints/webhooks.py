"""Inbound webhooks. Stubs until their build phase.

Every handler will: verify the signature on the raw body, record the event in
webhook_events (duplicates are skipped by the unique event id), reply 2xx
quickly, and do slow work afterwards from the outbox.
  * Stripe: checkout.session.completed / .expired (phase 3), plus
    charge.refunded and charge.dispute.created (recommended).
  * GHL: ContactUpdate, ContactDndUpdate, InboundMessage, OutboundMessage,
    OpportunityStageUpdate (phase 4), verified with X-GHL-Signature.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")


@bp.post("/stripe")
def stripe():
    return jsonify(status="not_implemented", phase="3. Checkout"), 501


@bp.post("/ghl")
def ghl():
    return jsonify(status="not_implemented", phase="4. GHL sync"), 501
