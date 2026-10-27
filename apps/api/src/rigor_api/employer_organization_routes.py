"""Self-service employer organization and reviewer onboarding.

Organization selection is verified against a live membership on *every* request
by principal_auth. This router never trusts a caller-supplied organization role.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from .auth import authenticated_principal
from .database import DatabaseEngine, principal_transaction
from .persistence import audit_event
from .schemas import AuthenticatedPrincipal

router = APIRouter(prefix="/api/v1/employer/organizations", tags=["employer-organizations"])
Principal = Annotated[AuthenticatedPrincipal, Depends(authenticated_principal)]
_USER = "NULLIF(current_setting('rigor.user_id',true),'')::uuid"
_ORG = "NULLIF(current_setting('rigor.organization_id',true),'')::uuid"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewOrganization(StrictModel):
    name: str = Field(min_length=3, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,99}$")


class OrganizationView(StrictModel):
    id: UUID
    name: str
    slug: str
    membership_role: str


class MemberAdd(StrictModel):
    user_id: UUID
    role: Literal["admin", "recruiter", "interviewer", "reviewer"]


class MemberView(StrictModel):
    user_id: UUID
    role: str
    status: str


@router.get("", response_model=list[OrganizationView])
def list_my_employer_organizations(
    engine: DatabaseEngine, principal: Principal,
) -> list[OrganizationView]:
    with principal_transaction(engine, principal) as conn:
        records = conn.execute(
            text(
                f"""SELECT o.id, o.name, o.slug, m.role_slug AS membership_role
                    FROM organizations o
                    JOIN organization_memberships m ON o.id=m.organization_id
                    WHERE m.user_id={_USER} AND m.status='active'
                    ORDER BY o.name LIMIT 50"""
            )
        ).mappings().all()
        return [OrganizationView.model_validate(dict(row)) for row in records]


@router.post("", response_model=OrganizationView, status_code=201)
def create_employer_organization(
    payload: NewOrganization, engine: DatabaseEngine, principal: Principal,
) -> OrganizationView:
    with principal_transaction(engine, principal) as conn:
        # Serialize per-user organization creation and avoid unlimited free
        # tenant generation. Owner invites only known provisioned accounts.
        actor = conn.execute(text(f"SELECT {_USER}")).scalar_one()
        conn.execute(text("SELECT id FROM users WHERE id=:user FOR UPDATE"), {"user": actor})
        owned_count = int(
            conn.execute(
                text(
                    f"""SELECT count(*) FROM organization_memberships
                        WHERE user_id={_USER} AND role_slug='owner'
                          AND status='active'"""
                )
            ).scalar_one()
        )
        if owned_count >= 3:
            raise HTTPException(status_code=429, detail="Organization creation quota reached")
        existing = conn.execute(
            text("SELECT 1 FROM organizations WHERE slug=:slug"),
            {"slug": payload.slug},
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="Organization slug already in use")
        row = conn.execute(
            text(
                """INSERT INTO organizations (name, slug)
                   VALUES (:name, :slug) RETURNING id, name, slug"""
            ),
            {"name": payload.name.strip(), "slug": payload.slug},
        ).mappings().one()
        conn.execute(
            text(
                """INSERT INTO organization_memberships
                     (organization_id, user_id, role_slug, status)
                   VALUES (:organization, :user, 'owner', 'active')"""
            ),
            {"organization": row["id"], "user": actor},
        )
        audit_event(
            conn, principal, actor, action="employer.organization_create",
            resource_type="organization", resource_id=str(row["id"]),
            details={"slug": row["slug"]},
        )
        return OrganizationView(
            id=row["id"], name=row["name"], slug=row["slug"], membership_role="owner"
        )


def _require_owner_admin(conn, organization_id: UUID) -> UUID:
    active_org = conn.execute(text(f"SELECT {_ORG}")).scalar_one_or_none()
    if active_org != organization_id:
        raise HTTPException(status_code=403, detail="Select this employer workspace first")
    row = conn.execute(
        text(
            f"""SELECT role_slug FROM organization_memberships
                WHERE organization_id={_ORG} AND user_id={_USER} AND status='active'"""
        )
    ).scalar_one_or_none()
    if row not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Organization administrator required")
    return conn.execute(text(f"SELECT {_USER}")).scalar_one()


@router.get("/{organization_id}/members", response_model=list[MemberView])
def list_employer_members(
    organization_id: UUID, engine: DatabaseEngine, principal: Principal,
) -> list[MemberView]:
    with principal_transaction(engine, principal) as conn:
        _require_owner_admin(conn, organization_id)
        rows = conn.execute(
            text(
                """SELECT user_id, role_slug AS role, status
                   FROM organization_memberships
                   WHERE organization_id=:org ORDER BY created_at LIMIT 200"""
            ),
            {"org": organization_id},
        ).mappings().all()
        return [MemberView.model_validate(dict(row)) for row in rows]


@router.post(
    "/{organization_id}/members", response_model=MemberView, status_code=201,
)
def add_employer_member(
    organization_id: UUID, payload: MemberAdd,
    engine: DatabaseEngine, principal: Principal,
) -> MemberView:
    with principal_transaction(engine, principal) as conn:
        actor = _require_owner_admin(conn, organization_id)
        if actor == payload.user_id:
            raise HTTPException(status_code=409, detail="Cannot change your own organization role")
        recipient = conn.execute(
            text("SELECT 1 FROM users WHERE id=:user AND status='active'"),
            {"user": payload.user_id},
        ).scalar_one_or_none()
        if recipient is None:
            raise HTTPException(status_code=404, detail="Registered user not found")
        inserted = conn.execute(
            text(
                """INSERT INTO organization_memberships
                     (organization_id, user_id, role_slug, status)
                   VALUES (:org, :user, :role, 'active')
                   ON CONFLICT (organization_id, user_id) DO NOTHING
                   RETURNING user_id, role_slug AS role, status"""
            ),
            {"org": organization_id, "user": payload.user_id, "role": payload.role},
        ).mappings().one_or_none()
        if inserted is None:
            raise HTTPException(status_code=409, detail="User already belongs to this organization")
        audit_event(
            conn, principal, actor, action="employer.member_create",
            resource_type="organization_membership", resource_id=str(organization_id),
            details={"user_id": str(payload.user_id), "role": payload.role},
        )
        return MemberView.model_validate(dict(inserted))
