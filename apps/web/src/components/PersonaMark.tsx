import { personaFor } from "../lib/personas";

export function PersonaMark({ role }: { role: string }) {
  const persona = personaFor(role);
  return (
    <span
      className={`persona-mark persona-mark-${role}`}
      title={`${persona.name} · 角色视觉隐喻`}
      aria-hidden="true"
    >
      <span>{persona.glyph}</span>
      <i>·</i>
    </span>
  );
}
