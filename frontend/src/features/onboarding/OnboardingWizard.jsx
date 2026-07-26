import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { api } from "../../api/client";
import BasicInfoScreen from "./BasicInfoScreen";
import GoalScreen from "./GoalScreen";
import ExperienceScreen from "./ExperienceScreen";
import AvailabilityScreen from "./AvailabilityScreen";
import EquipmentScreen from "./EquipmentScreen";
import SummaryScreen from "./SummaryScreen";

const EMPTY_DRAFT = {
  display_name: "",
  age: "",
  height_cm: "",
  bodyweight_kg: "",
  sex: "",
  global_goal: "",
  experience: "",
  days_per_week: 4,
  session_minutes: 60,
  training_location: "",
  equipment: [],
  privacy_accepted: false,
};

const STEPS = [3, 4, 5, 6, 7, 8]; // matches White Paper §4.2 screen numbers

export default function OnboardingWizard() {
  const { setUser } = useAuth();
  // Draft lives only in React state until the final POST (White Paper §4.1):
  // a refresh before completion means starting over, by design.
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [stepIndex, setStepIndex] = useState(0);

  const updateDraft = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const goNext = () => setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
  const goBack = () => setStepIndex((i) => Math.max(i - 1, 0));
  const jumpToStep = (screenNumber) => setStepIndex(STEPS.indexOf(screenNumber));

  const handleSubmit = async () => {
    const payload = {
      ...draft,
      age: Number(draft.age),
      height_cm: Number(draft.height_cm),
      bodyweight_kg: Number(draft.bodyweight_kg),
    };
    const data = await api.post("/onboarding", payload);
    setUser(data.user);
  };

  const step = STEPS[stepIndex];
  const commonProps = {
    draft,
    updateDraft,
    onNext: goNext,
    onBack: stepIndex > 0 ? goBack : undefined,
  };

  switch (step) {
    case 3:
      return <BasicInfoScreen {...commonProps} />;
    case 4:
      return <GoalScreen {...commonProps} />;
    case 5:
      return <ExperienceScreen {...commonProps} />;
    case 6:
      return <AvailabilityScreen {...commonProps} />;
    case 7:
      return <EquipmentScreen {...commonProps} />;
    case 8:
      return (
        <SummaryScreen
          draft={draft}
          updateDraft={updateDraft}
          onSubmit={handleSubmit}
          onEditStep={jumpToStep}
          onBack={goBack}
        />
      );
    default:
      return null;
  }
}
