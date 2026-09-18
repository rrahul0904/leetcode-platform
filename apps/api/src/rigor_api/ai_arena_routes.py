from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from .ai_arena_domain import rating_delta, score_arena_submission, tier_for_rating
from .ai_arena_provider import generate_arena_code
from .auth import require_permissions
from .database import DatabaseEngine, principal_transaction
from .practice import (
    PracticeSessionNotFoundError,
    published_question_payload,
    question_runtime,
    question_tests,
    starter_source,
)
from .schemas import AuthenticatedPrincipal, SubmissionRuntime

router = APIRouter(prefix="/api/v1/arena", tags=["ai-arena"])


class ArenaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PublicArenaChallenge(ArenaModel):
    slug: str
    title: str
    difficulty: str
    problem_statement: str
    constraints: list[str]
    public_examples: list[object]
    starter_code: str
    public_test_count: int = Field(ge=0)
    hidden_test_count: int = Field(ge=1)


class ArenaGenerationCreate(ArenaModel):
    challenge_slug: str = Field(min_length=1, max_length=180)
    prompt: str = Field(min_length=1, max_length=4000)


class ArenaGenerationView(ArenaModel):
    id: UUID
    challenge_slug: str
    prompt: str
    generated_code: str
    provider: str
    model: str


class ArenaFinalizeInput(ArenaModel):
    generation_id: UUID
    submission_id: UUID


class ArenaScoreView(ArenaModel):
    correctness: int = Field(ge=0, le=70)
    performance: int = Field(ge=0, le=15)
    quality: int = Field(ge=0, le=10)
    efficiency: int = Field(ge=0, le=5)
    total: int = Field(ge=0, le=100)


class ArenaResultView(ArenaModel):
    id: UUID
    generation_id: UUID
    submission_id: UUID
    challenge_slug: str
    score: ArenaScoreView
    rating_delta: int = Field(ge=0)
    rating_after: int = Field(ge=0)
    tier: str


class ArenaProfileView(ArenaModel):
    display_name: str
    rating: int = Field(ge=0)
    tier: str
    solved_count: int = Field(ge=0)
    submission_count: int = Field(ge=0)


class ArenaLeaderboardRow(ArenaProfileView):
    rank: int = Field(gt=0)


ArenaReadPrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("catalog:read")),
]
ArenaWritePrincipal = Annotated[
    AuthenticatedPrincipal,
    Depends(require_permissions("submission:create")),
]
IdempotencyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=160),
]

_CURRENT_USER_SQL = "NULLIF(current_setting('rigor.user_id', true), '')::uuid"


def _content(payload: dict[str, Any]) -> dict[str, Any]:
    structured = payload.get("structured_content")
    return cast(dict[str, Any], structured) if isinstance(structured, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _difficulty(content: dict[str, Any]) -> str:
    candidates: list[object] = [
        content.get("difficulty"),
        (content.get("metadata") or {}).get("difficulty")
        if isinstance(content.get("metadata"), dict)
        else None,
        (content.get("classification") or {}).get("difficulty")
        if isinstance(content.get("classification"), dict)
        else None,
    ]
    for value in candidates:
        if isinstance(value, str) and value.casefold() in {"easy", "medium", "hard"}:
            return value.casefold()
    return "medium"


def _challenge(payload: dict[str, Any]) -> PublicArenaChallenge:
    if question_runtime(payload) is not SubmissionRuntime.python:
        raise ValueError("AI Arena currently supports Python questions only")
    tests = question_tests(payload, public_only=False)
    hidden_count = sum(1 for item in tests if item.get("visibility") != "public")
    if hidden_count < 1:
        raise ValueError("AI Arena requires at least one hidden test")
    content = _content(payload)
    statement = (
        content.get("problem_statement")
        or content.get("description")
        or content.get("prompt")
        or ""
    )
    examples = content.get("public_examples")
    if not isinstance(examples, list):
        examples = content.get("examples")
    public_examples = cast(list[object], examples) if isinstance(examples, list) else []
    constraints = content.get("public_constraints")
    if not isinstance(constraints, list):
        constraints = content.get("constraints")
    return PublicArenaChallenge(
        slug=str(payload["slug"]),
        title=str(payload["title"]),
        difficulty=_difficulty(content),
        problem_statement=str(statement),
        constraints=_strings(constraints),
        public_examples=public_examples,
        starter_code=starter_source(payload, SubmissionRuntime.python),
        public_test_count=sum(1 for item in tests if item.get("visibility") == "public"),
        hidden_test_count=hidden_count,
    )


def _published_arena_question(connection: Connection, slug: str) -> dict[str, Any]:
    try:
        payload = published_question_payload(connection, slug)
        _challenge(payload)
        return payload
    except (PracticeSessionNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="AI Arena challenge not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Question is not AI Arena executable") from exc


def _generation_view(connection: Connection, row: Any) -> ArenaGenerationView:
    slug = connection.execute(
        text(
            """
            SELECT q.slug
            FROM question_versions v
            JOIN questions q ON q.id=v.question_id
            WHERE v.id=:question_version_id
            """
        ),
        {"question_version_id": row["question_version_id"]},
    ).scalar_one()
    return ArenaGenerationView(
        id=UUID(str(row["id"])),
        challenge_slug=str(slug),
        prompt=str(row["prompt"]),
        generated_code=str(row["generated_code"]),
        provider=str(row["provider"]),
        model=str(row["model"]),
    )


def _ensure_profile(connection: Connection) -> None:
    connection.execute(
        text(
            f"""
            INSERT INTO ai_arena_profiles (user_id)
            VALUES ({_CURRENT_USER_SQL})
            ON CONFLICT (user_id) DO NOTHING
            """
        )
    )


def _profile(connection: Connection, display_name: str) -> ArenaProfileView:
    _ensure_profile(connection)
    row = connection.execute(
        text(
            f"""
            SELECT rating, tier, solved_count, submission_count
            FROM ai_arena_profiles
            WHERE user_id={_CURRENT_USER_SQL}
            """
        )
    ).mappings().one()
    return ArenaProfileView(
        display_name=display_name,
        rating=int(row["rating"]),
        tier=str(row["tier"]),
        solved_count=int(row["solved_count"]),
        submission_count=int(row["submission_count"]),
    )


def _stored_result(
    connection: Connection,
    *,
    generation_id: UUID | None = None,
    submission_id: UUID | None = None,
) -> ArenaResultView | None:
    if generation_id is None and submission_id is None:
        return None
    clauses = [f"r.user_id={_CURRENT_USER_SQL}"]
    parameters: dict[str, object] = {}
    if generation_id is not None:
        clauses.append("r.generation_id=:generation_id")
        parameters["generation_id"] = generation_id
    if submission_id is not None:
        clauses.append("r.submission_id=:submission_id")
        parameters["submission_id"] = submission_id
    row = connection.execute(
        text(
            f"""
            SELECT r.id, r.generation_id, r.submission_id,
                   r.correctness_score, r.performance_score,
                   r.quality_score, r.efficiency_score, r.total_score,
                   r.rating_delta, r.rating_after, p.tier, q.slug
            FROM ai_arena_results r
            JOIN ai_arena_profiles p ON p.user_id=r.user_id
            JOIN ai_arena_generations g ON g.id=r.generation_id
            JOIN question_versions v ON v.id=g.question_version_id
            JOIN questions q ON q.id=v.question_id
            WHERE {" AND ".join(clauses)}
            ORDER BY r.created_at DESC
            LIMIT 1
            """
        ),
        parameters,
    ).mappings().one_or_none()
    if row is None:
        return None
    return ArenaResultView(
        id=UUID(str(row["id"])),
        generation_id=UUID(str(row["generation_id"])),
        submission_id=UUID(str(row["submission_id"])),
        challenge_slug=str(row["slug"]),
        score=ArenaScoreView(
            correctness=int(row["correctness_score"]),
            performance=int(row["performance_score"]),
            quality=int(row["quality_score"]),
            efficiency=int(row["efficiency_score"]),
            total=int(row["total_score"]),
        ),
        rating_delta=int(row["rating_delta"]),
        rating_after=int(row["rating_after"]),
        tier=str(row["tier"]),
    )


@router.get("/challenges", response_model=list[PublicArenaChallenge])
def list_arena_challenges(
    _principal: ArenaReadPrincipal,
    engine: DatabaseEngine,
) -> list[PublicArenaChallenge]:
    with engine.connect() as connection:
        slugs = connection.execute(
            text(
                """
                SELECT q.slug
                FROM questions q
                JOIN question_versions v ON v.id=q.current_published_version_id
                WHERE q.archived_at IS NULL
                  AND v.state='published'::content_state
                ORDER BY v.created_at DESC, q.slug
                LIMIT 250
                """
            )
        ).scalars().all()
        challenges: list[PublicArenaChallenge] = []
        for slug in slugs:
            try:
                challenges.append(_challenge(published_question_payload(connection, str(slug))))
            except (PracticeSessionNotFoundError, ValueError, Exception):
                continue
            if len(challenges) >= 50:
                break
        return challenges


@router.post("/generate", response_model=ArenaGenerationView, status_code=201)
def generate_arena_candidate(
    request: ArenaGenerationCreate,
    principal: ArenaWritePrincipal,
    engine: DatabaseEngine,
    idempotency_key: IdempotencyHeader,
) -> ArenaGenerationView:
    with principal_transaction(engine, principal) as connection:
        existing = connection.execute(
            text(
                f"""
                SELECT id, question_version_id, prompt, generated_code, provider, model
                FROM ai_arena_generations
                WHERE user_id={_CURRENT_USER_SQL}
                  AND idempotency_key=:idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().one_or_none()
        if existing is not None:
            return _generation_view(connection, existing)
        question = _published_arena_question(connection, request.challenge_slug)

    generation = generate_arena_code(question, request.prompt)

    with principal_transaction(engine, principal) as connection:
        existing = connection.execute(
            text(
                f"""
                SELECT id, question_version_id, prompt, generated_code, provider, model
                FROM ai_arena_generations
                WHERE user_id={_CURRENT_USER_SQL}
                  AND idempotency_key=:idempotency_key
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().one_or_none()
        if existing is not None:
            return _generation_view(connection, existing)
        fresh_question = _published_arena_question(connection, request.challenge_slug)
        if UUID(str(fresh_question["question_version_id"])) != UUID(
            str(question["question_version_id"])
        ):
            raise HTTPException(
                status_code=409,
                detail="Challenge version changed during generation; generate again.",
            )
        row = connection.execute(
            text(
                f"""
                INSERT INTO ai_arena_generations (
                    user_id, question_version_id, prompt, generated_code,
                    provider, model, idempotency_key
                ) VALUES (
                    {_CURRENT_USER_SQL}, :question_version_id, :prompt, :generated_code,
                    :provider, :model, :idempotency_key
                )
                RETURNING id, question_version_id, prompt, generated_code, provider, model
                """
            ),
            {
                "question_version_id": fresh_question["question_version_id"],
                "prompt": request.prompt.strip(),
                "generated_code": generation.code,
                "provider": generation.provider,
                "model": generation.model,
                "idempotency_key": idempotency_key,
            },
        ).mappings().one()
        return _generation_view(connection, row)


@router.post("/finalize", response_model=ArenaResultView)
def finalize_arena_submission(
    request: ArenaFinalizeInput,
    principal: ArenaWritePrincipal,
    engine: DatabaseEngine,
) -> ArenaResultView:
    with principal_transaction(engine, principal) as connection:
        existing = _stored_result(
            connection,
            generation_id=request.generation_id,
            submission_id=request.submission_id,
        )
        if existing is not None:
            return existing

        row = connection.execute(
            text(
                f"""
                SELECT g.id AS generation_id, g.question_version_id, g.prompt,
                       g.generated_code, q.slug, v.structured_content,
                       s.id AS submission_id, s.submitted_source,
                       sr.public_results, sr.hidden_total, sr.hidden_passed,
                       sr.runtime_ms, se.code_quality_score
                FROM ai_arena_generations g
                JOIN question_versions v ON v.id=g.question_version_id
                JOIN questions q ON q.id=v.question_id
                JOIN submissions s ON s.id=:submission_id
                JOIN submission_results sr ON sr.submission_id=s.id
                JOIN submission_evaluations se ON se.submission_id=s.id
                WHERE g.id=:generation_id
                  AND g.user_id={_CURRENT_USER_SQL}
                  AND s.candidate_id={_CURRENT_USER_SQL}
                  AND s.question_version_id=g.question_version_id
                """
            ),
            {
                "generation_id": request.generation_id,
                "submission_id": request.submission_id,
            },
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Completed Arena generation/submission pair not found.",
            )
        if str(row["generated_code"]) != str(row["submitted_source"]):
            raise HTTPException(
                status_code=409,
                detail="Arena-generated code must be submitted without modification.",
            )

        public_results = (
            cast(list[object], row["public_results"])
            if isinstance(row["public_results"], list)
            else []
        )
        public_dicts = [
            cast(dict[str, object], item)
            for item in public_results
            if isinstance(item, dict)
        ]
        public_total = len(public_dicts)
        public_passed = sum(1 for item in public_dicts if bool(item.get("passed")))
        content = (
            cast(dict[str, Any], row["structured_content"])
            if isinstance(row["structured_content"], dict)
            else {}
        )
        score = score_arena_submission(
            public_passed=public_passed,
            public_total=public_total,
            hidden_passed=int(row["hidden_passed"]),
            hidden_total=int(row["hidden_total"]),
            runtime_ms=(
                int(row["runtime_ms"]) if row["runtime_ms"] is not None else None
            ),
            code_quality_score=float(row["code_quality_score"]),
            prompt=str(row["prompt"]),
        )

        previous_best = connection.execute(
            text(
                f"""
                SELECT max(r.total_score)
                FROM ai_arena_results r
                JOIN ai_arena_generations previous
                  ON previous.id=r.generation_id
                WHERE r.user_id={_CURRENT_USER_SQL}
                  AND previous.question_version_id=:question_version_id
                """
            ),
            {"question_version_id": row["question_version_id"]},
        ).scalar_one()
        previous_best_score = int(previous_best) if previous_best is not None else None
        first_solve = score.total >= 70 and (
            previous_best_score is None or previous_best_score < 70
        )
        delta = rating_delta(
            difficulty=_difficulty(content),
            score=score.total,
            previous_best_score=previous_best_score,
            first_solve=first_solve,
        )

        _ensure_profile(connection)
        profile = connection.execute(
            text(
                f"""
                SELECT rating, solved_count, submission_count
                FROM ai_arena_profiles
                WHERE user_id={_CURRENT_USER_SQL}
                FOR UPDATE
                """
            )
        ).mappings().one()
        rating_after = int(profile["rating"]) + delta
        tier = tier_for_rating(rating_after)
        connection.execute(
            text(
                f"""
                UPDATE ai_arena_profiles
                SET rating=:rating,
                    tier=:tier,
                    solved_count=solved_count + :solved_increment,
                    submission_count=submission_count + 1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE user_id={_CURRENT_USER_SQL}
                """
            ),
            {
                "rating": rating_after,
                "tier": tier,
                "solved_increment": 1 if first_solve else 0,
            },
        )
        result = connection.execute(
            text(
                f"""
                INSERT INTO ai_arena_results (
                    user_id, generation_id, submission_id,
                    correctness_score, performance_score, quality_score,
                    efficiency_score, total_score, rating_delta, rating_after
                ) VALUES (
                    {_CURRENT_USER_SQL}, :generation_id, :submission_id,
                    :correctness, :performance, :quality,
                    :efficiency, :total, :rating_delta, :rating_after
                )
                RETURNING id
                """
            ),
            {
                "generation_id": request.generation_id,
                "submission_id": request.submission_id,
                "correctness": score.correctness,
                "performance": score.performance,
                "quality": score.quality,
                "efficiency": score.efficiency,
                "total": score.total,
                "rating_delta": delta,
                "rating_after": rating_after,
            },
        ).scalar_one()

        return ArenaResultView(
            id=UUID(str(result)),
            generation_id=request.generation_id,
            submission_id=request.submission_id,
            challenge_slug=str(row["slug"]),
            score=ArenaScoreView(
                correctness=score.correctness,
                performance=score.performance,
                quality=score.quality,
                efficiency=score.efficiency,
                total=score.total,
            ),
            rating_delta=delta,
            rating_after=rating_after,
            tier=tier,
        )


@router.get("/me", response_model=ArenaProfileView)
def get_arena_profile(
    principal: ArenaReadPrincipal,
    engine: DatabaseEngine,
) -> ArenaProfileView:
    with principal_transaction(engine, principal) as connection:
        return _profile(connection, principal.display_name)


@router.get("/leaderboard", response_model=list[ArenaLeaderboardRow])
def get_arena_leaderboard(
    _principal: ArenaReadPrincipal,
    engine: DatabaseEngine,
) -> list[ArenaLeaderboardRow]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT u.display_name, p.rating, p.tier,
                       p.solved_count, p.submission_count
                FROM ai_arena_profiles p
                JOIN users u ON u.id=p.user_id
                WHERE u.status='active'
                ORDER BY p.rating DESC, p.solved_count DESC,
                         p.submission_count ASC, u.display_name ASC
                LIMIT 100
                """
            )
        ).mappings().all()
    return [
        ArenaLeaderboardRow(
            rank=index,
            display_name=str(row["display_name"]),
            rating=int(row["rating"]),
            tier=str(row["tier"]),
            solved_count=int(row["solved_count"]),
            submission_count=int(row["submission_count"]),
        )
        for index, row in enumerate(rows, start=1)
    ]
