"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Check, Clock3, Target } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { ErrorState, LoadingState } from "@/components/page-ui";
import {
  ApiError,
  type CandidateProfile,
  type CandidateProfileInput,
  getProfile,
  putProfile,
} from "@/lib/api";

const roleOptions = [
  "Senior backend engineer",
  "Staff engineer",
  "Principal engineer",
  "Data architect",
  "ML engineer",
  "AI infrastructure engineer",
];

const emptyProfile: CandidateProfileInput = {
  target_roles: [],
  target_companies: [],
  experience_level: "senior",
  preferred_programming_language: "python",
  weekly_study_hours: 6,
  interview_date: null,
  strong_areas: [],
  weak_areas: [],
  preparation_intensity: "focused",
};

function editableProfile(profile: CandidateProfile): CandidateProfileInput {
  return {
    target_roles: profile.target_roles,
    target_companies: profile.target_companies ?? [],
    experience_level: profile.experience_level,
    preferred_programming_language: profile.preferred_programming_language,
    weekly_study_hours: profile.weekly_study_hours,
    interview_date: profile.interview_date ?? null,
    strong_areas: profile.strong_areas ?? [],
    weak_areas: profile.weak_areas ?? [],
    preparation_intensity: profile.preparation_intensity,
  };
}

function splitList(value: string) {
  return [
    ...new Set(
      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];
}

function OnboardingForm({ initial }: { initial: CandidateProfile | undefined }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [profile, setProfile] = useState<CandidateProfileInput>(() =>
    initial ? editableProfile(initial) : emptyProfile,
  );
  const [companies, setCompanies] = useState(() =>
    (initial?.target_companies ?? []).join(", "),
  );
  const [strongAreas, setStrongAreas] = useState(() =>
    (initial?.strong_areas ?? []).join(", "),
  );
  const [weakAreas, setWeakAreas] = useState(() =>
    (initial?.weak_areas ?? []).join(", "),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleRole(role: string) {
    setProfile((current) => ({
      ...current,
      target_roles: current.target_roles.includes(role)
        ? current.target_roles.filter((item) => item !== role)
        : [...current.target_roles, role],
    }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (profile.target_roles.length === 0) {
      setError("Choose at least one target role.");
      return;
    }

    setSaving(true);
    try {
      const saved = await putProfile({
        ...profile,
        target_companies: splitList(companies),
        strong_areas: splitList(strongAreas),
        weak_areas: splitList(weakAreas),
      });
      queryClient.setQueryData(["candidate-profile"], saved);
      queryClient.setQueryData(["candidate-profile", "auth-gate"], saved);
      await queryClient.invalidateQueries({ queryKey: ["candidate-readiness"] });
      await queryClient.invalidateQueries({ queryKey: ["next-action"] });
      router.replace("/");
    } catch {
      setError("The profile could not be saved. Check each field and retry.");
      setSaving(false);
    }
  }

  return (
    <form className="onboarding-form" onSubmit={save}>
      <section className="onboarding-intro">
        <span className="eyebrow">
          {initial ? "EDIT CANDIDATE PROFILE" : "FIRST-LOGIN ONBOARDING"}
        </span>
        <h1>
          {initial
            ? "Keep the plan aligned with your target."
            : "Turn a target interview into a focused preparation plan."}
        </h1>
        <p>
          SkillsForge AI uses these fields to shape transparent learning sequences.
          Recommendations remain provisional until submission evidence exists.
        </p>
        <div>
          <span>
            <Target size={16} /> Role-directed
          </span>
          <span>
            <Clock3 size={16} /> Availability-bounded
          </span>
          <span>
            <CalendarDays size={16} /> Timeline-aware
          </span>
        </div>
      </section>
      <div className="onboarding-sections">
        <fieldset>
          <legend>01 · Target roles</legend>
          <p>Select one or more role families.</p>
          <div className="role-options">
            {roleOptions.map((role) => (
              <button
                type="button"
                className={profile.target_roles.includes(role) ? "selected" : ""}
                onClick={() => toggleRole(role)}
                key={role}
              >
                {profile.target_roles.includes(role) && <Check size={14} />}
                {role}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>02 · Experience and tools</legend>
          <div className="form-grid">
            <label>
              <span>Current level</span>
              <select
                value={profile.experience_level}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    experience_level: event.target
                      .value as CandidateProfileInput["experience_level"],
                  })
                }
              >
                <option value="mid">Mid-level</option>
                <option value="senior">Senior</option>
                <option value="staff">Staff</option>
                <option value="principal">Principal</option>
                <option value="manager">Engineering manager</option>
              </select>
            </label>
            <label>
              <span>Preferred practice language</span>
              <select
                value={profile.preferred_programming_language}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    preferred_programming_language: event.target
                      .value as CandidateProfileInput["preferred_programming_language"],
                  })
                }
              >
                <option value="python">Python</option>
                <option value="sql">SQL</option>
                <option value="mixed">Mixed Python + SQL</option>
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>03 · Time and intensity</legend>
          <div className="form-grid form-grid--three">
            <label>
              <span>Weekly study hours</span>
              <input
                type="number"
                min={1}
                max={40}
                value={profile.weekly_study_hours}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    weekly_study_hours: Number(event.target.value),
                  })
                }
              />
            </label>
            <label>
              <span>Interview date (optional)</span>
              <input
                type="date"
                value={profile.interview_date ?? ""}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    interview_date: event.target.value || null,
                  })
                }
              />
            </label>
            <label>
              <span>Preparation intensity</span>
              <select
                value={profile.preparation_intensity}
                onChange={(event) =>
                  setProfile({
                    ...profile,
                    preparation_intensity: event.target
                      .value as CandidateProfileInput["preparation_intensity"],
                  })
                }
              >
                <option value="steady">Steady</option>
                <option value="focused">Focused</option>
                <option value="intensive">Intensive</option>
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>04 · Target context</legend>
          <label>
            <span>Target companies or company types</span>
            <input
              value={companies}
              onChange={(event) => setCompanies(event.target.value)}
              placeholder="Example: AI lab, large marketplace, fintech platform"
            />
          </label>
          <small>
            Comma-separated. Company-style curricula remain independent and never
            claim employer provenance.
          </small>
        </fieldset>
        <fieldset>
          <legend>05 · Self-assessment</legend>
          <div className="form-grid">
            <label>
              <span>Strong areas</span>
              <textarea
                value={strongAreas}
                onChange={(event) => setStrongAreas(event.target.value)}
                placeholder="Python, API design, data modeling"
              />
            </label>
            <label>
              <span>Areas to strengthen</span>
              <textarea
                value={weakAreas}
                onChange={(event) => setWeakAreas(event.target.value)}
                placeholder="Distributed systems, capacity planning"
              />
            </label>
          </div>
        </fieldset>
        {error && (
          <div className="inline-alert" role="alert">
            {error}
          </div>
        )}
        <button
          className="button button--primary onboarding-submit"
          disabled={saving}
          type="submit"
        >
          {saving
            ? "Saving profile…"
            : initial
              ? "Save profile changes"
              : "Complete onboarding"}
          <ArrowRight size={16} />
        </button>
      </div>
    </form>
  );
}

export function Onboarding() {
  const profile = useQuery({
    queryKey: ["candidate-profile"],
    queryFn: ({ signal }) => getProfile(signal),
    retry: false,
  });
  if (profile.isLoading) {
    return (
      <div className="page-content">
        <LoadingState label="Checking saved onboarding" />
      </div>
    );
  }
  if (
    profile.isError &&
    !(profile.error instanceof ApiError && profile.error.status === 404)
  ) {
    return (
      <div className="page-content">
        <ErrorState retry={() => void profile.refetch()} />
      </div>
    );
  }
  return (
    <div className="page-content page-content--wide">
      <OnboardingForm initial={profile.data} />
    </div>
  );
}
