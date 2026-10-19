-- =============================================================================
-- NBC Booking Engine — reference data
-- =============================================================================
-- Values here come from the NBC Booking Launch Hub (as of Oct 13–14, 2026).
-- Locations, sites, rooms, products and classes are NOT seeded: the Airtable
-- sync creates them. Settings marked "OPEN" still need a decision.
-- =============================================================================

BEGIN;

INSERT INTO course_families (code, name, slug, one_instructor_max, min_students_to_run) VALUES
  ('FA_CPR_AED', 'First Aid / CPR / AED',       'first-aid-cpr-aed', 12, NULL),
  ('BLS',        'Basic Life Support (BLS)',     'bls',                9, NULL),
  ('IT',         'Instructor Training',          'instructor-training', 6, 5);  -- "5 students are required to hold a class"

INSERT INTO app_settings (key, value, description) VALUES
  ('checkout_hold_minutes',          '15',    'Seat hold while the customer pays on Stripe (decision D2).'),
  ('stripe_checkout_expiry_minutes', '30',    'Stripe minimum; the engine expires the session itself at the hold limit.'),
  ('waitlist_offer_hours',           '2',     'Pay window for a waitlist offer.'),
  ('waitlist_offer_window_local',    '{"start":"08:00","end":"18:00"}', 'Offers are sent only in these class-local hours.'),
  ('waitlist_cutoff_one_instructor_hours', '24', 'One-instructor locations: waitlist closes 24 h before class.'),
  ('waitlist_cutoff_co_instructor',  '{"local_time":"08:00","days_before":1,"sun_mon_use_saturday":true}',
                                     'Co-instructor locations: 8 AM the day before (Saturday 8 AM for Sunday/Monday classes).'),
  ('waitlist_demand_alert_one_instructor', '3', 'Waiting count that triggers the second-session alert to the OTL.'),
  ('co_instructor_pay_cents',        '11000', 'Co-instructor pay used in the break-even formula ($110).'),
  ('cert_cost_cents_per_student',    '1000',  'Cert cost per student used in the break-even formula ($10).'),
  ('rule_a_bands',                   '[{"days":[2,3],"pct":67},{"days":[4,6],"pct":50},{"days":[7,9],"pct":42},{"days":[10,14],"pct":33},{"days":[15,30],"pct":25}]',
                                     'Ops Hub trigger to start a co-instructor search (fill % by days out).'),
  ('coverage_alert_days',            '[21,14,7]', 'Days before class that an unassigned class alerts ops; 7 escalates to Jennifer or Bre.'),
  ('instructor_drop_deadline_days',  '7',     'Instructors may release a class up to this many days before it.'),
  ('hub_first_right_days',           '7',     'HUB metros (DFW, Richmond): first right of refusal window.'),
  ('large_refund_threshold_cents',   'null',  'OPEN: refund amount that needs manager approval (not set in the Oct 14 policy).'),
  ('retention_days_client_ip',       '90',    'Purge orders.client_ip / user agent after this many days (proposed).'),
  ('retention_days_webhook_payload', '30',    'Purge webhook_events.payload after this many days (proposed).'),
  ('ghl_custom_field_ids',           '{}',    'GHL custom field ids (session id, site, date, product, Reg Type, UTMs). Differ between sandbox and live.'),
  ('environment',                    '"local"', 'local | staging | production. Set per database; staging uses Stripe test mode and GHL Sandbox 2.'),
  ('airtable_writeback_enabled',     'false', 'Only production writes back to the NBC Master Base (there is one base; staging must not write to it).'),
  ('customer_service_contact',       '{"email":"info@nationsbestcpr.com"}', 'Shown in the "Offer expired" message (waitlist rules §10, recommended).');

COMMIT;
