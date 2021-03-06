from __future__ import unicode_literals
import frappe
import random
from frappe.utils import random_string
from erpnext.projects.doctype.timesheet.test_timesheet import make_timesheet
from erpnext.projects.doctype.timesheet.timesheet import make_salary_slip, make_sales_invoice
from frappe.utils.make_random import how_many, get_random
from erpnext.hr.doctype.expense_claim.expense_claim import get_expense_approver, make_bank_entry

def work():
	frappe.set_user(frappe.db.get_global('demo_hr_user'))
	year, month = frappe.flags.current_date.strftime("%Y-%m").split("-")

	# process payroll
	if not frappe.db.get_value("Salary Slip", {"month": month, "fiscal_year": year}):
		process_payroll = frappe.get_doc("Process Payroll", "Process Payroll")
		process_payroll.company = frappe.flags.company
		process_payroll.month = month
		process_payroll.fiscal_year = year
		process_payroll.create_sal_slip()
		process_payroll.submit_salary_slip()
		r = process_payroll.make_journal_entry(frappe.get_value('Account',
			{'account_name': 'Salary'}))

		journal_entry = frappe.get_doc(r)
		journal_entry.cheque_no = random_string(10)
		journal_entry.cheque_date = frappe.flags.current_date
		journal_entry.posting_date = frappe.flags.current_date
		journal_entry.insert()
		journal_entry.submit()
	
	if frappe.db.get_global('demo_hr_user'):
		make_timesheet_records()
	
		#expense claim
		expense_claim = frappe.new_doc("Expense Claim")
		expense_claim.extend('expenses', get_expenses())
		expense_claim.employee = get_random("Employee")
		expense_claim.company = frappe.flags.company
		expense_claim.posting_date = frappe.flags.current_date
		expense_claim.exp_approver = filter((lambda x: x[0] != 'Administrator'), get_expense_approver(None, '', None, 0, 20, None))[0][0]
		expense_claim.insert()

		rand = random.random()

		if rand < 0.4:
			expense_claim.approval_status = "Approved"
			update_sanctioned_amount(expense_claim)
			expense_claim.submit()

			if random.randint(0, 1):
				#make journal entry against expense claim
				je = frappe.get_doc(make_bank_entry(expense_claim.name))
				je.posting_date = frappe.flags.current_date
				je.cheque_no = random_string(10)
				je.cheque_date = frappe.flags.current_date
				je.flags.ignore_permissions = 1
				je.submit()

		elif rand < 0.2:
			expense_claim.approval_status = "Rejected"
			expense_claim.submit()

def get_expenses():
	expenses = []
	expese_types = frappe.db.sql("""select ect.name, eca.default_account from `tabExpense Claim Type` ect,
		`tabExpense Claim Account` eca where eca.parent=ect.name
		and eca.company=%s """, frappe.flags.company,as_dict=1)

	for expense_type in expese_types[:random.randint(1,4)]:
		claim_amount = random.randint(1,20)*10

		expenses.append({
			"expense_date": frappe.flags.current_date,
			"expense_type": expense_type.name,
			"default_account": expense_type.default_account or "Miscellaneous Expenses - WPL",
			"claim_amount": claim_amount,
			"sanctioned_amount": claim_amount
		})

	return expenses

def update_sanctioned_amount(expense_claim):
	for expense in expense_claim.expenses:
		sanctioned_amount = random.randint(1,20)*10

		if sanctioned_amount < expense.claim_amount:
			expense.sanctioned_amount = sanctioned_amount

def get_timesheet_based_salary_slip_employee():
	return frappe.get_all('Salary Structure', fields = ["distinct employee as name"],
		filters = {'salary_slip_based_on_timesheet': 1})
	
def make_timesheet_records():
	employees = get_timesheet_based_salary_slip_employee()
	for employee in employees:
		ts = make_timesheet(employee.name, simulate = True, billable = 1, activity_type=get_random("Activity Type"))

		rand = random.random()
		if rand >= 0.3:
			make_salary_slip_for_timesheet(ts.name)

		rand = random.random()
		if rand >= 0.2:
			make_sales_invoice_for_timesheet(ts.name)

def make_salary_slip_for_timesheet(name):
	salary_slip = make_salary_slip(name)
	salary_slip.insert()
	salary_slip.submit()
	frappe.db.commit()

def make_sales_invoice_for_timesheet(name):
	sales_invoice = make_sales_invoice(name)
	sales_invoice.customer = get_random("Customer")
	sales_invoice.append('items', {
		'item_code': get_random("Item", {"has_variants": 0, "is_stock_item": 0, "is_fixed_asset": 0}),
		'qty': 1,
		'rate': 1000
	})
	sales_invoice.flags.ignore_permissions = 1
	sales_invoice.set_missing_values()
	sales_invoice.calculate_taxes_and_totals()
	sales_invoice.insert()
	sales_invoice.submit()
	frappe.db.commit()