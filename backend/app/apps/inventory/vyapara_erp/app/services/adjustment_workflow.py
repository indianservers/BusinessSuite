from datetime import date, datetime
from decimal import InvalidOperation
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import AdjustmentReview, AppSetting, Product, StockAdjustment, StockAdjustmentItem, Warehouse
from app.services.audit_service import record_audit
from app.services.numbering_service import next_number
from app.services.stock_service import apply_stock_adjustment
from app.utils.decorators import permission_required
from app.utils.helpers import qty, money

POLICY_KEY = "inventory.adjustments_require_evidence"
MAX_EVIDENCE = 2 * 1024 * 1024


def evidence_required():
    setting = AppSetting.query.filter_by(key=POLICY_KEY).first()
    return bool(setting and setting.value == "true")


def _post(adjustment):
    for item in adjustment.items.order_by(StockAdjustmentItem.product_id):
        apply_stock_adjustment(item.product_id, adjustment.warehouse_id, item.qty_in, item.qty_out, item.rate, adjustment.id, adjustment.adjustment_no, adjustment.reason)


def adjustment_form(adjustment_types):
    if request.method == "POST":
        try:
            warehouse = db.session.get(Warehouse, int(request.form["warehouse_id"]))
            if not warehouse or not warehouse.status:
                raise ValueError("An active warehouse is required")
            if not request.form.get("reason", "").strip() or len(request.form["reason"].strip()) > 100:
                raise ValueError("An adjustment reason of at most 100 characters is required")
            lines = []
            fields = [request.form.getlist(name) for name in ("product_id[]", "qty_in[]", "qty_out[]", "rate[]")]
            if len({len(values) for values in fields}) != 1:
                raise ValueError("Adjustment lines are incomplete")
            for pid, incoming, outgoing, rate in zip(*fields):
                if not pid: continue
                product = db.session.get(Product, int(pid))
                qi, qo, cost = qty(incoming or 0), qty(outgoing or 0), money(rate or 0)
                if not product or not product.is_active or not product.track_inventory or any(not x.is_finite() or x < 0 for x in (qi, qo, cost)) or (qi > 0) == (qo > 0):
                    raise ValueError("Each stock line needs an active stocked product, one positive direction and a nonnegative rate")
                lines.append((product.id, qi, qo, cost))
            if not lines: raise ValueError("At least one adjustment line is required")
            adjustment = StockAdjustment(adjustment_no=request.form.get("adjustment_no") or next_number("stock_adjustment"), adjustment_date=date.fromisoformat(request.form["adjustment_date"]), warehouse_id=warehouse.id, adjustment_type=request.form.get("adjustment_type") or "Other", reason=request.form["reason"].strip(), created_by=current_user.id)
            db.session.add(adjustment); db.session.flush()
            for pid, qi, qo, cost in lines:
                db.session.add(StockAdjustmentItem(adjustment_id=adjustment.id, product_id=pid, qty_in=qi, qty_out=qo, rate=cost))
            db.session.flush()
            pending = evidence_required()
            if pending:
                db.session.add(AdjustmentReview(adjustment_id=adjustment.id, status="Pending"))
            else:
                _post(adjustment)
            record_audit("Submitted" if pending else "Stock Adjustment", "StockAdjustment", adjustment.id, new_data={"adjustment_no":adjustment.adjustment_no, "warehouse_id":warehouse.id, "evidence_required":pending})
            db.session.commit()
            if pending:
                flash("Adjustment saved pending approval. Supporting evidence is required before posting; stock has not changed.", "success")
                return redirect(url_for("stock.adjustment_review", id=adjustment.id))
            flash("Stock adjusted.", "success")
            return redirect(url_for("stock.ledger"))
        except IntegrityError:
            db.session.rollback()
            flash("The adjustment number already exists or a linked record changed. Refresh before submitting again.", "danger")
        except (ValueError, KeyError, InvalidOperation, HTTPException) as exc:
            db.session.rollback()
            flash(getattr(exc, "description", str(exc)), "danger")
    return render_template("stock/adjustment.html", title="Stock Adjustment", products=Product.query.all(), warehouses=Warehouse.query.all(), adjustment_no=next_number("stock_adjustment"), today=date.today(), adjustment_types=adjustment_types, require_evidence=evidence_required(), pending_reviews=AdjustmentReview.query.order_by(AdjustmentReview.adjustment_id.desc()).limit(100).all())


def register_adjustment_routes(bp):
    @bp.route("/adjustments/policy", methods=["POST"])
    @login_required
    @permission_required("settings", "edit")
    def adjustment_policy():
        row = AppSetting.query.filter_by(key=POLICY_KEY).first()
        if not row: row = AppSetting(key=POLICY_KEY); db.session.add(row)
        row.value = "true" if request.form.get("require_evidence") == "on" else "false"
        record_audit("Policy Changed", "StockAdjustment", new_data={"require_evidence":row.value})
        db.session.commit()
        return redirect(url_for("stock.adjustments"))

    @bp.route("/adjustments/<int:id>")
    @login_required
    def adjustment_review(id):
        review = AdjustmentReview.query.get_or_404(id)
        return render_template("stock/adjustment_review.html", title=f"Adjustment {review.adjustment.adjustment_no}", review=review)

    @bp.route("/adjustments/<int:id>/evidence", methods=["POST"])
    @login_required
    def adjustment_evidence_upload(id):
        review = AdjustmentReview.query.filter_by(adjustment_id=id).with_for_update().first_or_404()
        if review.status != "Pending": abort(409, "Posted evidence cannot be replaced")
        if review.adjustment.created_by != current_user.id and not current_user.has_permission("inventory", "approve"): abort(403)
        upload = request.files.get("evidence")
        if not upload or not upload.filename:
            flash("Choose a supporting evidence file", "danger")
            return redirect(url_for("stock.adjustment_review", id=id))
        data = upload.read(MAX_EVIDENCE + 1)
        suffix = Path(upload.filename).suffix.lower()
        valid = bool(data) and len(data) <= MAX_EVIDENCE
        mime = {".pdf":"application/pdf", ".png":"image/png", ".csv":"text/csv"}.get(suffix)
        if suffix == ".pdf": valid = valid and data.startswith(b"%PDF-")
        elif suffix == ".png": valid = valid and data.startswith(b"\x89PNG\r\n\x1a\n")
        elif suffix == ".csv":
            try: valid = valid and b"\x00" not in data and bool(data.decode("utf-8-sig").strip())
            except UnicodeDecodeError: valid = False
        else: valid = False
        if not valid:
            flash("Evidence must be a valid PDF, PNG or UTF-8 CSV, at most 2 MB. No attachment was saved.", "danger")
            return redirect(url_for("stock.adjustment_review", id=id))
        review.evidence, review.evidence_name, review.evidence_mime = data, secure_filename(upload.filename), mime
        review.evidence_sha256, review.uploaded_by = sha256(data).hexdigest(), current_user.id
        record_audit("Evidence Uploaded", "StockAdjustment", id, new_data={"name":review.evidence_name,"sha256":review.evidence_sha256})
        db.session.commit()
        return redirect(url_for("stock.adjustment_review", id=id))

    @bp.route("/adjustments/<int:id>/evidence")
    @login_required
    def adjustment_evidence_download(id):
        review = AdjustmentReview.query.get_or_404(id)
        if not review.evidence: abort(404)
        if sha256(review.evidence).hexdigest() != review.evidence_sha256: abort(409, "Evidence checksum mismatch")
        return send_file(BytesIO(review.evidence), mimetype=review.evidence_mime, as_attachment=True, download_name=review.evidence_name)

    @bp.route("/adjustments/<int:id>/approve", methods=["POST"])
    @login_required
    @permission_required("inventory", "approve")
    def adjustment_approve(id):
        review = AdjustmentReview.query.filter_by(adjustment_id=id).populate_existing().with_for_update().first_or_404()
        if review.status != "Pending": abort(409, "Adjustment already posted")
        if not review.evidence:
            flash("Supporting evidence is required before approval. No stock posted.", "danger")
            return redirect(url_for("stock.adjustment_review", id=id))
        try:
            _post(review.adjustment)
            review.status, review.approved_by, review.approved_at = "Posted", current_user.id, datetime.utcnow()
            record_audit("Approved and Posted", "StockAdjustment", id, new_data={"evidence_sha256":review.evidence_sha256})
            db.session.commit()
            flash("Adjustment approved and posted once.", "success")
        except HTTPException as exc:
            db.session.rollback(); flash(exc.description, "danger")
        return redirect(url_for("stock.adjustment_review", id=id))
