import { describe, expect, it } from "vitest";
import type {
} from "./contracts";
import {
  csiFrames,
  evidencePackets,
  featureWindows,
  signalTriplets,
} from "./fixtures";

// Compile-time compatibility is enforced by the typed exports in fixtures.ts.
const frames = csiFrames;
const windows = featureWindows;
const triplets = signalTriplets;
const packets = evidencePackets;

describe("generated contract types accept the mock fixtures", () => {
  it("csi frames are valid normalized frames", () => {
    expect(frames.length).toBeGreaterThan(0);
    for (const frame of frames) {
      expect(["mock", "replay", "live"]).toContain(frame.source_mode);
      expect(frame.csi_iq.length).toBeGreaterThanOrEqual(2);
      expect(frame.quality.parse_ok).toBe(true);
    }
  });

  it("feature windows expose per-link summaries", () => {
    expect(windows.length).toBeGreaterThan(0);
    for (const window of windows) {
      expect(window.links["rx-a"]).toBeDefined();
      expect(window.paired_packet_coverage).toBeGreaterThanOrEqual(0);
    }
  });

  it("signal triplets carry the three proxies", () => {
    expect(triplets.length).toBe(3);
    for (const triplet of triplets) {
      expect(triplet.motion.value).toBeGreaterThanOrEqual(0);
      expect(triplet.occupancy_density.state).toBeTruthy();
      expect(triplet.depth_zone.state).toBeTruthy();
    }
  });

  it("evidence packets expose sealed sha256 hashes", () => {
    expect(packets.length).toBe(1);
    for (const packet of packets) {
      expect(packet.evidence_hash.startsWith("sha256:")).toBe(true);
      expect(packet.evidence_hash).toHaveLength(71);
      expect(packet.source_manifest.source_mode).toBe("mock");
    }
  });
});
