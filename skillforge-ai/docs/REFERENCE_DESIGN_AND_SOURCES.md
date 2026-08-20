# SkillForge Reference Design and Source-Material Contract

## Visual reference

The supplied screen recording is the interaction and composition benchmark for the public SkillForge experience.

Reuse the reference's design principles, not its branding or palette:

- editorial-first hierarchy;
- slim, quiet global header;
- narrow centered hero copy;
- serif-led display typography;
- generous vertical whitespace;
- restrained controls and separators;
- minimal cardification;
- a large projected Earth as a dominant homepage object;
- slow real geographic rotation;
- pointer/touch drag;
- reduced-motion support;
- truthful activity markers only;
- responsive globe sizing rather than clipping or replacing the globe on mobile.

SkillForge intentionally uses its own deep-ink/periwinkle/ivory palette instead of reproducing the reference colors.

## Globe implementation

`frontend/components/rotating-globe.tsx` uses:

- `world-atlas` world geometry;
- `d3-geo` `geoOrthographic` projection;
- `topojson-client` geometry conversion;
- projected graticules and coast/country geometry;
- common projection for geography and activity markers;
- horizon clipping;
- roughly minute-scale calm auto-rotation;
- horizontal/vertical drag;
- a pause before auto-rotation resumes;
- `prefers-reduced-motion` support.

Activity is read from `GET /api/activity/globe`. The API reads only coarse aggregate rollups from `globe_activity_rollups`. When no observed aggregate activity exists, the UI shows a truthful no-activity state. It must never fabricate cities or user locations.

## Additional source materials

The earlier uploaded repositories are part of the SkillForge source inventory. Their intended use is captured in `content-manifest/ADDITIONAL_SOURCE_REGISTRY.json` and stored in Supabase through `content_sources`.

The governing rules are:

- `HOSTABLE_LICENSED`: may enrich solution variants with attribution after compatibility review;
- `EXTERNAL_REFERENCE_ONLY`: use identifiers, titles, URLs, company/frequency/recency observations and derived metadata only;
- `RIGHTS_REVIEW_REQUIRED`: quarantine content until publishing rights are confirmed;
- `REJECTED_PROPRIETARY`: do not ingest into the learner-facing catalog.

Company-wise datasets feed canonical company observations rather than copied problem text. System-design and competitive-programming archives can guide coverage and taxonomy without automatically becoming publishable content.
