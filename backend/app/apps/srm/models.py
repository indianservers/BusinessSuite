from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class SRMSalesOrder(Base):
    __tablename__ = "srm_sales_orders"
    __table_args__ = (UniqueConstraint("organization_id", "order_number", name="uq_srm_sales_order_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    order_number = Column(String(80), nullable=False, index=True)
    status = Column(String(40), default="draft", index=True)
    crm_deal_id = Column(Integer, nullable=True, index=True)
    crm_quote_id = Column(Integer, nullable=True, index=True)
    crm_company_id = Column(Integer, nullable=True, index=True)
    crm_contact_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approval_request_id = Column(Integer, nullable=True, index=True)
    title = Column(String(220), nullable=False)
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    expected_start_date = Column(Date, nullable=True)
    expected_end_date = Column(Date, nullable=True)
    terms = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    lines = relationship("SRMSalesOrderLine", back_populates="sales_order", cascade="all, delete-orphan")


class SRMSalesOrderLine(Base):
    __tablename__ = "srm_sales_order_lines"

    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    source_quote_line_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, nullable=True, index=True)
    item_code = Column(String(80), nullable=True, index=True)
    description = Column(Text)
    service_type = Column(String(80), default="service", index=True)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)
    pms_template_key = Column(String(80), nullable=True)
    metadata_json = Column(JSON)

    sales_order = relationship("SRMSalesOrder", back_populates="lines")


class SRMPOSSession(Base):
    __tablename__ = "srm_pos_sessions"
    __table_args__ = (UniqueConstraint("organization_id", "session_number", name="uq_srm_pos_session_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    session_number = Column(String(80), nullable=False, index=True)
    status = Column(String(40), default="open", index=True)
    branch = Column(String(160), default="Main Branch")
    register_name = Column(String(160), default="Main POS Register")
    cashier_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    opening_cash = Column(Numeric(14, 2), default=0)
    expected_cash = Column(Numeric(14, 2), default=0)
    counted_cash = Column(Numeric(14, 2), default=0)
    cash_variance = Column(Numeric(14, 2), default=0)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    closed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    cash_movements = relationship("SRMPOSCashMovement", back_populates="session", cascade="all, delete-orphan")
    closings = relationship("SRMPOSCashierClosing", back_populates="session", cascade="all, delete-orphan")


class SRMPOSCashMovement(Base):
    __tablename__ = "srm_pos_cash_movements"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("srm_pos_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_type = Column(String(40), default="cash_in", index=True)
    amount = Column(Numeric(14, 2), default=0)
    reason = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    session = relationship("SRMPOSSession", back_populates="cash_movements")


class SRMPOSCashierClosing(Base):
    __tablename__ = "srm_pos_cashier_closings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("srm_pos_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    opening_cash = Column(Numeric(14, 2), default=0)
    cash_sales = Column(Numeric(14, 2), default=0)
    cash_in = Column(Numeric(14, 2), default=0)
    cash_out = Column(Numeric(14, 2), default=0)
    expected_cash = Column(Numeric(14, 2), default=0)
    counted_cash = Column(Numeric(14, 2), default=0)
    variance = Column(Numeric(14, 2), default=0)
    notes = Column(Text)
    closed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    session = relationship("SRMPOSSession", back_populates="closings")


class SRMPOSHeldBill(Base):
    __tablename__ = "srm_pos_held_bills"
    __table_args__ = (UniqueConstraint("organization_id", "hold_number", name="uq_srm_pos_held_bill_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("srm_pos_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    hold_number = Column(String(80), nullable=False, index=True)
    status = Column(String(40), default="held", index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    customer_name = Column(String(220), nullable=True)
    notes = Column(Text)
    cart_json = Column(JSON, nullable=False)
    amount = Column(Numeric(14, 2), default=0)
    item_count = Column(Integer, default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recalled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    recalled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    session = relationship("SRMPOSSession")


class SRMPOSReturn(Base):
    __tablename__ = "srm_pos_returns"
    __table_args__ = (UniqueConstraint("organization_id", "return_number", name="uq_srm_pos_return_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    return_number = Column(String(80), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("srm_pos_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    customer_name = Column(String(220), nullable=True)
    status = Column(String(40), default="completed", index=True)
    refund_method = Column(String(60), default="cash", index=True)
    refund_status = Column(String(40), default="refunded", index=True)
    subtotal = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    refund_amount = Column(Numeric(14, 2), default=0)
    reason = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    sales_order = relationship("SRMSalesOrder")
    session = relationship("SRMPOSSession")
    lines = relationship("SRMPOSReturnLine", back_populates="return_doc", cascade="all, delete-orphan")


class SRMPOSReturnLine(Base):
    __tablename__ = "srm_pos_return_lines"

    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(Integer, ForeignKey("srm_pos_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_line_id = Column(Integer, ForeignKey("srm_sales_order_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    item_code = Column(String(80), nullable=True, index=True)
    description = Column(Text)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)
    condition = Column(String(60), default="sellable", index=True)
    restock = Column(Boolean, default=True, index=True)
    metadata_json = Column(JSON)

    return_doc = relationship("SRMPOSReturn", back_populates="lines")
    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")


class SRMProductCategory(Base):
    __tablename__ = "srm_product_categories"
    __table_args__ = (UniqueConstraint("organization_id", "category_code", name="uq_srm_product_category_org_code"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    parent_category_id = Column(Integer, ForeignKey("srm_product_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    category_code = Column(String(80), nullable=False, index=True)
    category_name = Column(String(180), nullable=False, index=True)
    description = Column(Text)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMWarehouse(Base):
    __tablename__ = "srm_warehouses"
    __table_args__ = (UniqueConstraint("organization_id", "warehouse_code", name="uq_srm_warehouse_org_code"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    warehouse_code = Column(String(80), nullable=False, index=True)
    warehouse_name = Column(String(180), nullable=False, index=True)
    branch = Column(String(160), nullable=True, index=True)
    address = Column(Text)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMProduct(Base):
    __tablename__ = "srm_products"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uq_srm_product_org_sku"),
        UniqueConstraint("organization_id", "barcode", name="uq_srm_product_org_barcode"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("srm_product_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    default_warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    sku = Column(String(80), nullable=False, index=True)
    item_name = Column(String(220), nullable=False, index=True)
    barcode = Column(String(120), nullable=True, index=True)
    description = Column(Text)
    product_type = Column(String(40), default="stock", index=True)
    category_name = Column(String(180), nullable=True, index=True)
    unit_code = Column(String(40), default="PCS", index=True)
    hsn_code = Column(String(30), nullable=True, index=True)
    gst_rate = Column(Numeric(6, 2), default=0)
    purchase_rate = Column(Numeric(14, 2), default=0)
    sales_rate = Column(Numeric(14, 2), default=0)
    mrp = Column(Numeric(14, 2), default=0)
    current_quantity = Column(Numeric(14, 3), default=0)
    average_cost = Column(Numeric(14, 4), default=0)
    reorder_level = Column(Numeric(14, 3), default=0)
    min_stock = Column(Numeric(14, 3), default=0)
    max_stock = Column(Numeric(14, 3), default=0)
    track_inventory = Column(Boolean, default=True, index=True)
    batch_tracking = Column(Boolean, default=False)
    serial_tracking = Column(Boolean, default=False)
    expiry_tracking = Column(Boolean, default=False)
    active = Column(Boolean, default=True, index=True)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    category = relationship("SRMProductCategory")
    default_warehouse = relationship("SRMWarehouse")


class SRMInventoryBalance(Base):
    __tablename__ = "srm_inventory_balances"
    __table_args__ = (UniqueConstraint("organization_id", "product_id", "warehouse_id", name="uq_srm_inventory_balance_org_product_warehouse"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Numeric(14, 3), default=0)
    average_cost = Column(Numeric(14, 4), default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")


class SRMInventoryMovement(Base):
    __tablename__ = "srm_inventory_movements"
    __table_args__ = (UniqueConstraint("organization_id", "movement_number", name="uq_srm_inventory_movement_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    movement_number = Column(String(80), nullable=False, index=True)
    movement_type = Column(String(40), default="opening_stock", index=True)
    movement_date = Column(Date, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity_in = Column(Numeric(14, 3), default=0)
    quantity_out = Column(Numeric(14, 3), default=0)
    rate = Column(Numeric(14, 4), default=0)
    value = Column(Numeric(14, 2), default=0)
    reference_number = Column(String(120), nullable=True, index=True)
    notes = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")


class SRMPurchaseOrder(Base):
    __tablename__ = "srm_purchase_orders"
    __table_args__ = (UniqueConstraint("organization_id", "po_number", name="uq_srm_purchase_order_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    po_number = Column(String(80), nullable=False, index=True)
    vendor_id = Column(Integer, nullable=True, index=True)
    vendor_name = Column(String(220), nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    order_date = Column(Date, nullable=False, index=True)
    expected_date = Column(Date, nullable=True, index=True)
    subtotal = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    lines = relationship("SRMPurchaseOrderLine", back_populates="purchase_order", cascade="all, delete-orphan")


class SRMPurchaseOrderLine(Base):
    __tablename__ = "srm_purchase_order_lines"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("srm_purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    item_code = Column(String(80), nullable=True, index=True)
    description = Column(Text)
    quantity = Column(Numeric(14, 3), default=1)
    received_quantity = Column(Numeric(14, 3), default=0)
    unit_price = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)
    metadata_json = Column(JSON)

    purchase_order = relationship("SRMPurchaseOrder", back_populates="lines")
    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")


class SRMGoodsReceipt(Base):
    __tablename__ = "srm_goods_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "grn_number", name="uq_srm_goods_receipt_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    grn_number = Column(String(80), nullable=False, index=True)
    purchase_order_id = Column(Integer, ForeignKey("srm_purchase_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_id = Column(Integer, nullable=True, index=True)
    vendor_name = Column(String(220), nullable=True, index=True)
    status = Column(String(40), default="posted", index=True)
    receipt_date = Column(Date, nullable=False, index=True)
    reference_number = Column(String(120), nullable=True, index=True)
    subtotal = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    purchase_order = relationship("SRMPurchaseOrder")
    lines = relationship("SRMGoodsReceiptLine", back_populates="goods_receipt", cascade="all, delete-orphan")


class SRMGoodsReceiptLine(Base):
    __tablename__ = "srm_goods_receipt_lines"

    id = Column(Integer, primary_key=True, index=True)
    goods_receipt_id = Column(Integer, ForeignKey("srm_goods_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_line_id = Column(Integer, ForeignKey("srm_purchase_order_lines.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    item_code = Column(String(80), nullable=True, index=True)
    description = Column(Text)
    quantity = Column(Numeric(14, 3), default=1)
    accepted_quantity = Column(Numeric(14, 3), default=1)
    rejected_quantity = Column(Numeric(14, 3), default=0)
    unit_price = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)
    metadata_json = Column(JSON)

    goods_receipt = relationship("SRMGoodsReceipt", back_populates="lines")
    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")


class SRMPriceList(Base):
    __tablename__ = "srm_price_lists"
    __table_args__ = (UniqueConstraint("organization_id", "price_list_code", name="uq_srm_price_list_org_code"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    price_list_code = Column(String(80), nullable=False, index=True)
    price_list_name = Column(String(180), nullable=False, index=True)
    channel = Column(String(80), default="retail", index=True)
    customer_type = Column(String(80), default="cash", index=True)
    currency = Column(String(10), default="INR")
    effective_from = Column(Date, nullable=True, index=True)
    effective_to = Column(Date, nullable=True, index=True)
    priority = Column(Integer, default=100, index=True)
    active = Column(Boolean, default=True, index=True)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    lines = relationship("SRMPriceListLine", back_populates="price_list", cascade="all, delete-orphan")


class SRMPriceListLine(Base):
    __tablename__ = "srm_price_list_lines"
    __table_args__ = (UniqueConstraint("price_list_id", "product_id", "min_quantity", name="uq_srm_price_list_line_product_break"),)

    id = Column(Integer, primary_key=True, index=True)
    price_list_id = Column(Integer, ForeignKey("srm_price_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(80), nullable=True, index=True)
    item_name = Column(String(220), nullable=True)
    min_quantity = Column(Numeric(14, 3), default=1)
    price = Column(Numeric(14, 2), nullable=False)
    discount_percent = Column(Numeric(6, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_inclusive = Column(Boolean, default=False)
    active = Column(Boolean, default=True, index=True)
    metadata_json = Column(JSON)

    price_list = relationship("SRMPriceList", back_populates="lines")
    product = relationship("SRMProduct")


class SRMInventoryBatch(Base):
    __tablename__ = "srm_inventory_batches"
    __table_args__ = (UniqueConstraint("organization_id", "product_id", "batch_number", name="uq_srm_inventory_batch_org_product_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_number = Column(String(120), nullable=False, index=True)
    manufacture_date = Column(Date, nullable=True, index=True)
    expiry_date = Column(Date, nullable=True, index=True)
    received_date = Column(Date, nullable=True, index=True)
    quantity = Column(Numeric(14, 3), default=0)
    available_quantity = Column(Numeric(14, 3), default=0)
    unit_cost = Column(Numeric(14, 4), default=0)
    status = Column(String(40), default="available", index=True)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")
    serials = relationship("SRMSerialNumber", back_populates="batch")


class SRMSerialNumber(Base):
    __tablename__ = "srm_serial_numbers"
    __table_args__ = (UniqueConstraint("organization_id", "serial_number", name="uq_srm_serial_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_id = Column(Integer, ForeignKey("srm_inventory_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    serial_number = Column(String(160), nullable=False, index=True)
    status = Column(String(40), default="available", index=True)
    received_date = Column(Date, nullable=True, index=True)
    sold_at = Column(DateTime(timezone=True), nullable=True)
    reference_number = Column(String(120), nullable=True, index=True)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("SRMProduct")
    warehouse = relationship("SRMWarehouse")
    batch = relationship("SRMInventoryBatch", back_populates="serials")


class SRMBillOfMaterial(Base):
    __tablename__ = "srm_bills_of_material"
    __table_args__ = (UniqueConstraint("organization_id", "bom_number", name="uq_srm_bom_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    bom_number = Column(String(80), nullable=False, index=True)
    bom_name = Column(String(180), nullable=False, index=True)
    finished_product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"), nullable=False, index=True)
    output_quantity = Column(Numeric(14, 3), default=1)
    status = Column(String(40), default="active", index=True)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    finished_product = relationship("SRMProduct", foreign_keys=[finished_product_id])
    components = relationship("SRMBOMComponent", back_populates="bom", cascade="all, delete-orphan")


class SRMBOMComponent(Base):
    __tablename__ = "srm_bom_components"

    id = Column(Integer, primary_key=True, index=True)
    bom_id = Column(Integer, ForeignKey("srm_bills_of_material.id", ondelete="CASCADE"), nullable=False, index=True)
    component_product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity = Column(Numeric(14, 3), default=1)
    scrap_percent = Column(Numeric(6, 2), default=0)
    unit_cost = Column(Numeric(14, 4), default=0)
    line_total = Column(Numeric(14, 2), default=0)
    metadata_json = Column(JSON)

    bom = relationship("SRMBillOfMaterial", back_populates="components")
    component_product = relationship("SRMProduct", foreign_keys=[component_product_id])
    warehouse = relationship("SRMWarehouse")


class SRMProductionOrder(Base):
    __tablename__ = "srm_production_orders"
    __table_args__ = (UniqueConstraint("organization_id", "production_number", name="uq_srm_production_order_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    production_number = Column(String(80), nullable=False, index=True)
    bom_id = Column(Integer, ForeignKey("srm_bills_of_material.id", ondelete="RESTRICT"), nullable=False, index=True)
    finished_product_id = Column(Integer, ForeignKey("srm_products.id", ondelete="RESTRICT"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("srm_warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    planned_quantity = Column(Numeric(14, 3), default=1)
    completed_quantity = Column(Numeric(14, 3), default=0)
    status = Column(String(40), default="planned", index=True)
    order_date = Column(Date, nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_component_cost = Column(Numeric(14, 2), default=0)
    notes = Column(Text)
    metadata_json = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    bom = relationship("SRMBillOfMaterial")
    finished_product = relationship("SRMProduct", foreign_keys=[finished_product_id])
    warehouse = relationship("SRMWarehouse")


class SRMContract(Base):
    __tablename__ = "srm_contracts"
    __table_args__ = (UniqueConstraint("organization_id", "contract_number", name="uq_srm_contract_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    contract_number = Column(String(80), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    title = Column(String(220), nullable=False)
    status = Column(String(40), default="draft", index=True)
    contract_type = Column(String(80), default="services")
    effective_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    contract_value = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="INR")
    signed_by_customer_at = Column(DateTime(timezone=True))
    signed_by_company_at = Column(DateTime(timezone=True))
    terms = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class SRMEngagement(Base):
    __tablename__ = "srm_engagements"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_number = Column(String(80), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    contract_id = Column(Integer, ForeignKey("srm_contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    crm_deal_id = Column(Integer, nullable=True, index=True)
    crm_quote_id = Column(Integer, nullable=True, index=True)
    pms_project_id = Column(Integer, nullable=True, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(220), nullable=False)
    status = Column(String(40), default="created", index=True)
    billing_type = Column(String(40), default="fixed_fee", index=True)
    budget_amount = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="INR")
    planned_start_date = Column(Date)
    planned_end_date = Column(Date)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))


class SRMEngagementLink(Base):
    __tablename__ = "srm_engagement_links"
    __table_args__ = (UniqueConstraint("engagement_id", "linked_module", "linked_entity_type", "linked_entity_id", name="uq_srm_engagement_link"),)

    id = Column(Integer, primary_key=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    linked_module = Column(String(80), nullable=False, index=True)
    linked_entity_type = Column(String(80), nullable=False, index=True)
    linked_entity_id = Column(Integer, nullable=False, index=True)
    label = Column(String(180))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SRMBillingPlan(Base):
    __tablename__ = "srm_billing_plans"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    billing_type = Column(String(40), default="fixed_fee", index=True)
    status = Column(String(40), default="draft", index=True)
    currency = Column(String(10), default="INR")
    total_amount = Column(Numeric(14, 2), default=0)
    recurrence_rule = Column(String(120))
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMBillingMilestone(Base):
    __tablename__ = "srm_billing_milestones"

    id = Column(Integer, primary_key=True, index=True)
    billing_plan_id = Column(Integer, ForeignKey("srm_billing_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(180), nullable=False)
    status = Column(String(40), default="pending", index=True)
    due_date = Column(Date, nullable=True, index=True)
    amount = Column(Numeric(14, 2), default=0)
    invoice_draft_id = Column(Integer, nullable=True, index=True)
    metadata_json = Column(JSON)


class SRMInvoiceDraft(Base):
    __tablename__ = "srm_invoice_drafts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    billing_plan_id = Column(Integer, ForeignKey("srm_billing_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    source_type = Column(String(60), nullable=False, index=True)
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMInvoice(Base):
    __tablename__ = "srm_invoices"
    __table_args__ = (UniqueConstraint("organization_id", "invoice_number", name="uq_srm_invoice_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    invoice_number = Column(String(80), nullable=False, index=True)
    invoice_draft_id = Column(Integer, ForeignKey("srm_invoice_drafts.id", ondelete="SET NULL"), nullable=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("srm_sales_orders.id", ondelete="SET NULL"), nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    issue_date = Column(Date, nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True))
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True))
    currency = Column(String(10), default="INR")
    subtotal = Column(Numeric(14, 2), default=0)
    discount_amount = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    total_amount = Column(Numeric(14, 2), default=0)
    paid_amount = Column(Numeric(14, 2), default=0)
    balance_amount = Column(Numeric(14, 2), default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True))

    lines = relationship("SRMInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")


class SRMInvoiceLine(Base):
    __tablename__ = "srm_invoice_lines"
    __table_args__ = (UniqueConstraint("source_type", "source_id", name="uq_srm_invoice_line_source"),)

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(60), nullable=True, index=True)
    source_id = Column(Integer, nullable=True, index=True)
    description = Column(Text, nullable=False)
    quantity = Column(Numeric(12, 2), default=1)
    unit_price = Column(Numeric(14, 2), default=0)
    tax_amount = Column(Numeric(14, 2), default=0)
    line_total = Column(Numeric(14, 2), default=0)

    invoice = relationship("SRMInvoice", back_populates="lines")


class SRMInvoiceHistory(Base):
    __tablename__ = "srm_invoice_history"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(40))
    to_status = Column(String(40), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMReceipt(Base):
    __tablename__ = "srm_receipts"
    __table_args__ = (UniqueConstraint("organization_id", "receipt_number", name="uq_srm_receipt_org_number"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    receipt_number = Column(String(80), nullable=False, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    status = Column(String(40), default="draft", index=True)
    receipt_date = Column(Date, nullable=True, index=True)
    payment_method = Column(String(60), default="bank_transfer")
    reference_number = Column(String(120), nullable=True)
    currency = Column(String(10), default="INR")
    amount = Column(Numeric(14, 2), default=0)
    unallocated_amount = Column(Numeric(14, 2), default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SRMReceiptAllocation(Base):
    __tablename__ = "srm_receipt_allocations"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("srm_receipts.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(14, 2), default=0)
    allocated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    allocated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SRMCollectionReminder(Base):
    __tablename__ = "srm_collection_reminders"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="CASCADE"), nullable=True, index=True)
    status = Column(String(40), default="queued", index=True)
    reminder_type = Column(String(60), default="email")
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMCustomerAging(Base):
    __tablename__ = "srm_customer_aging"
    __table_args__ = (UniqueConstraint("organization_id", "customer_id", name="uq_srm_customer_aging_org_customer"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    customer_id = Column(Integer, nullable=False, index=True)
    current_amount = Column(Numeric(14, 2), default=0)
    days_1_30 = Column(Numeric(14, 2), default=0)
    days_31_60 = Column(Numeric(14, 2), default=0)
    days_61_90 = Column(Numeric(14, 2), default=0)
    days_90_plus = Column(Numeric(14, 2), default=0)
    total_outstanding = Column(Numeric(14, 2), default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SRMProfitabilitySnapshot(Base):
    __tablename__ = "srm_profitability_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(Integer, nullable=True, index=True)
    quoted_amount = Column(Numeric(14, 2), default=0)
    order_amount = Column(Numeric(14, 2), default=0)
    contract_amount = Column(Numeric(14, 2), default=0)
    billing_amount = Column(Numeric(14, 2), default=0)
    invoiced_amount = Column(Numeric(14, 2), default=0)
    collected_amount = Column(Numeric(14, 2), default=0)
    outstanding_amount = Column(Numeric(14, 2), default=0)
    overdue_amount = Column(Numeric(14, 2), default=0)
    cost_amount = Column(Numeric(14, 2), default=0)
    gross_margin_amount = Column(Numeric(14, 2), default=0)
    gross_margin_percent = Column(Numeric(6, 2), default=0)
    cash_margin_amount = Column(Numeric(14, 2), default=0)
    status = Column(String(40), default="healthy", index=True)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMRevenueEvent(Base):
    __tablename__ = "srm_revenue_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    engagement_id = Column(Integer, ForeignKey("srm_engagements.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("srm_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    amount = Column(Numeric(14, 2), default=0)
    currency = Column(String(10), default="INR")
    recognized_on = Column(Date, nullable=True, index=True)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMAuditLog(Base):
    __tablename__ = "srm_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    before_json = Column(JSON)
    after_json = Column(JSON)
    ip_address = Column(String(80))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SRMSetting(Base):
    __tablename__ = "srm_settings"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_srm_setting_org_key"),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    key = Column(String(120), nullable=False, index=True)
    value_json = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
