import { View, Text, StyleSheet } from "react-native";

interface AgentStepsProps {
  steps: string[];
  currentStep: string | null;
  completedSteps: string[];
}

type StepState = "idle" | "active" | "completed";

function getStepState(
  stepName: string,
  currentStep: string | null,
  completedSteps: string[],
): StepState {
  if (completedSteps.includes(stepName)) return "completed";
  if (currentStep === stepName) return "active";
  return "idle";
}

const PILL_COLORS: Record<StepState, string> = {
  idle: "#333",
  active: "#4a90d9",
  completed: "#4ade80",
};

const LABEL_COLORS: Record<StepState, string> = {
  idle: "#555",
  active: "#4a90d9",
  completed: "#4ade80",
};

/**
 * Horizontal step indicator showing agent chain progression.
 * Each step renders as a pill-shaped indicator connected by thin dashes.
 */
export function AgentSteps({
  steps,
  currentStep,
  completedSteps,
}: AgentStepsProps) {
  return (
    <View style={styles.container}>
      {steps.map((step, index) => {
        const state = getStepState(step, currentStep, completedSteps);
        return (
          <View key={step} style={styles.stepRow}>
            {index > 0 && <View style={styles.connector} />}
            <View style={styles.stepItem}>
              <View
                style={[
                  styles.pill,
                  { backgroundColor: PILL_COLORS[state] },
                  state === "active" && styles.pillActive,
                ]}
              />
              <Text style={[styles.label, { color: LABEL_COLORS[state] }]}>
                {step}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  connector: {
    width: 24,
    height: 2,
    backgroundColor: "#333",
    marginHorizontal: 4,
  },
  stepItem: {
    alignItems: "center",
  },
  pill: {
    width: 48,
    height: 12,
    borderRadius: 6,
  },
  pillActive: {
    // Brighter glow effect for the active step
    shadowColor: "#4a90d9",
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 6,
    elevation: 4,
  },
  label: {
    fontSize: 10,
    fontWeight: "500",
    marginTop: 4,
  },
});
