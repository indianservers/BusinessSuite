"""Company catalog taxonomy, stored in the existing versioned policy table."""
import hashlib
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from sqlalchemy import func
from app.shared.models import ServicePolicy
from app.apps.srm.models import SRMProduct
from app.apps.srm.services.commercial import tenant

class Node(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalized_name(cls, value):
        value = " ".join(value.split())
        if not value or ">" in value:
            raise ValueError("Use a category name without >")
        return value

class Category(Node):
    children: list[Node] = Field(default_factory=list, max_length=100)

class Taxonomy(BaseModel):
    version: int = Field(ge=0)
    categories: list[Category] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        ids, names = set(), set()
        for node in self.categories:
            if node.name.casefold() in names:
                raise ValueError("Category names must be unique")
            names.add(node.name.casefold())
            child_names = set()
            for child in [node, *node.children]:
                if child.id in ids:
                    raise ValueError("Category and subcategory IDs must be unique")
                ids.add(child.id)
                if child is not node:
                    if child.name.casefold() in child_names:
                        raise ValueError("Subcategory names must be unique within the category")
                    child_names.add(child.name.casefold())
        return self

def policy(db, user, lock=False):
    q = db.query(ServicePolicy).filter_by(scope_key=f"catalog-categories:{tenant(user)}", organization_id=tenant(user), kind="catalog_categories")
    return (q.with_for_update().populate_existing() if lock else q).first()

def options(db, user):
    row = policy(db, user)
    tree = (row.values_json or {}).get("categories", []) if row else []
    # Existing names become selectable choices without changing any product.
    known = {n["name"] for n in tree}
    for (name,) in db.query(SRMProduct.category_name).filter(func.coalesce(SRMProduct.organization_id,1)==tenant(user), SRMProduct.deleted_at.is_(None)).distinct():
        if name and name not in known:
            tree = [*tree, {"id":"legacy-"+hashlib.sha256(name.encode()).hexdigest()[:24], "name":name, "children":[]}]
            known.add(name)
    return {"version":row.version if row else 0, "categories":tree}

def flatten(tree):
    return {child["id"]: (node["name"] if child is node else node["name"]+" > "+child["name"]) for node in tree for child in [node,*node.get("children",[])]}

def selection(db, user, ids):
    from app.models.company import Company
    db.query(Company).filter_by(id=tenant(user)).with_for_update().first()
    tree = options(db,user)["categories"]
    labels = flatten(tree)
    if any(i not in labels for i in ids):
        raise HTTPException(422,"Select existing categories and subcategories; reload the choices")
    parents = {child["id"]:node["id"] for node in tree for child in node.get("children",[])}
    normalized = list(dict.fromkeys([*ids, *(parents[i] for i in ids if i in parents)]))
    return normalized, [labels[i] for i in normalized]

def save(db, user, data):
    from app.models.company import Company
    # Lock the existing company even on the first save to serialize taxonomy creation.
    db.query(Company).filter_by(id=tenant(user)).with_for_update().first()
    row = policy(db,user,True)
    if data.version != (row.version if row else 0):
        raise HTTPException(409,"Categories changed. Reload before saving")
    old = options(db,user)["categories"]
    new = [n.model_dump() for n in data.categories]
    new_labels = flatten(new)
    legacy_ids = {n["name"]:n["id"] for n in old}
    products = db.query(SRMProduct).filter(func.coalesce(SRMProduct.organization_id,1)==tenant(user),SRMProduct.deleted_at.is_(None)).all()
    for product in products:
        meta = product.metadata_json or {}
        ids = meta.get("catalog_category_ids")
        if ids is None:
            ids = [legacy_ids[product.category_name]] if product.category_name in legacy_ids else []
        if any(i not in new_labels for i in ids):
            raise HTTPException(409,"Remove categories or subcategories from assigned items before deleting them")
        if ids:
            labels = [new_labels[i] for i in ids]
            product.metadata_json = {**meta,"catalog_category_ids":ids,"catalog_categories":labels}
            product.category_name = labels[0].split(" > ")[0]
    if row is None:
        row = ServicePolicy(scope_key=f"catalog-categories:{tenant(user)}",organization_id=tenant(user),module_key="*",kind="catalog_categories",version=0,updated_by=user.id)
        db.add(row)
    row.values_json={"categories":new};row.version+=1;row.updated_by=user.id
    db.flush()
    return {"version":row.version,"categories":new}
