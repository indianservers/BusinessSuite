from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import BOMItem, BillOfMaterials, InventoryLedger, ManufacturingOrder, Product, Unit, Warehouse
from app.services.numbering_service import next_number
from app.services.stock_service import add_inventory_entry, _locked_product
from app.services.audit_service import record_audit
from app.utils.helpers import qty, money

bp = Blueprint("manufacturing", __name__, url_prefix="/manufacturing")


@bp.route("/bom/")
@login_required
def bom_index():
    boms = BillOfMaterials.query.order_by(BillOfMaterials.id.desc()).all()
    return render_template("manufacturing/bom_index.html", title="Bills of Materials", boms=boms)


@bp.route("/bom/create", methods=["GET", "POST"])
@login_required
def bom_create():
    return _bom_form(BillOfMaterials(), "Create BOM")


@bp.route("/bom/<int:id>/edit", methods=["GET", "POST"])
@login_required
def bom_edit(id):
    return _bom_form(BillOfMaterials.query.get_or_404(id), "Edit BOM")


@bp.route("/orders/")
@login_required
def order_index():
    orders = ManufacturingOrder.query.order_by(ManufacturingOrder.id.desc()).all()
    return render_template("manufacturing/order_index.html", title="Manufacturing Orders", orders=orders)


@bp.route("/orders/create", methods=["GET", "POST"])
@login_required
def order_create():
    return _order_form(ManufacturingOrder(mo_no=next_number("manufacturing_order"),
                                          planned_date=date.today(), planned_qty=1, produced_qty=0),
                       "Create Manufacturing Order")


@bp.route("/orders/<int:id>/edit", methods=["GET", "POST"])
@login_required
def order_edit(id):
    order = ManufacturingOrder.query.filter_by(id=id).with_for_update().first_or_404()
    if order.status != "Draft":
        abort(409, "Only unposted draft manufacturing orders can be amended")
    return _order_form(order, "Edit Manufacturing Order")


def _order_form(order, title):
    if request.method == "POST":
        try:
            planned = qty(request.form["planned_qty"])
            if not planned.is_finite() or planned <= 0:
                raise ValueError("Planned quantity must be positive")
            bom = db.session.get(BillOfMaterials, int(request.form["bom_id"]))
            warehouse = db.session.get(Warehouse, int(request.form["warehouse_id"]))
            if not bom or not bom.is_active or not warehouse or not warehouse.status:
                raise ValueError("Select an active BOM and valid warehouse")
            if order.id and db.session.query(db.func.count()).select_from(
                    InventoryLedger).filter_by(
                    reference_type="ManufacturingOrder", reference_id=order.id).scalar():
                raise ValueError("Posted manufacturing movements cannot be amended")
            old = {"planned_qty":str(order.planned_qty),"bom_id":order.bom_id,"warehouse_id":order.warehouse_id}
            action = "Edit" if order.id else "Create"
            order.mo_no = request.form.get("mo_no") or order.mo_no
            order.bom_id, order.warehouse_id = bom.id, warehouse.id
            order.planned_qty, order.produced_qty, order.status = planned, 0, "Draft"
            order.planned_date = date.fromisoformat(request.form["planned_date"]) if request.form.get("planned_date") else date.today()
            order.notes = request.form.get("notes")
            if not order.created_by: order.created_by = current_user.id
            db.session.add(order); db.session.flush()
            record_audit(action, "ManufacturingOrder", order.id, old_data=old if action=="Edit" else None,
                         new_data={"mo_no":order.mo_no,"planned_qty":str(planned),"bom_id":bom.id,"warehouse_id":warehouse.id})
            db.session.commit()
            flash("Manufacturing order saved; no stock posted.", "success")
            return redirect(url_for("manufacturing.order_index"))
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "danger")
    return render_template("manufacturing/order_form.html", title=title, order=order,
        boms=BillOfMaterials.query.filter_by(is_active=True).order_by(BillOfMaterials.name).all(),
        warehouses=Warehouse.query.order_by(Warehouse.name).all())


@bp.route("/orders/<int:id>/complete", methods=["POST"])
@login_required
def order_complete(id):
    order = ManufacturingOrder.query.filter_by(id=id).populate_existing().with_for_update().first_or_404()
    if order.status in {"Completed", "Cancelled"}:
        flash("Only an unfinished manufacturing order can be completed.", "danger")
        return redirect(url_for("manufacturing.order_index"))
    try:
        produced_qty = qty(request.form.get("produced_qty") or order.produced_qty or order.planned_qty)
        yield_qty = qty(order.bom.yield_qty)
        if not produced_qty.is_finite() or produced_qty <= 0 or not yield_qty.is_finite() or yield_qty <= 0:
            raise ValueError("Production quantity and BOM yield must be positive")
        if produced_qty > qty(order.planned_qty):
            raise ValueError("Production quantity cannot exceed the amended planned quantity")
        order.produced_qty = produced_qty
        component_cost = money(0)
        for item in sorted(order.bom.items, key=lambda line: line.component_id):
            component = _locked_product(item.component_id)
            required = qty(qty(item.quantity) * produced_qty / yield_qty * (1 + money(item.waste_pct) / 100))
            if not required.is_finite() or required <= 0:
                raise ValueError("BOM component quantities must be positive")
            rate = component.average_cost or component.purchase_price or 0
            add_inventory_entry(component, order.warehouse_id, "Manufacturing Issue", "ManufacturingOrder", order.id, order.mo_no, qty_out=required, rate=rate)
            component_cost += required * money(rate)
        finished_rate = money(component_cost / produced_qty)
        finished = _locked_product(order.bom.product_id)
        old_value = qty(finished.current_stock) * money(finished.average_cost)
        finished.average_cost = money((old_value + component_cost) / (qty(finished.current_stock) + produced_qty))
        add_inventory_entry(finished, order.warehouse_id, "Manufacturing Receipt", "ManufacturingOrder", order.id, order.mo_no, qty_in=produced_qty, rate=finished_rate)
        order.status = "Completed"
        order.completed_date = date.today()
        record_audit("Complete", "ManufacturingOrder", order.id, new_data={"produced_qty":str(produced_qty),"component_cost":str(component_cost)})
        db.session.commit()
        flash(f"Manufacturing order {order.mo_no} completed.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("manufacturing.order_index"))


def _bom_form(bom, title):
    if request.method == "POST":
        try:
            bom.product_id = request.form["product_id"]
            bom.name = request.form["name"]
            bom.yield_qty = request.form.get("yield_qty") or 1
            bom.version = request.form.get("version") or "1"
            bom.is_active = bool(request.form.get("is_active"))
            bom.notes = request.form.get("notes")
            db.session.add(bom)
            db.session.flush()
            BOMItem.query.filter_by(bom_id=bom.id).delete()
            for component_id, qty, unit_id, waste in zip(request.form.getlist("component_id[]"), request.form.getlist("quantity[]"), request.form.getlist("unit_id[]"), request.form.getlist("waste_pct[]")):
                if component_id:
                    db.session.add(BOMItem(bom_id=bom.id, component_id=component_id, quantity=qty or 0, unit_id=unit_id or None, waste_pct=waste or 0))
            db.session.commit()
            flash("BOM saved.", "success")
            return redirect(url_for("manufacturing.bom_index"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template(
        "manufacturing/bom_form.html",
        title=title,
        bom=bom,
        products=Product.query.order_by(Product.name).all(),
        units=Unit.query.order_by(Unit.name).all(),
    )
