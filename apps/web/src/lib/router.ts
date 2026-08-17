import { useEffect, useState } from "react";

export type RouteName =
  | "home"
  | "observe"
  | "council"
  | "evidence"
  | "replay"
  | "story"
  | "perf"
  | "settings";

export function parseHash(): RouteName {
  const raw = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  const known: RouteName[] = [
    "home",
    "observe",
    "council",
    "evidence",
    "replay",
    "story",
    "perf",
    "settings",
  ];
  return (known as string[]).includes(raw) ? (raw as RouteName) : "home";
}

export function navigate(route: RouteName, params?: Record<string, string>): void {
  const query = params
    ? `?${new URLSearchParams(params).toString()}`
    : "";
  window.location.hash = `/${route}${query}`;
}

export function routeParams(): URLSearchParams {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const query = raw.split("?")[1] ?? "";
  return new URLSearchParams(query);
}

export function useRoute(): RouteName {
  const [route, setRoute] = useState<RouteName>(() => parseHash());
  useEffect(() => {
    const onChange = () => setRoute(parseHash());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
