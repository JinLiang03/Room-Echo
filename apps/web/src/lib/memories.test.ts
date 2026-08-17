import { beforeEach, describe, expect, it } from "vitest";
import { signalTriplets } from "../generated/fixtures";
import {
  deleteLifeMemory,
  findEchoMemory,
  readLifeMemories,
  saveLifeMemory,
} from "./memories";
import type { SignalTriplet } from "./types";

const triplet = signalTriplets[1] as SignalTriplet;

describe("local visual memories", () => {
  beforeEach(() => window.localStorage.clear());

  it("stores only compact derived values and deletes by id", () => {
    const memory = saveLifeMemory({
      lifeState: "flow",
      triplet,
      result: null,
      now: new Date("2026-08-08T10:00:00Z"),
    });
    expect(readLifeMemories()).toEqual([memory]);
    expect(JSON.stringify(memory)).not.toContain("raw");
    expect(deleteLifeMemory(memory.id)).toEqual([]);
  });

  it("does not echo a just-created memory but can match an older proxy signature", () => {
    const recent = saveLifeMemory({
      lifeState: "rest",
      triplet,
      result: null,
      now: new Date("2026-08-08T10:00:00Z"),
    });
    expect(findEchoMemory(triplet, [recent], new Date("2026-08-08T10:00:10Z").getTime())).toBeNull();
    expect(findEchoMemory(triplet, [recent], new Date("2026-08-08T10:01:00Z").getTime())?.id).toBe(recent.id);
  });

  it("does not carry a visual echo across source modes or sessions", () => {
    const memory = saveLifeMemory({
      lifeState: "rest",
      triplet,
      result: null,
      now: new Date("2026-08-08T10:00:00Z"),
    });
    const later = new Date("2026-08-08T10:01:00Z").getTime();
    expect(
      findEchoMemory({ ...triplet, session_id: "another-session" }, [memory], later),
    ).toBeNull();
    expect(
      findEchoMemory({ ...triplet, source_mode: "live" }, [memory], later),
    ).toBeNull();
  });
});
