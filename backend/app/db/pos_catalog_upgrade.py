"""Move shared catalog references onto the existing POS master, retaining history."""
import sqlalchemy as sa


def upgrade(op):
    connection = op.get_bind()
    metadata = sa.MetaData()
    pos = sa.Table("srm_products", metadata, autoload_with=connection)
    details = sa.Table("shared_catalog_details", metadata, autoload_with=connection)
    links = sa.Table("shared_catalog_links", metadata, autoload_with=connection)
    mappings = {"product": {}, "service": {}}
    pos_rows = {(row.organization_id or 1, row.sku): dict(row._mapping) for row in connection.execute(sa.select(pos))}
    detail_rows = {(kind, row._mapping[kind + "_id"]): row._mapping for row in connection.execute(sa.select(details)) for kind in mappings if row._mapping[kind + "_id"] is not None}
    for kind, table_name in (("product", "crm_products"), ("service", "crm_services")):
        legacy = sa.Table(table_name, metadata, autoload_with=connection)
        for result in connection.execute(sa.select(legacy)):
            row = result._mapping
            organization = row["organization_id"] or 1
            code = (row.get("sku") or row.get("product_code")) if kind == "product" else row.get("service_code")
            code = code or f"LEGACY-{kind.upper()}-{row['id']}"
            existing = pos_rows.get((organization, code))
            if existing and (existing["product_type"] == "service") != (kind == "service"):
                # A code can identify only one offering in POS. Preserve both offerings.
                code = f"{code[:55]}-{kind.upper()}-{row['id']}"
                existing = pos_rows.get((organization, code))
                if existing:
                    raise RuntimeError(f"Resolve catalog code conflict {code} before migration")
            detail = detail_rows.get((kind, row["id"]))
            images = list(detail["images"] or []) if detail else ([row["image_url"]] if row.get("image_url") else [])
            attributes = {**((existing or {}).get("metadata_json") or {})}
            attributes.setdefault("currency", row.get("currency") or "INR")
            if kind == "service":
                attributes.setdefault("billing_type", row.get("billing_type") or "fixed")
            attributes["images"] = list(dict.fromkeys([*attributes.get("images", []), *images]))
            if existing:
                connection.execute(pos.update().where(pos.c.id == existing["id"]).values(metadata_json=attributes))
                existing["metadata_json"] = attributes
                ident = existing["id"]
            else:
                price = (row.get("list_price") if row.get("list_price") is not None else row.get("unit_price")) if kind == "product" else row.get("default_rate")
                values = dict(organization_id=organization, sku=code, item_name=row["name"], description=row.get("description"), product_type="service" if kind == "service" else "stock", category_name=row.get("category"), unit_code=detail["unit"] if detail else (row.get("unit_of_measure") or "unit"), gst_rate=row.get("tax_rate") or 0, sales_rate=price or 0, mrp=price or 0, purchase_rate=row.get("cost_price") or row.get("default_cost") or 0, current_quantity=0, average_cost=0, reorder_level=0, min_stock=0, max_stock=0, track_inventory=kind != "service", batch_tracking=False, serial_tracking=False, expiry_tracking=False, active=row.get("active", True), deleted_at=row.get("deleted_at"), created_by=row.get("created_by_user_id"), metadata_json=attributes)
                ident = connection.execute(pos.insert().values(**values)).inserted_primary_key[0]
                pos_rows[(organization, code)] = {**values, "id": ident}
            mappings[kind][row["id"]] = ident

    # Remove old constraints before changing IDs, then enforce the POS foreign keys.
    convention = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
    inspector = sa.inspect(connection)
    referenced = [details, links]
    for name in ("crm_deal_products", "crm_price_book_items", "crm_quotation_items"):
        if inspector.has_table(name):
            referenced.append(sa.Table(name, metadata, autoload_with=connection))
    for table in referenced:
        foreign_keys = [fk for fk in sa.inspect(connection).get_foreign_keys(table.name) if fk["referred_table"] in {"crm_products", "crm_services"}]
        with op.batch_alter_table(table.name, naming_convention=convention) as batch:
            for fk in foreign_keys:
                name = fk["name"] or f"fk_{table.name}_{fk['constrained_columns'][0]}_{fk['referred_table']}"
                batch.drop_constraint(name, type_="foreignkey")
        for kind, mapping in mappings.items():
            if kind + "_id" not in {fk["constrained_columns"][0] for fk in foreign_keys}:
                continue
            column = table.c[kind + "_id"]
            for old_id in mapping:
                connection.execute(table.update().where(column == old_id).values({column.name: -old_id}))
            for old_id, new_id in mapping.items():
                connection.execute(table.update().where(column == -old_id).values({column.name: new_id}))
        with op.batch_alter_table(table.name) as batch:
            for fk in foreign_keys:
                field = fk["constrained_columns"][0]
                batch.create_foreign_key(f"fk_{table.name}_{field}_pos", "srm_products", [field], ["id"], ondelete=fk.get("options", {}).get("ondelete", "RESTRICT"))

    deals = sa.Table("crm_deals", metadata, autoload_with=connection)
    for result in connection.execute(sa.select(deals.c.id, deals.c.catalog_items)):
        if result.catalog_items is not None:
            lines = [{**line, "item_id": mappings[line["kind"]].get(line["item_id"], line["item_id"])} for line in result.catalog_items]
            connection.execute(deals.update().where(deals.c.id == result.id).values(catalog_items=lines))


def downgrade():
    raise RuntimeError("Restore the pre-migration backup to return to separate catalog masters")
