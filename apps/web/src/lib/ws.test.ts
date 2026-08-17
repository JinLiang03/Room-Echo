import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StreamClient, type ConnectionStatus } from "./ws";
import type { StreamEvent } from "./types";

class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    FakeSocket.instances.push(this);
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  emit(event: StreamEvent): void {
    this.onmessage?.({ data: JSON.stringify(event) });
  }
}

describe("StreamClient", () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("connects, forwards events, and tracks last sequence", () => {
    const statuses: ConnectionStatus[] = [];
    const events: StreamEvent[] = [];
    const client = new StreamClient({
      url: "ws://test/ws",
      createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
      onStatus: (status) => statuses.push(status),
      onEvent: (event) => events.push(event),
    });
    client.connect();
    expect(statuses[0]).toBe("connecting");
    const socket = FakeSocket.instances[0];
    expect(socket.url).toBe("ws://test/ws");
    socket.open();
    expect(statuses).toContain("online");
    expect(socket.sent).toEqual([]);
    socket.emit({
      sequence: 7,
      event_type: "signal.frame",
      payload: {},
    });
    socket.emit({
      sequence: 9,
      event_type: "heartbeat",
      payload: {},
    });
    socket.emit({
      sequence: 8,
      event_type: "heartbeat",
      payload: {},
    });
    expect(events).toHaveLength(3);
    client.close();
  });

  it("reconnects with last_sequence after an unexpected close", () => {
    const statuses: ConnectionStatus[] = [];
    const client = new StreamClient({
      url: "ws://test/ws",
      createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
      onStatus: (status) => statuses.push(status),
      onEvent: () => undefined,
      reconnectBaseMs: 100,
    });
    client.connect();
    const first = FakeSocket.instances[0];
    first.open();
    first.emit({ sequence: 42, event_type: "heartbeat", payload: {} });
    first.emit({ sequence: 40, event_type: "heartbeat", payload: {} });
    first.close();
    expect(statuses).toContain("offline");
    vi.advanceTimersByTime(200);
    expect(FakeSocket.instances.length).toBe(2);
    const second = FakeSocket.instances[1];
    expect(second.url).toBe("ws://test/ws?last_sequence=42");
    second.open();
    expect(second.sent).toEqual([]);
    client.close();
  });

  it("sends control messages as JSON", () => {
    const client = new StreamClient({
      url: "ws://test/ws",
      createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
      onStatus: () => undefined,
      onEvent: () => undefined,
    });
    client.connect();
    const socket = FakeSocket.instances[0];
    socket.open();
    client.control("rate", { rate: 2 });
    const last = socket.sent[socket.sent.length - 1];
    expect(JSON.parse(last)).toEqual({ type: "control", action: "rate", rate: 2 });
    client.close();
  });

  it("resets the resume sequence when the server starts a new session", () => {
    const client = new StreamClient({
      url: "ws://test/ws",
      createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
      onStatus: () => undefined,
      onEvent: () => undefined,
      reconnectBaseMs: 100,
    });
    client.connect();
    const first = FakeSocket.instances[0];
    first.open();
    first.emit({
      session_id: "session-old",
      sequence: 42,
      event_type: "heartbeat",
      payload: {},
    });
    first.emit({
      session_id: "session-new",
      sequence: 1,
      event_type: "session.status",
      payload: {},
    });
    first.close();
    vi.advanceTimersByTime(200);
    expect(FakeSocket.instances[1].url).toBe(
      "ws://test/ws?last_sequence=1",
    );
    client.close();
  });
});
