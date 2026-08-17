import type { RouteName } from "../lib/router";
import { useStream } from "../lib/state";

const NAV: { route: RouteName; label: string }[] = [
  { route: "home", label: "此刻" },
  { route: "replay", label: "记忆" },
  { route: "council", label: "为什么" },
];

interface Props {
  route: RouteName;
  onNavigate: (route: RouteName) => void;
}

export function TopBar({ route, onNavigate }: Props) {
  const { state } = useStream();
  const activeRoute = publicRoute(route);
  const sourceBadge = badgeForSourceMode(
    state.session?.mode ?? state.sourceHealth?.source_mode,
  );
  return (
    <header className={`topbar topbar-${route}`} aria-label="应用顶栏">
      <div className="topbar-identity">
        <button
          type="button"
          className="topbar-brand"
          onClick={() => onNavigate("home")}
          aria-label="回到此刻"
        >
          <span className="topbar-wordmark">
            <span className="brand-title">Room Echo</span>
            <small>空间回声</small>
          </span>
        </button>
        <span
          className={`source-mode-badge source-mode-${sourceBadge.kind}`}
          aria-label={sourceBadge.accessibleLabel}
          title={sourceBadge.detail}
        >
          {sourceBadge.label}
        </span>
      </div>
      <nav className="topnav" aria-label="主导航">
        {NAV.map((item) => (
          <button
            key={item.route}
            type="button"
            className={`nav-button ${activeRoute === item.route ? "nav-active" : ""}`}
            aria-current={activeRoute === item.route ? "page" : undefined}
            onClick={() => onNavigate(item.route)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <button
        type="button"
        className={`settings-glyph ${route === "settings" ? "settings-glyph-active" : ""}`}
        onClick={() => onNavigate("settings")}
        aria-label="设置"
        title="设置"
      >
        <span aria-hidden="true">⌁</span>
      </button>
    </header>
  );
}

function badgeForSourceMode(mode: string | null | undefined): {
  kind: "live" | "sim" | "waiting";
  label: string;
  accessibleLabel: string;
  detail: string;
} {
  if (mode === "live") {
    return {
      kind: "live",
      label: "LIVE",
      accessibleLabel: "数据源：LIVE 实时硬件",
      detail: "实时硬件数据源",
    };
  }
  if (mode === "mock") {
    return {
      kind: "sim",
      label: "SIM · MOCK",
      accessibleLabel: "数据源：SIM MOCK 模拟数据，非实时硬件",
      detail: "模拟数据，非实时硬件",
    };
  }
  if (mode === "replay") {
    return {
      kind: "sim",
      label: "SIM · REPLAY",
      accessibleLabel: "数据源：SIM REPLAY 回放数据，非实时硬件",
      detail: "录制回放，非实时硬件",
    };
  }
  return {
    kind: "waiting",
    label: "SIM · WAIT",
    accessibleLabel: "数据源：尚未确认，非实时硬件",
    detail: "尚未确认数据源；不会标记为实时硬件",
  };
}

function publicRoute(route: RouteName): RouteName | null {
  if (route === "home" || route === "observe") return "home";
  if (route === "council" || route === "evidence") return "council";
  if (route === "replay") return "replay";
  return null;
}
