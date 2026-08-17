import type { StreamEvent } from "./types";

export type ConnectionStatus = "connecting" | "online" | "offline";

const OPEN = 1;

export interface StreamClientOptions {
  url: string;
  onEvent: (event: StreamEvent) => void;
  onStatus: (status: ConnectionStatus) => void;
  createSocket?: (url: string) => WebSocket;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
}

/**
 * WebSocket client with reconnect + sequence recovery.
 *
 * On (re)connect it sends `last_sequence` so the server can replay buffered
 * events; out-of-order/duplicate events are counted and dropped by the
 * reducer, never applied twice.
 */
export class StreamClient {
  private socket: WebSocket | null = null;
  private closed = false;
  private retry = 0;
  private reconnectTimer: number | null = null;
  private lastSequence: number | null = null;
  private sessionId: string | null = null;
  private readonly options: Required<Pick<StreamClientOptions, "url" | "reconnectBaseMs" | "reconnectMaxMs">> &
    StreamClientOptions;

  constructor(options: StreamClientOptions) {
    this.options = {
      reconnectBaseMs: 500,
      reconnectMaxMs: 8000,
      ...options,
    };
  }

  connect(): void {
    this.closed = false;
    this.open();
  }

  private open(): void {
    if (this.closed) {
      return;
    }
    this.options.onStatus("connecting");
    const create = this.options.createSocket ?? ((url: string) => new WebSocket(url));
    let socket: WebSocket;
    try {
      socket = create(this.resumeUrl());
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      this.retry = 0;
      this.options.onStatus("online");
    };
    socket.onmessage = (message) => {
      let event: StreamEvent;
      try {
        const raw = JSON.parse(String(message.data)) as Record<string, unknown>;
        if (raw.type === "pong" || raw.type === "hello") {
          return;
        }
        event = raw as unknown as StreamEvent;
      } catch {
        return;
      }
      if (event.sequence !== undefined && event.sequence !== null) {
        if (
          event.session_id != null &&
          this.sessionId !== null &&
          event.session_id !== this.sessionId
        ) {
          this.lastSequence = event.sequence;
        } else {
          this.lastSequence = Math.max(this.lastSequence ?? -1, event.sequence);
        }
      }
      if (event.session_id != null) {
        this.sessionId = event.session_id;
      }
      this.options.onEvent(event);
    };
    socket.onclose = () => {
      if (this.closed) {
        return;
      }
      this.options.onStatus("offline");
      this.scheduleReconnect();
    };
    socket.onerror = () => {
      // close will follow; keep the state transition there
    };
  }

  private resumeUrl(): string {
    if (this.lastSequence === null) {
      return this.options.url;
    }
    const url = new URL(this.options.url, window.location.href);
    url.searchParams.set("last_sequence", String(this.lastSequence));
    return url.toString();
  }

  private scheduleReconnect(): void {
    if (this.closed || this.reconnectTimer !== null) {
      return;
    }
    const delay = Math.min(
      this.options.reconnectBaseMs * 2 ** this.retry,
      this.options.reconnectMaxMs,
    );
    this.retry += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.open();
    }, delay);
  }

  send(payload: unknown): void {
    if (this.socket && this.socket.readyState === OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  control(action: string, payload?: Record<string, unknown>): void {
    this.send({ type: "control", action, ...payload });
  }

  ping(): void {
    this.send({ type: "ping" });
  }

  close(): void {
    this.closed = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
  }
}
