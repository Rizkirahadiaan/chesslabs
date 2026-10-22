from sqlalchemy import select
from .models import License


def locked_license(db, license_id):
    # Semua perubahan entitlement dan perangkat diserialisasi melalui baris induk.
    return db.scalar(select(License).where(License.id == license_id).with_for_update())


def list_rows(db, model, page, size, sort="created_at", descending=True, conditions=()):
    from sqlalchemy import func
    query = select(model).where(*conditions)
    count = db.scalar(select(func.count()).select_from(model).where(*conditions))
    column = getattr(model, sort)
    rows = db.scalars(query.order_by(column.desc() if descending else column.asc(), model.id)
                      .offset((page-1)*size).limit(size)).all()
    return {"items": rows, "total": count, "page": page, "size": size}
