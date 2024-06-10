# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.financial_statements_custom import (
	get_columns,
	get_data,
	get_filtered_list_for_consolidated_report,
	get_period_list,
)


def execute(filters=None):
	period_list = get_period_list(
		filters.from_fiscal_year,
		filters.to_fiscal_year,
		filters.period_start_date,
		filters.period_end_date,
		filters.filter_based_on,
		filters.periodicity,
		company=filters.company,
	)

	income = get_data(
		filters.company,
		"Income",
		"Credit",
		"Total Revenue",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	cogs = get_data(
		filters.company,
		"Cost of Good Sold",
		"Debit",
		"Total COGS",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	expense = get_data(
		filters.company,
		"Expense",
		"Debit",
		"Total Operational Expense",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	other_revenue_expense = get_data(
		filters.company,
		"Other",
		"Debit",
		"Total Other Revenue & Expense",
		period_list,
		filters=filters,
		accumulated_values=filters.accumulated_values,
		ignore_closing_entries=True,
		ignore_accumulated_values_for_fy=True,
	)

	net_profit_loss = get_net_profit_loss(
		income, cogs, expense, other_revenue_expense, period_list, filters.company, filters.presentation_currency
	)

	data = []
	data.extend(income or [])
	data.extend(cogs or [])
	data.extend(expense or [])
	data.extend(other_revenue_expense or [])
	if net_profit_loss:
		data.append(net_profit_loss)

	columns = get_columns(filters.periodicity, period_list, filters.accumulated_values, filters.company)

	# chart = get_chart_data(filters, columns, income, expense, net_profit_loss)

	currency = filters.presentation_currency or frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)
	report_summary, primitive_summary = get_report_summary(
		period_list, filters.periodicity, income, cogs, expense, net_profit_loss, currency, filters, other_revenue_expense=other_revenue_expense
	)

	return columns, data, None, None, report_summary, primitive_summary


def get_report_summary(
    period_list, periodicity, income, cogs, expense, net_profit_loss, currency, filters, consolidated=False, other_revenue_expense=None
):
    net_income, net_cogs, net_expense, net_profit, net_other_revenue_expense = 0.0, 0.0, 0.0, 0.0, 0.0

    # from consolidated financial statement
    if filters.get("accumulated_in_group_company"):
        period_list = get_filtered_list_for_consolidated_report(filters, period_list)

    def filter_out_custom_rows(rows):
        return [row for row in rows if not row.get("is_gross_profit") and not row.get("is_operating_profit")]

    def get_specific_account_value(rows, account_name, key):
            for row in rows:
                if row.get("account_name") == account_name:
                    return flt(row.get(key, 0), 3)
            return 0
    
    income_filtered = filter_out_custom_rows(income) if income else []
    cogs_filtered = filter_out_custom_rows(cogs) if cogs else []
    expense_filtered = filter_out_custom_rows(expense) if expense else []
    other_revenue_expense_filtered = filter_out_custom_rows(other_revenue_expense) if other_revenue_expense else []

    for period in period_list:
        key = period if consolidated else period.key
        if income_filtered:
            net_income = get_specific_account_value(income_filtered, "Total Revenue", key)
        if cogs_filtered:
            net_cogs = get_specific_account_value(cogs_filtered, "Total COGS", key)
        if expense_filtered:
            net_expense = get_specific_account_value(expense_filtered, "Total Operational Expense", key)  # Adjust account name as needed
        if other_revenue_expense_filtered:
            net_other_revenue_expense = get_specific_account_value(other_revenue_expense_filtered, "Total Other Revenue & Expense", key)  # Adjust account name as needed
        if net_profit_loss:
            net_profit += net_profit_loss.get(key, 0.0)

    if len(period_list) == 1 and periodicity == "Yearly":
        profit_label = _("Profit This Year")
        income_label = _("Total Income This Year")
        cogs_label = _("Total COGS This Year")
        expense_label = _("Total Expense This Year")
        other_revenue_expense_label = _("Total Other Revenue & Expense This Year")
    else:
        profit_label = _("Net Profit")
        income_label = _("Total Income")
        cogs_label = _("Total COGS")
        expense_label = _("Total Expense")
        other_revenue_expense_label = _("Total Other Revenue & Expense")

    return [
        {"value": net_income, "label": income_label, "datatype": "Currency", "currency": currency},
        {"type": "separator", "value": "-"},
        {"value": net_cogs, "label": cogs_label, "datatype": "Currency", "currency": currency},
        {"type": "separator", "value": "-"},
        {"value": net_expense, "label": expense_label, "datatype": "Currency", "currency": currency},
        {"type": "separator", "value": "="},
        {"value": net_other_revenue_expense, "label": other_revenue_expense_label, "datatype": "Currency", "currency": currency},
        {"type": "separator", "value": "=", "color": "blue"},
        {
            "value": net_profit,
            "indicator": "Green" if net_profit > 0 else "Red",
            "label": profit_label,
            "datatype": "Currency",
            "currency": currency,
        },
    ], net_profit


def get_net_profit_loss(income, cogs, expense, other_revenue_expense, period_list, company, currency=None, consolidated=False):
    total = 0
    net_profit_loss = {
        "account_name": "'" + _("Net Profit") + "'",
        "account": "'" + _("Net Profit") + "'",
        "warn_if_negative": True,
        "currency": currency or frappe.get_cached_value("Company", company, "default_currency"),
    }

    has_value = False

    def filter_out_custom_rows(rows):
        return [row for row in rows if not row.get("is_gross_profit") and not row.get("is_operating_profit")]

    def get_specific_account_value(rows, account_name, key):
        for row in rows:
            if row.get("account_name") == account_name:
                return flt(row.get(key, 0), 3)
        return 0

    income_filtered = filter_out_custom_rows(income) if income else []
    cogs_filtered = filter_out_custom_rows(cogs) if cogs else []
    expense_filtered = filter_out_custom_rows(expense) if expense else []
    other_revenue_expense_filtered = filter_out_custom_rows(other_revenue_expense) if other_revenue_expense else []

    for period in period_list:
        key = period if consolidated else period.key

        total_income = get_specific_account_value(income_filtered, "Total Revenue", key)
        total_cogs = get_specific_account_value(cogs_filtered, "Total COGS", key)
        total_expense = get_specific_account_value(expense_filtered, "Total Operational Expense", key)  # Adjust account name as needed
        total_other_revenue_expense = get_specific_account_value(other_revenue_expense_filtered, "Total Other Revenue & Expense", key)  # Adjust account name as needed

        net_profit_loss[key] = total_income - total_cogs - total_expense - total_other_revenue_expense

        if net_profit_loss[key]:
            has_value = True

        total += flt(net_profit_loss[key])
        net_profit_loss["total"] = total
        percentage = total / total_income * 100
        net_profit_loss['percentage'] = f"{round(percentage, 2)}%"

    if has_value:
        return net_profit_loss


def get_chart_data(filters, columns, income, cogs, expense, net_profit_loss):
	labels = [d.get("label") for d in columns[2:]]

	income_data, cogs_data, expense_data, net_profit = [], [], []

	for p in columns[2:]:
		if income:
			income_data.append(income[-2].get(p.get("fieldname")))
		if cogs:
			cogs_data.append(cogs[-2].get(p.get("fieldname")))
		if expense:
			expense_data.append(expense[-2].get(p.get("fieldname")))
		if net_profit_loss:
			net_profit.append(net_profit_loss.get(p.get("fieldname")))

	datasets = []
	if income_data:
		datasets.append({"name": _("Income"), "values": income_data})
	if cogs:
		datasets.append({"name": _("COGS"), "values": cogs_data})
	if expense_data:
		datasets.append({"name": _("Expense"), "values": expense_data})
	if net_profit:
		datasets.append({"name": _("Net Profit/Loss"), "values": net_profit})

	chart = {"data": {"labels": labels, "datasets": datasets}}

	if not filters.accumulated_values:
		chart["type"] = "bar"
	else:
		chart["type"] = "line"

	chart["fieldtype"] = "Currency"

	return chart
