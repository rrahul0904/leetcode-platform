import { colors, radius, spacing } from "@rigor/design-tokens";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import type { CandidateProfile, CandidateProfileInput } from "../api/types";
import { Card, Eyebrow, PrimaryButton, mobileStyles } from "../ui/primitives";

const roleOptions = [
  "Senior backend engineer",
  "Staff engineer",
  "Principal engineer",
  "Data architect",
  "ML engineer",
  "AI infrastructure engineer",
] as const;

const experienceOptions = ["mid", "senior", "staff", "principal", "manager"] as const;
const languageOptions = ["python", "sql", "mixed"] as const;
const intensityOptions = ["steady", "focused", "intensive"] as const;

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
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

function Choice<T extends string>({
  value,
  selected,
  onPress,
}: {
  value: T;
  selected: boolean;
  onPress: (value: T) => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={() => onPress(value)}
      style={[styles.choice, selected && styles.choiceSelected]}
    >
      <Text style={[styles.choiceText, selected && styles.choiceTextSelected]}>{value}</Text>
    </Pressable>
  );
}

export function CandidateProfileEditor({
  initial,
  onSave,
  saving,
}: {
  initial?: CandidateProfile;
  onSave: (profile: CandidateProfileInput) => Promise<void> | void;
  saving: boolean;
}) {
  const initialInput = useMemo(() => (initial ? editableProfile(initial) : emptyProfile), [initial]);
  const [profile, setProfile] = useState<CandidateProfileInput>(initialInput);
  const [companies, setCompanies] = useState((initial?.target_companies ?? []).join(", "));
  const [strongAreas, setStrongAreas] = useState((initial?.strong_areas ?? []).join(", "));
  const [weakAreas, setWeakAreas] = useState((initial?.weak_areas ?? []).join(", "));
  const [error, setError] = useState<string | null>(null);

  function toggleRole(role: string) {
    setProfile((current) => ({
      ...current,
      target_roles: current.target_roles.includes(role)
        ? current.target_roles.filter((item) => item !== role)
        : [...current.target_roles, role],
    }));
  }

  async function save() {
    setError(null);
    if (profile.target_roles.length === 0) {
      setError("Choose at least one target role.");
      return;
    }
    if (profile.weekly_study_hours < 1 || profile.weekly_study_hours > 40) {
      setError("Weekly study hours must be between 1 and 40.");
      return;
    }
    await onSave({
      ...profile,
      target_companies: splitList(companies),
      strong_areas: splitList(strongAreas),
      weak_areas: splitList(weakAreas),
    });
  }

  return (
    <View style={styles.stack}>
      <Card>
        <Eyebrow>TARGET ROLES</Eyebrow>
        <Text style={mobileStyles.small}>Choose one or more role families.</Text>
        <View style={styles.choices}>
          {roleOptions.map((role) => (
            <Choice
              key={role}
              value={role}
              selected={profile.target_roles.includes(role)}
              onPress={toggleRole}
            />
          ))}
        </View>
      </Card>

      <Card>
        <Eyebrow>EXPERIENCE & TOOLS</Eyebrow>
        <Text style={styles.label}>Current level</Text>
        <View style={styles.choices}>
          {experienceOptions.map((value) => (
            <Choice
              key={value}
              value={value}
              selected={profile.experience_level === value}
              onPress={(next) => setProfile((current) => ({ ...current, experience_level: next }))}
            />
          ))}
        </View>
        <Text style={styles.label}>Preferred practice language</Text>
        <View style={styles.choices}>
          {languageOptions.map((value) => (
            <Choice
              key={value}
              value={value}
              selected={profile.preferred_programming_language === value}
              onPress={(next) =>
                setProfile((current) => ({ ...current, preferred_programming_language: next }))
              }
            />
          ))}
        </View>
      </Card>

      <Card>
        <Eyebrow>TIME & INTENSITY</Eyebrow>
        <Text style={styles.label}>Weekly study hours</Text>
        <TextInput
          accessibilityLabel="Weekly study hours"
          keyboardType="number-pad"
          style={styles.input}
          value={String(profile.weekly_study_hours)}
          onChangeText={(value) =>
            setProfile((current) => ({
              ...current,
              weekly_study_hours: Number(value.replace(/[^0-9]/g, "")) || 0,
            }))
          }
        />
        <Text style={styles.label}>Interview date (optional, YYYY-MM-DD)</Text>
        <TextInput
          accessibilityLabel="Interview date"
          autoCapitalize="none"
          placeholder="2026-10-15"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={profile.interview_date ?? ""}
          onChangeText={(value) =>
            setProfile((current) => ({ ...current, interview_date: value.trim() || null }))
          }
        />
        <Text style={styles.label}>Preparation intensity</Text>
        <View style={styles.choices}>
          {intensityOptions.map((value) => (
            <Choice
              key={value}
              value={value}
              selected={profile.preparation_intensity === value}
              onPress={(next) =>
                setProfile((current) => ({ ...current, preparation_intensity: next }))
              }
            />
          ))}
        </View>
      </Card>

      <Card>
        <Eyebrow>TARGET CONTEXT</Eyebrow>
        <Text style={styles.label}>Target companies or company types</Text>
        <TextInput
          accessibilityLabel="Target companies"
          placeholder="AI lab, marketplace, fintech platform"
          placeholderTextColor={colors.textMuted}
          style={styles.input}
          value={companies}
          onChangeText={setCompanies}
        />
        <Text style={mobileStyles.small}>Comma-separated. Company-style curricula remain independent.</Text>
        <Text style={styles.label}>Strong areas</Text>
        <TextInput
          accessibilityLabel="Strong areas"
          multiline
          placeholder="Python, API design, data modeling"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.multiline]}
          value={strongAreas}
          onChangeText={setStrongAreas}
        />
        <Text style={styles.label}>Areas to strengthen</Text>
        <TextInput
          accessibilityLabel="Areas to strengthen"
          multiline
          placeholder="Distributed systems, capacity planning"
          placeholderTextColor={colors.textMuted}
          style={[styles.input, styles.multiline]}
          value={weakAreas}
          onChangeText={setWeakAreas}
        />
      </Card>

      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      <PrimaryButton
        label={initial ? "Save profile changes" : "Complete onboarding"}
        busy={saving}
        onPress={() => void save()}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  choice: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  choiceSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  choiceText: { color: colors.textMuted, fontWeight: "700" },
  choiceTextSelected: { color: colors.background },
  label: { color: colors.text, fontWeight: "700" },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceRaised,
    color: colors.text,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: 16,
  },
  multiline: { minHeight: 96, textAlignVertical: "top" },
  error: { color: colors.danger, lineHeight: 22 },
});
