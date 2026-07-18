"""Runs once when the app is installed on a site (see hooks.py:after_install).
Creates the roles the app depends on and a sane default Commerce Settings,
so the app is usable immediately after `bench install-app` without any
manual setup step.
"""

import frappe


def after_install():
	_create_role("Commerce Manager", desk_access=1)
	_create_role("Commerce API", desk_access=0)

	if not frappe.db.exists("Commerce Settings", "Commerce Settings"):
		frappe.get_single("Commerce Settings").save(ignore_permissions=True)

	frappe.db.commit()
	print("Advanced Commerce: roles and default settings created.")


def _create_role(role_name, desk_access):
	if frappe.db.exists("Role", role_name):
		return
	frappe.get_doc(
		{"doctype": "Role", "role_name": role_name, "desk_access": desk_access}
	).insert(ignore_permissions=True)
