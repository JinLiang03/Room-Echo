import type { AlertItem } from "../lib/types";

export function AlertTray({ alerts }: { alerts: AlertItem[] }) {
  if (alerts.length === 0) {
    return null;
  }
  return (
    <div className="alert-tray" aria-live="polite" aria-label="告警">
      {alerts.map((alert) => (
        <div key={alert.id} className={`alert alert-${alert.level}`} role="status">
          <span className="alert-level">{alert.level}</span>
          {alert.message}
        </div>
      ))}
    </div>
  );
}
