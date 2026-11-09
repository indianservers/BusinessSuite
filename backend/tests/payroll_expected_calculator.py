"""Independent QA oracle. No imports from application payroll code."""
import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN


def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN)


def salary_segments(year, month, versions):
    """Average annual CTC/basic/HRA by applicable calendar date, inclusive bounds."""
    days = calendar.monthrange(year, month)[1]
    totals = [Decimal(0), Decimal(0), Decimal(0)]
    for day in range(1, days + 1):
        current = date(year, month, day)
        matches = [v for v in versions if v['start'] <= current and (v.get('end') is None or current <= v['end'])]
        if not matches:
            continue
        assert len(matches) == 1, 'Oracle requires nonoverlapping explicit salary versions'
        version = matches[0]
        monthly = Decimal(version['ctc']) / 12
        basic = Decimal(version.get('basic') or 0) or monthly * Decimal('.4')
        hra = Decimal(version.get('hra') or 0) or basic * Decimal('.5')
        for index, amount in enumerate((monthly, basic, hra)):
            totals[index] += amount / days
    return tuple(money(value) for value in totals)


def monthly_pay(monthly, calendar_days, employed_days, working_days, lop, earnings=0, deductions=0, reimbursement=0):
    eligible = money(Decimal(monthly) * Decimal(employed_days) / Decimal(calendar_days))
    gross = eligible - eligible * Decimal(lop) / Decimal(working_days or 1) + Decimal(earnings)
    return money(gross), money(gross - Decimal(deductions) + Decimal(reimbursement))
