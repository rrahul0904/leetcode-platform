# Identity and Authorization Model

Cognito subject identifiers map to internal users. Organization membership and application roles remain in PostgreSQL so entitlement and review separation cannot be changed solely through client-controlled claims.

Every request constructs an immutable principal containing subject, tenant, roles, permissions, authentication time, and correlation ID. Domain services require explicit permissions. Database sessions set tenant context transaction-locally; background workflows carry a signed internal principal reference rather than user tokens.

Technical and editorial approval require different users. Platform administrators may perform emergency overrides only through an explicit reason, step-up authentication policy, and immutable audit event; an override is visible in content provenance.

