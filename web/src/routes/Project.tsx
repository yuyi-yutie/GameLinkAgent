import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { Stepper, type StepKey } from "../components/Stepper";
import { message } from "../lib/format";
import type { DesignerOptions, ProjectInfo } from "../types";
import { AnalyzeStep, type AnalyzeOutcome } from "../steps/AnalyzeStep";
import { DeployStep, type DeployOutcome } from "../steps/DeployStep";
import { GenerateStep, type GenerateOutcome } from "../steps/GenerateStep";
import { ImportStep } from "../steps/ImportStep";
import { SpecsStep } from "../steps/SpecsStep";

interface Props {
  path: string;
  onLeave: () => void;
}

export function Project({ path, onLeave }: Props) {
  const [project, setProject] = useState<ProjectInfo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [step, setStep] = useState<StepKey>("import");
  const [choices, setChoices] = useState<Record<string, string[]>>({});
  const [options, setOptions] = useState<DesignerOptions | null>(null);
  const [analyzeOut, setAnalyzeOut] = useState<AnalyzeOutcome | null>(null);
  const [generateOut, setGenerateOut] = useState<GenerateOutcome | null>(null);
  const [deployOut, setDeployOut] = useState<DeployOutcome | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProject(null);
    setLoadError(null);
    setAnalyzeOut(null);
    setGenerateOut(null);
    setDeployOut(null);
    setStep("import");

    api
      .project(path)
      .then((info) => {
        if (!cancelled) setProject(info);
      })
      .catch((cause) => {
        if (!cancelled) setLoadError(message(cause));
      });

    api
      .options()
      .then((response) => {
        if (cancelled) return;
        setChoices(response.choices);
        setOptions((current) => current ?? response.defaults);
      })
      .catch((cause) => {
        if (!cancelled) setLoadError(message(cause));
      });

    return () => {
      cancelled = true;
    };
  }, [path]);

  const handleAnalyze = useCallback((outcome: AnalyzeOutcome) => {
    setAnalyzeOut(outcome);
    setStep("specs");
  }, []);
  const handleGenerate = useCallback((outcome: GenerateOutcome) => {
    setGenerateOut(outcome);
  }, []);
  const handleDeploy = useCallback((outcome: DeployOutcome) => {
    setDeployOut(outcome);
  }, []);

  const done: StepKey[] = ["import"];
  if (analyzeOut) done.push("analyze");
  if (analyzeOut && analyzeOut.specs.length > 0) done.push("specs");
  if (generateOut) done.push("generate");
  if (deployOut) done.push("deploy");

  return (
    <main className="project">
      <div className="project-bar">
        <button type="button" className="btn btn-ghost" onClick={onLeave}>
          ← 换一个工程
        </button>
        <span className="project-name">{project?.name ?? path}</span>
      </div>

      <Stepper current={step} done={done} onSelect={setStep} />

      {/* Every step stays mounted: switching steps must not drop a running job. */}
      <div className={step === "import" ? "step-view" : "step-view hidden"}>
        <ImportStep project={project} error={loadError} onNext={() => setStep("analyze")} />
      </div>
      <div className={step === "analyze" ? "step-view" : "step-view hidden"}>
        <AnalyzeStep
          projectPath={path}
          choices={choices}
          options={options}
          onOptions={setOptions}
          onOutcome={handleAnalyze}
          onNext={() => setStep("specs")}
        />
      </div>
      <div className={step === "specs" ? "step-view" : "step-view hidden"}>
        <SpecsStep
          projectPath={path}
          specsDir={analyzeOut?.out ?? null}
          specs={analyzeOut?.specs ?? []}
          onNext={() => setStep("generate")}
        />
      </div>
      <div className={step === "generate" ? "step-view" : "step-view hidden"}>
        <GenerateStep
          projectPath={path}
          specsDir={analyzeOut?.out ?? null}
          onOutcome={handleGenerate}
          onNext={() => setStep("deploy")}
        />
      </div>
      <div className={step === "deploy" ? "step-view" : "step-view hidden"}>
        <DeployStep serverDir={generateOut?.out ?? null} onOutcome={handleDeploy} />
      </div>
    </main>
  );
}
