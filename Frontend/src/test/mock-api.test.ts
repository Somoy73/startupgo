import { describe, expect, it } from "vitest";
import { api } from "../api/client";
import { emptyAssessment, emptyCompany } from "../lib/assessment";

describe("Preview API boundaries", () => {
  it("keeps the uploaded three-startup comparison limit", async () => {
    const result = await api.compare(["origin-by-ocean", "kelp-blue", "sulapac", "clearbot"]);
    expect(result.map((s) => s.slug)).toEqual(["origin-by-ocean", "kelp-blue", "sulapac"]);
  });
  it("reads back a mocked pipeline change", async () => {
    await api.setPipeline("clearbot", "screening");
    expect((await api.startup("clearbot")).pipeline_stage).toBe("screening");
  });
  it("reads back a mocked analyst note", async () => {
    await api.addNote("kelp-blue", "Evidence requested");
    expect((await api.startup("kelp-blue")).notes[0]?.body).toBe("Evidence requested");
  });
  it("adds a new startup as Sourced as in the supplied assessment page", async () => {
    const draft = { ...emptyAssessment(), assessor: "Reviewer" };
    const saved = await api.createStartup({
      company: { ...emptyCompany, name: "Test Ocean", sector: "Seaweed", country: "Finland" },
      draft,
    });
    const result = await api.startup(saved.slug);
    expect(result.pipeline_stage).toBe("sourced");
    expect(result.readiness.assessor).toBe("Reviewer");
  });
});
