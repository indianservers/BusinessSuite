from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.leave import LeaveType, LeaveBalance, LeaveBalanceLedger, LeaveRequest
from app.models.employee import Employee


LEAVE_ACCRUAL_FREQUENCIES = {"daily", "weekly", "monthly", "quarterly", "annual"}


def get_leave_type(db: Session, leave_type_id: int) -> Optional[LeaveType]:
    return db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()


def get_all_leave_types(db: Session) -> List[LeaveType]:
    return db.query(LeaveType).filter(LeaveType.is_active == True).all()


def get_leave_balance(db: Session, employee_id: int, leave_type_id: int, year: int) -> Optional[LeaveBalance]:
    return db.query(LeaveBalance).filter(
        and_(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.year == year,
        )
    ).first()


def get_employee_leave_balances(db: Session, employee_id: int, year: int) -> List[LeaveBalance]:
    return db.query(LeaveBalance).filter(
        and_(LeaveBalance.employee_id == employee_id, LeaveBalance.year == year)
    ).all()


def get_available_balance(balance: LeaveBalance) -> Decimal:
    return balance.allocated + balance.carried_forward - balance.used - balance.pending


def _money_days(value: Decimal) -> Decimal:
    return (value or Decimal("0")).quantize(Decimal("0.1"))


def _period_key(frequency: str, run_date: date) -> str:
    if frequency == "monthly":
        return f"{run_date.year}-{run_date.month:02d}"
    if frequency == "weekly":
        year, week, _ = run_date.isocalendar()
        return f"{year}-W{week:02d}"
    if frequency == "quarterly":
        quarter = ((run_date.month - 1) // 3) + 1
        return f"{run_date.year}-Q{quarter}"
    if frequency == "daily":
        return run_date.isoformat()
    return str(run_date.year)


def _is_accrual_due(frequency: str, run_date: date) -> bool:
    if frequency == "daily":
        return True
    if frequency == "weekly":
        return run_date.weekday() == 0
    if frequency == "monthly":
        return True
    if frequency == "quarterly":
        return run_date.month in {3, 6, 9, 12}
    return run_date.month == 1


def _accrual_amount(leave_type: LeaveType) -> Decimal:
    frequency = (leave_type.accrual_frequency or "annual").lower()
    if frequency == "daily":
        return _money_days(Decimal(leave_type.days_allowed or 0) / Decimal("365"))
    if frequency == "weekly":
        return _money_days(Decimal(leave_type.days_allowed or 0) / Decimal("52"))
    if frequency == "monthly":
        return _money_days(Decimal(leave_type.days_allowed or 0) / Decimal("12"))
    if frequency == "quarterly":
        return _money_days(Decimal(leave_type.days_allowed or 0) / Decimal("4"))
    return _money_days(Decimal(leave_type.days_allowed or 0))


def _employee_eligible_for_leave_type(employee: Employee, leave_type: LeaveType, run_date: date) -> bool:
    if employee.status not in {"Active", "Probation"}:
        return False
    if employee.deleted_at is not None:
        return False
    if leave_type.applicable_gender and leave_type.applicable_gender != "All" and employee.gender != leave_type.applicable_gender:
        return False
    if employee.date_of_joining and leave_type.applicable_from_months:
        months_worked = (run_date.year - employee.date_of_joining.year) * 12 + (run_date.month - employee.date_of_joining.month)
        if months_worked < int(leave_type.applicable_from_months or 0):
            return False
    return True


def run_scheduled_leave_accruals(db: Session, run_date: date | None = None, created_by: int | None = None) -> dict:
    run_date = run_date or date.today()
    year = run_date.year
    credited = 0
    skipped = 0

    leave_types = db.query(LeaveType).filter(LeaveType.is_active == True).all()
    employees = db.query(Employee).filter(Employee.status.in_(["Active", "Probation"]), Employee.deleted_at.is_(None)).all()

    for leave_type in leave_types:
        frequency = (leave_type.accrual_frequency or "annual").lower()
        if frequency not in LEAVE_ACCRUAL_FREQUENCIES or not _is_accrual_due(frequency, run_date):
            continue
        amount = _accrual_amount(leave_type)
        if amount <= Decimal("0"):
            continue
        period_key = _period_key(frequency, run_date)
        reason = f"Scheduled {frequency} accrual {period_key}"
        for employee in employees:
            if not _employee_eligible_for_leave_type(employee, leave_type, run_date):
                skipped += 1
                continue
            balance = get_leave_balance(db, employee.id, leave_type.id, year)
            if not balance:
                balance = LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=leave_type.id,
                    year=year,
                    allocated=Decimal("0"),
                )
                db.add(balance)
                db.flush()

            already_credited = db.query(LeaveBalanceLedger).filter(
                LeaveBalanceLedger.leave_balance_id == balance.id,
                LeaveBalanceLedger.transaction_type == "scheduled_accrual",
                LeaveBalanceLedger.reason == reason,
            ).first()
            if already_credited:
                skipped += 1
                continue

            balance.allocated = _money_days(Decimal(balance.allocated or 0) + amount)
            add_ledger_entry(
                db,
                balance=balance,
                transaction_type="scheduled_accrual",
                amount=amount,
                balance_after=get_available_balance(balance),
                reason=reason,
                created_by=created_by,
            )
            credited += 1

    db.commit()
    return {"credited": credited, "skipped": skipped, "run_date": run_date.isoformat()}


def run_leave_carry_forward(
    db: Session,
    *,
    from_year: int,
    to_year: int | None = None,
    created_by: int | None = None,
) -> dict:
    to_year = to_year or from_year + 1
    carried = 0
    skipped = 0

    source_balances = (
        db.query(LeaveBalance)
        .join(LeaveType, LeaveType.id == LeaveBalance.leave_type_id)
        .filter(LeaveBalance.year == from_year, LeaveType.is_active == True)
        .all()
    )
    for source in source_balances:
        leave_type = source.leave_type
        if not leave_type or not leave_type.carry_forward:
            skipped += 1
            continue

        available = get_available_balance(source)
        limit = Decimal(leave_type.carry_forward_limit or 0)
        carry_amount = max(Decimal("0"), min(available, limit)) if limit > 0 else max(Decimal("0"), available)
        carry_amount = _money_days(carry_amount)
        if carry_amount <= 0:
            skipped += 1
            continue

        target = get_leave_balance(db, source.employee_id, source.leave_type_id, to_year)
        if not target:
            target = LeaveBalance(
                employee_id=source.employee_id,
                leave_type_id=source.leave_type_id,
                year=to_year,
                allocated=Decimal("0"),
                used=Decimal("0"),
                pending=Decimal("0"),
                carried_forward=Decimal("0"),
            )
            db.add(target)
            db.flush()

        reason = f"Carry forward from {from_year} to {to_year}"
        already_carried = db.query(LeaveBalanceLedger).filter(
            LeaveBalanceLedger.leave_balance_id == target.id,
            LeaveBalanceLedger.transaction_type == "carry_forward",
            LeaveBalanceLedger.reason == reason,
        ).first()
        if already_carried:
            skipped += 1
            continue

        target.carried_forward = _money_days(Decimal(target.carried_forward or 0) + carry_amount)
        add_ledger_entry(
            db,
            balance=target,
            transaction_type="carry_forward",
            amount=carry_amount,
            balance_after=get_available_balance(target),
            reason=reason,
            created_by=created_by,
        )
        carried += 1

    db.commit()
    return {"carried": carried, "skipped": skipped, "from_year": from_year, "to_year": to_year}


def add_ledger_entry(
    db: Session,
    *,
    balance: LeaveBalance,
    transaction_type: str,
    amount: Decimal,
    balance_after: Decimal,
    leave_request_id: int | None = None,
    reason: str | None = None,
    created_by: int | None = None,
) -> LeaveBalanceLedger:
    entry = LeaveBalanceLedger(
        employee_id=balance.employee_id,
        leave_type_id=balance.leave_type_id,
        leave_balance_id=balance.id,
        leave_request_id=leave_request_id,
        year=balance.year,
        transaction_type=transaction_type,
        amount=amount,
        balance_after=balance_after,
        reason=reason,
        created_by=created_by,
    )
    db.add(entry)
    return entry


def allocate_leave_balance(
    db: Session, employee_id: int, leave_type_id: int, year: int, days: Decimal
) -> LeaveBalance:
    balance = get_leave_balance(db, employee_id, leave_type_id, year)
    if balance:
        previous_available = get_available_balance(balance)
        balance.allocated = days
    else:
        previous_available = Decimal("0")
        balance = LeaveBalance(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            year=year,
            allocated=days,
        )
        db.add(balance)
        db.flush()
    add_ledger_entry(
        db,
        balance=balance,
        transaction_type="allocation_adjustment",
        amount=days - previous_available,
        balance_after=get_available_balance(balance),
        reason="Leave balance allocation",
    )
    db.commit()
    db.refresh(balance)
    return balance


def calculate_leave_days(from_date: date, to_date: date, is_half_day: bool) -> Decimal:
    if to_date < from_date:
        raise ValueError("Leave end date cannot be before start date")
    if is_half_day:
        return Decimal("0.5")
    delta = (to_date - from_date).days + 1
    return Decimal(str(delta))


def has_overlapping_leave(
    db: Session,
    employee_id: int,
    from_date: date,
    to_date: date,
    exclude_request_id: int | None = None,
) -> bool:
    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.deleted_at.is_(None),
        LeaveRequest.status.in_(["Pending", "Approved"]),
        LeaveRequest.from_date <= to_date,
        LeaveRequest.to_date >= from_date,
    )
    if exclude_request_id:
        query = query.filter(LeaveRequest.id != exclude_request_id)
    return db.query(query.exists()).scalar()


def create_leave_request(db: Session, employee_id: int, data: dict) -> LeaveRequest:
    from_date = data["from_date"]
    to_date = data["to_date"]
    days = calculate_leave_days(from_date, to_date, data.get("is_half_day", False))

    if has_overlapping_leave(db, employee_id, from_date, to_date):
        raise ValueError("Leave dates overlap an existing pending or approved request")

    # Check balance
    year = from_date.year
    balance = get_leave_balance(db, employee_id, data["leave_type_id"], year)
    if not balance:
        raise ValueError("No leave balance allocated for this leave type and year")

    available = get_available_balance(balance)
    if available < days:
        raise ValueError(f"Insufficient leave balance. Available: {available}, Requested: {days}")

    employee = db.query(Employee).filter(Employee.id == employee_id, Employee.deleted_at.is_(None)).first()
    company_id = employee.branch.company_id if employee and employee.branch else None

    request = LeaveRequest(
        company_id=company_id,
        employee_id=employee_id,
        days_count=days,
        **{k: v for k, v in data.items() if k != "days_count"},
    )
    db.add(request)

    # Update pending balance
    balance.pending = balance.pending + days
    db.flush()
    add_ledger_entry(
        db,
        balance=balance,
        transaction_type="request_pending",
        amount=-days,
        balance_after=get_available_balance(balance),
        leave_request_id=request.id,
        reason="Leave request submitted",
    )

    db.commit()
    db.refresh(request)
    return request


def approve_leave_request(
    db: Session, request_id: int, status: str, reviewer_id: int, remarks: str = None
) -> Optional[LeaveRequest]:
    from datetime import datetime, timezone
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.deleted_at.is_(None),
    ).first()
    if not request or request.status != "Pending":
        return None

    old_status = request.status
    request.status = status
    request.reviewed_by = reviewer_id
    request.reviewed_at = datetime.now(timezone.utc)
    request.review_remarks = remarks

    # Update balance
    year = request.from_date.year
    balance = get_leave_balance(db, request.employee_id, request.leave_type_id, year)
    if balance:
        balance.pending = max(Decimal("0"), balance.pending - request.days_count)
        if status == "Approved":
            balance.used = balance.used + request.days_count
            transaction_type = "request_approved"
            amount = Decimal("0")
            reason = "Leave request approved"
        else:
            transaction_type = "request_rejected"
            amount = request.days_count
            reason = "Leave request rejected"
        add_ledger_entry(
            db,
            balance=balance,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=get_available_balance(balance),
            leave_request_id=request.id,
            reason=reason,
            created_by=reviewer_id,
        )

    db.commit()
    db.refresh(request)
    return request


def cancel_leave_request(db: Session, request_id: int, actor_id: int | None = None) -> Optional[LeaveRequest]:
    request = db.query(LeaveRequest).filter(
        LeaveRequest.id == request_id,
        LeaveRequest.deleted_at.is_(None),
    ).first()
    if not request or request.status != "Pending":
        return None

    request.status = "Cancelled"
    balance = get_leave_balance(db, request.employee_id, request.leave_type_id, request.from_date.year)
    if balance:
        balance.pending = max(Decimal("0"), balance.pending - request.days_count)
        add_ledger_entry(
            db,
            balance=balance,
            transaction_type="request_cancelled",
            amount=request.days_count,
            balance_after=get_available_balance(balance),
            leave_request_id=request.id,
            reason="Leave request cancelled",
            created_by=actor_id,
        )
    db.commit()
    db.refresh(request)
    return request


def get_leave_ledger(
    db: Session,
    *,
    employee_id: int,
    leave_type_id: Optional[int] = None,
    year: Optional[int] = None,
) -> List[LeaveBalanceLedger]:
    query = db.query(LeaveBalanceLedger).filter(LeaveBalanceLedger.employee_id == employee_id)
    if leave_type_id:
        query = query.filter(LeaveBalanceLedger.leave_type_id == leave_type_id)
    if year:
        query = query.filter(LeaveBalanceLedger.year == year)
    return query.order_by(LeaveBalanceLedger.created_at.desc(), LeaveBalanceLedger.id.desc()).all()


def get_leave_requests(
    db: Session,
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    company_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[LeaveRequest], int]:
    query = (
        db.query(LeaveRequest)
        .join(Employee, LeaveRequest.employee_id == Employee.id)
        .filter(LeaveRequest.deleted_at.is_(None), Employee.deleted_at.is_(None))
    )
    if company_id:
        query = query.filter(LeaveRequest.company_id == company_id)
    if employee_id:
        query = query.filter(LeaveRequest.employee_id == employee_id)
    if status:
        query = query.filter(LeaveRequest.status == status)
    total = query.count()
    items = query.order_by(LeaveRequest.applied_at.desc()).offset(skip).limit(limit).all()
    return items, total
