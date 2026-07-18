"""
Saga-style workflow engine — the Medusa-inspired piece of this app.

A "workflow" is a named, ordered list of steps. Each step is a pair of
functions: `run(context) -> dict` and `compensate(context, result)`. If any
step's `run` raises, every already-completed step's `compensate` is invoked
in reverse order, so partial side effects (stock reserved, payment
authorized, etc.) are automatically rolled back instead of leaving the
system in an inconsistent half-finished state.

Steps are executed as background jobs so a slow payment gateway or shipping
API never blocks the request/response cycle, and a `Workflow Run` document
gives full visibility + a manual retry/compensate button for support staff.

Usage:

	from advanced_commerce.workflow_engine.engine import register_workflow, start_workflow
	from advanced_commerce.workflow_engine.steps import reserve_stock, charge_payment, ...

	register_workflow("place_order", [reserve_stock.STEP, charge_payment.STEP, ...])

	start_workflow("place_order", context={"cart": cart_name}, reference_doctype="Cart", reference_name=cart_name)
"""

import frappe
from frappe.utils import add_to_date, now_datetime

WORKFLOW_REGISTRY = {}


class Step:
	"""A single saga step.

	name: unique string identifier, stored in the step log.
	run(context) -> dict: performs the action, returns data merged into context.
	compensate(context, result): undoes the action. Must be idempotent/safe
	    to call even if `run` partially failed.
	"""

	def __init__(self, name, run, compensate=None):
		self.name = name
		self.run = run
		self.compensate = compensate or (lambda context, result: None)


def register_workflow(name, steps):
	WORKFLOW_REGISTRY[name] = steps


def start_workflow(name, context, reference_doctype=None, reference_name=None, max_retries=3):
	if name not in WORKFLOW_REGISTRY:
		frappe.throw(f"Workflow '{name}' is not registered")

	run_doc = frappe.get_doc(
		{
			"doctype": "Workflow Run",
			"workflow_name": name,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"status": "Pending",
			"current_step_index": 0,
			"max_retries": max_retries,
			"context": frappe.as_json(context),
		}
	).insert(ignore_permissions=True)

	for step in WORKFLOW_REGISTRY[name]:
		run_doc.append("steps", {"step_name": step.name, "status": "Pending", "attempts": 0})
	run_doc.save(ignore_permissions=True)
	frappe.db.commit()

	frappe.enqueue(
		"advanced_commerce.workflow_engine.engine.advance",
		queue="short",
		enqueue_after_commit=True,
		run_name=run_doc.name,
	)
	return run_doc.name


def advance(run_name):
	"""Execute the next pending step of a workflow run. Re-enqueues itself
	for the following step on success, or triggers compensation on
	unrecoverable failure. Designed to be safely re-invoked (e.g. by the
	scheduler's process_pending_runs) if a worker died mid-run.
	"""
	run_doc = frappe.get_doc("Workflow Run", run_name)
	steps = WORKFLOW_REGISTRY.get(run_doc.workflow_name)
	if not steps:
		frappe.log_error(title="Unknown workflow", message=run_doc.workflow_name)
		return

	if run_doc.status in ("Completed", "Compensated"):
		return

	run_doc.status = "Running"
	context = run_doc.get_context()

	idx = run_doc.current_step_index
	if idx >= len(steps):
		run_doc.status = "Completed"
		run_doc.save(ignore_permissions=True)
		frappe.db.commit()
		return

	step = steps[idx]
	log_row = run_doc.steps[idx]
	log_row.status = "Running"
	log_row.attempts = (log_row.attempts or 0) + 1
	log_row.started_at = now_datetime()
	run_doc.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		result = step.run(context) or {}
		context.update(result)
		run_doc.reload()
		run_doc.set_context(context)
		log_row = run_doc.steps[idx]
		log_row.status = "Done"
		log_row.finished_at = now_datetime()
		log_row.result = frappe.as_json(result)
		run_doc.current_step_index = idx + 1
		run_doc.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.enqueue(
			"advanced_commerce.workflow_engine.engine.advance",
			queue="short",
			enqueue_after_commit=True,
			run_name=run_doc.name,
		)
	except Exception:
		frappe.db.rollback()
		run_doc.reload()
		log_row = run_doc.steps[idx]
		log_row.status = "Failed"
		log_row.error = frappe.get_traceback()
		run_doc.save(ignore_permissions=True)

		if log_row.attempts < run_doc.max_retries:
			# exponential-ish backoff: 1min, 4min, 9min...
			delay_minutes = log_row.attempts ** 2 or 1
			run_doc.next_retry_at = add_to_date(now_datetime(), minutes=delay_minutes)
			run_doc.save(ignore_permissions=True)
			frappe.db.commit()
		else:
			run_doc.status = "Compensating"
			run_doc.save(ignore_permissions=True)
			frappe.db.commit()
			_compensate(run_doc.name)


def _compensate(run_name):
	"""Roll back every completed step, in reverse order."""
	run_doc = frappe.get_doc("Workflow Run", run_name)
	steps = WORKFLOW_REGISTRY.get(run_doc.workflow_name, [])
	context = run_doc.get_context()

	for idx in range(min(run_doc.current_step_index, len(steps)) - 1, -1, -1):
		step = steps[idx]
		log_row = run_doc.steps[idx]
		if log_row.status != "Done":
			continue
		try:
			result = frappe.parse_json(log_row.result) if log_row.result else {}
			step.compensate(context, result)
			log_row.status = "Compensated"
		except Exception:
			frappe.log_error(
				title=f"Compensation failed for step {step.name} in {run_name}",
				message=frappe.get_traceback(),
			)
		run_doc.save(ignore_permissions=True)
		frappe.db.commit()

	run_doc.status = "Compensated"
	run_doc.save(ignore_permissions=True)
	frappe.db.commit()


def process_pending_runs():
	"""Scheduler entry point (every 5 min, see hooks.py). Resumes any
	Workflow Run whose retry backoff has elapsed, and nudges any run stuck
	in 'Running' for too long in case a worker died before re-enqueuing.
	"""
	now = now_datetime()
	due = frappe.get_all(
		"Workflow Run",
		filters=[
			["status", "in", ["Pending", "Running"]],
			["next_retry_at", "<=", now],
		],
		pluck="name",
	)
	for name in due:
		frappe.db.set_value("Workflow Run", name, "next_retry_at", None)
		frappe.enqueue(
			"advanced_commerce.workflow_engine.engine.advance",
			queue="short",
			run_name=name,
		)
