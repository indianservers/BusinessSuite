import json
from datetime import date
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import AppSetting, CustomView, Sale, User, Warehouse
from app.services.audit_service import record_audit
from app.utils.decorators import permission_required

FILTERS = ("date_from", "date_to", "warehouse_id", "status")


def _validate(values):
    result = {key:str(values.get(key) or "") for key in FILTERS}
    try:
        for key in ("date_from", "date_to"):
            if result[key]: date.fromisoformat(result[key])
        if result["warehouse_id"]: int(result["warehouse_id"])
        if result["date_from"] and result["date_to"] and result["date_from"] > result["date_to"]: raise ValueError()
    except (ValueError, TypeError): abort(400, "Invalid report date range or warehouse")
    return result


def sales_summary_rows():
    selected = None
    values = request.args
    if request.args.get("view_id"):
        selected = CustomView.query.filter_by(id=request.args.get("view_id", type=int), entity_type="reports").first_or_404()
        try: values = json.loads(selected.filters_json or "{}")
        except (ValueError, TypeError): abort(400, "Saved report filters are invalid")
        if not isinstance(values, dict) or values.get("_report", "sales-summary") != "sales-summary": abort(400, "Choose a Sales Summary view")
    filters = _validate(values)
    query = Sale.query.filter(Sale.status.notin_(["Draft", "Cancelled"]))
    scope = AppSetting.query.filter_by(key=f"reports.warehouses.{current_user.id}").first()
    allowed = None
    if scope:
        try:
            allowed = json.loads(scope.value)
            if not isinstance(allowed, list) or any(type(value) is not int or value <= 0 for value in allowed): raise ValueError()
        except (ValueError, TypeError): abort(403, "Invalid warehouse access configuration")
        query = query.filter(Sale.warehouse_id.in_(allowed))
    if filters["date_from"]: query = query.filter(Sale.invoice_date >= date.fromisoformat(filters["date_from"]))
    if filters["date_to"]: query = query.filter(Sale.invoice_date <= date.fromisoformat(filters["date_to"]))
    if filters["warehouse_id"]: query = query.filter(Sale.warehouse_id == int(filters["warehouse_id"]))
    if filters["status"]: query = query.filter(Sale.status == filters["status"])
    # Retain existing explicit customer/branch filters for unsaved reports.
    if not selected and request.args.get("customer_id"): query = query.filter(Sale.customer_id == request.args["customer_id"])
    if not selected and request.args.get("branch_id"):
        query = query.join(Warehouse).filter(Warehouse.branch_id == request.args["branch_id"])
    rows = [{"Invoice":s.invoice_no,"Date":s.invoice_date,"Customer":s.customer.name,"Warehouse":s.warehouse.name if s.warehouse else "", "Branch":s.warehouse.branch.name if s.warehouse and s.warehouse.branch else "", "Total":s.grand_total,"Paid":s.paid_amount,"Balance":s.balance_amount} for s in query.order_by(Sale.invoice_date.desc(),Sale.id).all()]
    return rows, filters, selected, allowed


def register_shared_report_routes(bp):
    @bp.route("/sales-summary/views", methods=["POST"])
    @login_required
    @permission_required("reports", "edit")
    def edit_shared_report_view():
        filters = _validate(request.form)
        name = request.form.get("name", "").strip()
        if not name or len(name) > 120: abort(400, "A view name of at most 120 characters is required")
        filters["_report"] = "sales-summary"
        view = CustomView(entity_type="reports",name=name,filters_json=json.dumps(filters),created_by=current_user.id)
        db.session.add(view);db.session.flush()
        record_audit("Shared View Saved", "Reports", view.id, new_data=filters)
        db.session.commit()
        return redirect(url_for("reports.sales_summary",view_id=view.id))

    @bp.route("/access", methods=["GET", "POST"])
    @login_required
    @permission_required("settings", "edit")
    def configure_report_access():
        if request.method == "POST":
            user = db.session.get(User, request.form.get("user_id", type=int))
            if not user: abort(400, "Choose a valid user")
            try: ids = sorted({int(value) for value in request.form.getlist("warehouse_ids")})
            except ValueError: abort(400, "Invalid warehouse")
            if any(not db.session.get(Warehouse, value) for value in ids): abort(400, "Invalid warehouse")
            row = AppSetting.query.filter_by(key=f"reports.warehouses.{user.id}").first()
            if not row: row = AppSetting(key=f"reports.warehouses.{user.id}");db.session.add(row)
            row.value = json.dumps(ids)
            record_audit("Warehouse Access Changed", "Reports", user.id, new_data={"warehouse_ids":ids})
            db.session.commit();flash("Report access saved. Only selected warehouses are visible in Sales Summary and its exports.","success")
        return render_template("reports/access.html",title="Sales report warehouse access",users=User.query.all(),warehouses=Warehouse.query.all(),scopes=AppSetting.query.filter(AppSetting.key.like("reports.warehouses.%")).all())
