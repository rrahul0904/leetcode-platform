# Local Docker Release

## Scope

The Docker release packages every currently implemented Rigor component: the Next.js web application, FastAPI API, PostgreSQL 18 with pgvector and trigram search, idempotent migrations, taxonomy seeding, and Valkey. It does **not** represent unimplemented milestones—authentication, secure code/SQL execution, Temporal workflows, AI evaluation, payments, or the complete reviewed question bank—as finished.

## Start

On a managed network that intercepts TLS, export the organization root certificate as the build-only secret `.docker-build-ca.pem`. This file is ignored by Git, mounted only during dependency resolution, and is not copied into either final image. On this development machine the certificate is exported from the macOS System keychain:

```bash
security find-certificate -a -c Zscaler -p /Library/Keychains/System.keychain > .docker-build-ca.pem
```

On a network without interception, point the same secret at the organization-approved/public CA bundle. Do not disable TLS verification.

```bash
docker compose up --build -d
docker compose ps
```

The local published surfaces are:

- Web: `http://localhost:3001`
- API: `http://localhost:8002`
- PostgreSQL: `localhost:5434`
- Valkey: `localhost:6381`

`migrate` and `seed` are one-shot services. The API waits for both before starting. Images run as non-root users with dropped Linux capabilities, read-only filesystems, bounded temporary storage, and `no-new-privileges`.

## Stop and inspect

```bash
docker compose logs --tail=200 web api migrate seed
docker compose down
```

`docker compose down` preserves the database volume. Removing the volume deletes local Rigor database data and should be an explicit action.

## Registry publication

The images are tagged locally as `rigor-web:0.1.0-local` and `rigor-api:0.1.0-local`. Pushing them requires a chosen registry namespace and credentials. For AWS, the images will be retagged to ECR, scanned, assigned immutable digests, signed, and deployed through Terraform and GitHub OIDC rather than pushed manually from a developer laptop.
