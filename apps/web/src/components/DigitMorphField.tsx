import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { DigitSectionMark } from "./DigitSectionMark";
import { measureFrameTiming } from "../lib/frame-timing";
import {
  lifeStateDefinition,
  type LifeStateId,
} from "../lib/life-state";
import {
  mapRenderParams,
  renderSnapshotHash,
  seedParticles,
  VISUAL_SEED,
  type Particle,
  type RenderParams,
} from "../lib/multimodal";
import {
  createThemePoints,
  spatialTheme,
  type SpatialPoint,
  type SpatialThemeId,
} from "../lib/spatial-themes";
import type { CouncilResult, SignalTriplet } from "../lib/types";
import { RAINBOW_COLORS } from "../lib/rainbow";

interface Props {
  theme: SpatialThemeId;
  triplet: SignalTriplet | null;
  result: CouncilResult | null;
  stale: boolean;
  reducedMotion?: boolean;
  debug?: boolean;
  autoMorph?: boolean;
  pointCount?: number;
  onStats?: (stats: Stats) => void;
  lifeState?: LifeStateId;
  onRemember?: () => void;
}

interface Stats {
  fps: number;
  drawCalls: number;
  dropped: number;
}

interface PointerState {
  x: number;
  y: number;
  normalizedX: number;
  normalizedY: number;
  speed: number;
  active: boolean;
}

interface ScrollState {
  velocity: number;
  lastY: number;
}

interface MutablePoint {
  x: number;
  y: number;
  z: number;
  glyph: string;
  phase: number;
  weight: number;
}

const DEFAULT_POINT_COUNT = 540;

/**
 * A user-selected, digit-built visual theme driven by the approved render
 * parameters. Theme identity and pointer deformation are presentation only:
 * neither can write to SignalTriplet, confidence, or Council state.
 */
export function DigitMorphField({
  theme,
  triplet,
  result,
  stale,
  reducedMotion = false,
  debug = false,
  autoMorph = false,
  pointCount = DEFAULT_POINT_COUNT,
  onStats,
  lifeState = "sound",
  onRemember,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const paramsRef = useRef<RenderParams>(
    mapRenderParams({ triplet, result, stale }),
  );
  const particlesRef = useRef<Particle[]>(seedParticles(VISUAL_SEED, pointCount));
  const [initialPoints] = useState(() =>
    createThemePoints(autoMorph && !reducedMotion ? "floorplan" : theme, pointCount),
  );
  const currentPointsRef = useRef<MutablePoint[]>(clonePoints(initialPoints));
  const fromPointsRef = useRef<MutablePoint[]>(clonePoints(initialPoints));
  const targetPointsRef = useRef<SpatialPoint[]>(initialPoints);
  const alternatePointsRef = useRef<SpatialPoint[]>(
    createThemePoints("atrium", pointCount),
  );
  const visualThemeRef = useRef<SpatialThemeId>(
    autoMorph && !reducedMotion ? "floorplan" : theme,
  );
  const pointerRef = useRef<PointerState>({
    x: 0,
    y: 0,
    normalizedX: 0,
    normalizedY: 0,
    speed: 0,
    active: false,
  });
  const scrollRef = useRef<ScrollState>({ velocity: 0, lastY: 0 });
  const pressTimerRef = useRef<number | null>(null);
  const pressOriginRef = useRef({ x: 0, y: 0 });
  const longPressTriggeredRef = useRef(false);
  const pressMovedRef = useRef(false);
  const activityRef = useRef(0);
  const morphRef = useRef(1);
  const introCompleteRef = useRef(!autoMorph);
  const lifeStateRef = useRef(lifeState);
  const themeRef = useRef(theme);
  const lastLifeStateRef = useRef(lifeState);
  const lastThemeRef = useRef(theme);
  const emissionSourceRef = useRef({
    lifeState,
    cycleId: result?.cycle_id ?? null,
  });
  const emissionStartedRef = useRef(Number.NEGATIVE_INFINITY);
  const redrawRef = useRef<(() => void) | null>(null);
  const staticModeRef = useRef(false);
  const [stats, setStats] = useState<Stats>({ fps: 0, drawCalls: 0, dropped: 0 });
  const [snapshotHash, setSnapshotHash] = useState("");
  const [emission, setEmission] = useState(0);
  const [visualStage, setVisualStage] = useState<SpatialThemeId | "river">(
    autoMorph && !reducedMotion ? "floorplan" : theme,
  );

  const renderParams = mapRenderParams({ triplet, result, stale });
  paramsRef.current = renderParams;
  lifeStateRef.current = lifeState;
  themeRef.current = theme;

  useEffect(() => {
    if (autoMorph) return;
    const next = createThemePoints(theme, pointCount);
    setTargetGeometry(next, theme, pointCount, currentPointsRef, fromPointsRef,
      targetPointsRef, alternatePointsRef, particlesRef, visualThemeRef, morphRef,
      staticModeRef.current);
    setVisualStage(theme);
    redrawRef.current?.();
  }, [autoMorph, pointCount, theme]);

  useEffect(() => {
    if (!autoMorph || introCompleteRef.current) {
      return;
    }
    const targetTheme = themeRef.current;
    const staticMode = prefersReducedMotion(reducedMotion);
    if (staticMode) {
      const target = createThemePoints(targetTheme, pointCount);
      setTargetGeometry(target, targetTheme, pointCount, currentPointsRef, fromPointsRef,
        targetPointsRef, alternatePointsRef, particlesRef, visualThemeRef, morphRef, true);
      setVisualStage(targetTheme);
      introCompleteRef.current = true;
      lastLifeStateRef.current = lifeStateRef.current;
      lastThemeRef.current = targetTheme;
      redrawRef.current?.();
      return;
    }

    // No data means no invented lifecycle. Keep a partial plan until an
    // approved signal triplet arrives, then play the introduction once.
    if (!renderParams.active) return;

    const plan = createThemePoints("floorplan", pointCount);
    currentPointsRef.current = clonePoints(plan);
    fromPointsRef.current = clonePoints(plan);
    targetPointsRef.current = plan;
    alternatePointsRef.current = createThemePoints("atrium", pointCount);
    visualThemeRef.current = "floorplan";
    setVisualStage("floorplan");
    particlesRef.current = seedParticles(VISUAL_SEED, pointCount);
    morphRef.current = 1;
    redrawRef.current?.();

    const volumeTimer = window.setTimeout(() => {
      const volume = createThemePoints("volume", pointCount);
      setTargetGeometry(volume, "volume", pointCount, currentPointsRef, fromPointsRef,
        targetPointsRef, alternatePointsRef, particlesRef, visualThemeRef, morphRef, false);
      setVisualStage("volume");
    }, 1200);
    const bodyTimer = window.setTimeout(() => {
      const currentState = lifeStateRef.current;
      const currentTheme = themeRef.current;
      const body = createThemePoints(currentTheme, pointCount);
      setTargetGeometry(body, currentTheme, pointCount, currentPointsRef, fromPointsRef,
        targetPointsRef, alternatePointsRef, particlesRef, visualThemeRef, morphRef, false);
      setVisualStage(currentTheme);
      introCompleteRef.current = true;
      lastLifeStateRef.current = currentState;
      lastThemeRef.current = currentTheme;
    }, 3200);
    return () => {
      window.clearTimeout(volumeTimer);
      window.clearTimeout(bodyTimer);
    };
  }, [autoMorph, pointCount, reducedMotion, renderParams.active]);

  useEffect(() => {
    if (!autoMorph || !introCompleteRef.current) return;
    if (
      lifeState === lastLifeStateRef.current &&
      theme === lastThemeRef.current
    ) return;
    lastLifeStateRef.current = lifeState;
    lastThemeRef.current = theme;
    const targetTheme = theme;
    if (prefersReducedMotion(reducedMotion)) {
      const target = createThemePoints(targetTheme, pointCount);
      setTargetGeometry(target, targetTheme, pointCount, currentPointsRef, fromPointsRef,
        targetPointsRef, alternatePointsRef, particlesRef, visualThemeRef, morphRef, true);
      setVisualStage(targetTheme);
      redrawRef.current?.();
      return;
    }

    // A live event first loosens the old body into a horizontal digit stream;
    // those same particles then gather into the next state.
    const river = createTransitionRiverPoints(pointCount, lifeState);
    setTargetGeometry(river, visualThemeRef.current, pointCount, currentPointsRef,
      fromPointsRef, targetPointsRef, alternatePointsRef, particlesRef,
      visualThemeRef, morphRef, false);
    setVisualStage("river");
    const gatherTimer = window.setTimeout(() => {
      const target = createThemePoints(targetTheme, pointCount);
      setTargetGeometry(target, targetTheme, pointCount, currentPointsRef, fromPointsRef,
        targetPointsRef, alternatePointsRef, particlesRef, visualThemeRef, morphRef, false);
      setVisualStage(targetTheme);
    }, 1450);
    return () => window.clearTimeout(gatherTimer);
  }, [autoMorph, lifeState, pointCount, reducedMotion, theme]);

  useEffect(() => {
    const next = { lifeState, cycleId: result?.cycle_id ?? null };
    const previous = emissionSourceRef.current;
    emissionSourceRef.current = next;
    if (
      previous.lifeState !== next.lifeState ||
      (next.cycleId !== null && previous.cycleId !== next.cycleId)
    ) {
      emissionStartedRef.current = performance.now() / 1000;
      setEmission((value) => value + 1);
    }
  }, [lifeState, result?.cycle_id]);

  useEffect(() => {
    const onScroll = () => {
      const nextY = window.scrollY;
      scrollRef.current.velocity = Math.max(
        -1,
        Math.min(1, (nextY - scrollRef.current.lastY) / 72),
      );
      scrollRef.current.lastY = nextY;
    };
    scrollRef.current.lastY = window.scrollY;
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(
    () => () => {
      if (pressTimerRef.current !== null) {
        window.clearTimeout(pressTimerRef.current);
      }
    },
    [],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) {
      return;
    }

    let context: CanvasRenderingContext2D | null = null;
    try {
      context = canvas.getContext("2d");
    } catch {
      context = null;
    }
    if (!context) {
      return;
    }

    const mediaReduced =
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
    const staticMode = reducedMotion || mediaReduced;
    staticModeRef.current = staticMode;
    if (staticMode) {
      morphRef.current = 1;
    }

    let frame = 0;
    let frameId = 0;
    let last = performance.now();
    let fpsEma = 60;
    let dropped = 0;

    const draw = (now: number) => {
      const timing = measureFrameTiming(now - last, fpsEma);
      last = now;
      fpsEma = timing.fpsEma;
      if (timing.dropped) {
        dropped += 1;
      }

      if (staticMode) {
        morphRef.current = 1;
      } else {
        const motionBoost = 0.78 + paramsRef.current.particle_speed * 0.2;
        morphRef.current = Math.min(
          1,
          morphRef.current + (timing.simulationDtMs / 1000) * motionBoost,
        );
      }

      const drawCalls = drawDigitField(
        context,
        canvas,
        paramsRef.current,
        particlesRef.current,
        currentPointsRef.current,
        fromPointsRef.current,
        targetPointsRef.current,
        alternatePointsRef.current,
        activityRef,
        pointerRef.current,
        scrollRef.current,
        emissionStartedRef.current,
        lifeState,
        staticMode ? 0 : now / 1000,
        staticMode ? 1 : timing.simulationDtMs / 1000,
        morphRef.current,
        spatialTheme(visualThemeRef.current).accent,
      );

      const nextStats = {
        fps: Math.round(fpsEma),
        drawCalls,
        dropped,
      };
      onStats?.(nextStats);

      if (debug && frame % 30 === 0) {
        setStats(nextStats);
        setSnapshotHash(
          `${renderSnapshotHash(paramsRef.current, particlesRef.current)}-${theme}`,
        );
      }
      frame += 1;
      if (!staticMode && document.visibilityState !== "hidden") {
        frameId = window.requestAnimationFrame(draw);
      }
    };

    const requestStaticDraw = () => {
      if (staticMode) {
        draw(performance.now());
      }
    };
    redrawRef.current = requestStaticDraw;

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.round(rect.width * ratio));
      canvas.height = Math.max(1, Math.round(rect.height * ratio));
      requestStaticDraw();
    };
    resize();

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(resize);
      observer.observe(wrap);
    }

    const onVisibility = () => {
      window.cancelAnimationFrame(frameId);
      if (document.visibilityState === "visible") {
        last = performance.now();
        if (staticMode) {
          requestStaticDraw();
        } else {
          frameId = window.requestAnimationFrame(draw);
        }
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    if (staticMode) {
      requestStaticDraw();
    } else {
      frameId = window.requestAnimationFrame(draw);
    }

    return () => {
      redrawRef.current = null;
      window.cancelAnimationFrame(frameId);
      observer?.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [debug, lifeState, onStats, reducedMotion, theme]);

  useEffect(() => {
    redrawRef.current?.();
  }, [lifeState, result, stale, triplet]);

  const setPointer = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (staticModeRef.current) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const nextX = (event.clientX - rect.left) * ratio;
    const nextY = (event.clientY - rect.top) * ratio;
    const previous = pointerRef.current;
    pointerRef.current = {
      x: nextX,
      y: nextY,
      normalizedX: rect.width > 0 ? (event.clientX - rect.left) / rect.width - 0.5 : 0,
      normalizedY: rect.height > 0 ? (event.clientY - rect.top) / rect.height - 0.5 : 0,
      speed: Math.min(1, Math.hypot(nextX - previous.x, nextY - previous.y) / (42 * ratio)),
      active: true,
    };
    if (
      pressTimerRef.current !== null &&
      Math.hypot(
        event.clientX - pressOriginRef.current.x,
        event.clientY - pressOriginRef.current.y,
      ) > 10
    ) {
      pressMovedRef.current = true;
      cancelPress();
    }
  };

  const clearPointer = () => {
    pointerRef.current.active = false;
    pointerRef.current.speed = 0;
    cancelPress();
  };

  const cancelPress = () => {
    if (pressTimerRef.current !== null) {
      window.clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }
  };

  const emitLogo = () => {
    emissionStartedRef.current = performance.now() / 1000;
    setEmission((value) => value + 1);
  };

  const beginPress = (event: ReactPointerEvent<HTMLDivElement>) => {
    setPointer(event);
    if (
      !onRemember ||
      !event.isPrimary ||
      (event.pointerType === "mouse" && event.button !== 0)
    ) {
      return;
    }
    cancelPress();
    longPressTriggeredRef.current = false;
    pressMovedRef.current = false;
    pressOriginRef.current = { x: event.clientX, y: event.clientY };
    pressTimerRef.current = window.setTimeout(() => {
      longPressTriggeredRef.current = true;
      emitLogo();
      onRemember();
      pressTimerRef.current = null;
    }, 680);
  };

  const endPress = () => {
    cancelPress();
  };

  const rememberOnClick = () => {
    if (!onRemember) return;
    if (pressMovedRef.current) {
      pressMovedRef.current = false;
      return;
    }
    if (longPressTriggeredRef.current) {
      longPressTriggeredRef.current = false;
      return;
    }
    emitLogo();
    onRemember();
  };

  const rememberOnKey = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (!onRemember || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    emitLogo();
    onRemember();
  };

  return (
    <div
      className="digit-field"
      ref={wrapRef}
      data-life-state={lifeState}
      data-life-active={renderParams.active ? "true" : "false"}
      data-visual-stage={visualStage}
      role={onRemember ? "button" : undefined}
      tabIndex={onRemember ? 0 : undefined}
      onPointerDown={beginPress}
      onPointerMove={setPointer}
      onPointerUp={endPress}
      onPointerLeave={clearPointer}
      onPointerCancel={clearPointer}
      onClick={rememberOnClick}
      onKeyDown={rememberOnKey}
      aria-label={`${renderParams.active ? "" : "证据不足，身体未完全成形；"}${lifeStateDefinition(lifeState).label}状态的${spatialTheme(theme).name}数字生成式推断场${onRemember ? "；点击或长按保存这一刻" : ""}`}
    >
      <canvas
        ref={canvasRef}
        className="digit-field-canvas"
        role="img"
        aria-label={`由数字构成的${spatialTheme(theme).name}视觉形态；由空间代理信号驱动，非相机影像，也不表示检测到真实物体`}
      />
      <span className="life-emission" key={`${lifeState}-${emission}`} aria-hidden="true">
        <DigitSectionMark
          role={lifeStateDefinition(lifeState).role}
          seed={`${lifeState}-${result?.cycle_id ?? "ambient"}-${emission}`}
          size="medium"
        />
      </span>
      {!renderParams.active && (
        <span className="life-unknown" aria-hidden="true">
          0&nbsp;?&nbsp;0
        </span>
      )}
      {debug && (
        <div className="digit-field-debug" aria-label="数字场渲染调试信息">
          <span>fps {stats.fps}</span>
          <span>draws {stats.drawCalls}</span>
          <span>dropped {stats.dropped}</span>
          <span>hash {snapshotHash}</span>
        </div>
      )}
    </div>
  );
}

function drawDigitField(
  context: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  params: RenderParams,
  particles: Particle[],
  current: MutablePoint[],
  from: MutablePoint[],
  target: SpatialPoint[],
  alternate: SpatialPoint[],
  activityRef: { current: number },
  pointer: PointerState,
  scroll: ScrollState,
  emissionStarted: number,
  lifeState: LifeStateId,
  seconds: number,
  dt: number,
  morphProgress: number,
  accent: string,
): number {
  const width = canvas.width;
  const height = canvas.height;
  const highContrast = document.documentElement.classList.contains("high-contrast");
  const background = highContrast ? "#05070a" : "rgba(255, 255, 255, 0)";
  const inactive = highContrast ? "#637085" : "#a09c95";
  const ratio = Math.min(2, window.devicePixelRatio || 1);

  context.clearRect(0, 0, width, height);
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);
  let draws = 2;

  // A missing/unknown stream leaves only a partial shell. No previous active
  // body is retained, and the visual cannot look more certain than the data.
  const targetActivity = params.active ? 1 : 0.32;
  activityRef.current +=
    (targetActivity - activityRef.current) * Math.min(1, Math.max(0.035, dt * 3.2));
  const activity = activityRef.current;
  const easedMorph = easeInOutCubic(morphProgress);
  scroll.velocity *= Math.pow(0.08, Math.max(0, dt));

  for (let index = 0; index < current.length; index += 1) {
    const origin = from[index] ?? target[index];
    const destination = target[index] ?? origin;
    const point = current[index];
    point.x = mix(origin.x, destination.x, easedMorph);
    point.y = mix(origin.y, destination.y, easedMorph);
    point.z = mix(origin.z, destination.z, easedMorph);
    point.glyph = destination.glyph;
    point.phase = destination.phase;
    point.weight = destination.weight;
  }

  // A sparse neutral halo remains visible even without data; it contains no
  // previous shape and makes the unknown state explicit rather than blank.
  context.save();
  context.fillStyle = highContrast ? "rgba(120,167,255,0.08)" : "rgba(36,87,214,0.055)";
  for (let index = 0; index < Math.min(42, particles.length); index += 1) {
    const particle = particles[index];
    const x = width * (0.5 + Math.cos(particle.angle) * particle.radius * 0.47);
    const y = height * (0.48 + Math.sin(particle.angle) * particle.radius * 0.4);
    context.fillRect(x, y, ratio, ratio);
    draws += 1;
  }
  context.restore();

  const minSide = Math.min(width, height);
  const scaleX = Math.min(width * 0.48, height * 0.94);
  const compactViewport = width / ratio < 700;
  const scaleY = compactViewport
    ? Math.min(width * 0.72, height * 0.78)
    : Math.min(width * 0.48, height * 0.72);
  const centerX = width * 0.5;
  const centerY = height * 0.56;
  const depthFactor = 0.28 + params.z_layer_separation * 0.28;
  const motion = Math.min(1, Math.max(0, (params.particle_speed - 0.08) / 1.72));
  const pulse = Math.sin(seconds * Math.PI * 2 * params.pulse_hz);
  const activeCount = Math.round(
    current.length * (params.active ? 0.84 + params.field_density * 0.16 : 0.34),
  );
  const pointerRadius = minSide * 0.18;
  const fontSize = Math.max(8 * ratio, Math.min(14 * ratio, minSide / 43));
  context.font = `${fontSize}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  const renderStride = 1;

  for (let index = 0; index < current.length; index += 1) {
    if (index % renderStride !== 0) {
      continue;
    }
    const point = current[index];
    const alternatePoint = alternate[index] ?? point;
    const particle = particles[index % particles.length];
    const scatterX = Math.cos(particle.angle) * particle.radius * 1.66;
    const scatterY = Math.sin(particle.angle) * particle.radius * 1.3;
    const scatterZ = Math.sin(particle.phase) * 0.4;
    const coherence = params.active
      ? Math.max(0.66, 1 - params.edge_diffusion * 0.34)
      : 1;
    const bodyFormation = activity * coherence;
    const candidateBlend = index % 2 === 0 ? 0 : params.disagreement_phase;
    const candidateX = mix(point.x, alternatePoint.x, candidateBlend);
    const candidateY = mix(point.y, alternatePoint.y, candidateBlend);
    const candidateZ = mix(point.z, alternatePoint.z, candidateBlend);
    const disagreementSplit =
      (index % 2 === 0 ? -1 : 1) * params.disagreement_phase * 0.12;
    const shapedX = mix(scatterX, candidateX + disagreementSplit, bodyFormation);
    const shapedY = mix(scatterY, candidateY, bodyFormation);
    const shapedZ = mix(scatterZ, candidateZ - disagreementSplit * 0.42, bodyFormation);
    const drift =
      Math.sin(seconds * (0.24 + motion * 1.3) + point.phase) *
      motion *
      0.035 *
      activity;
    const expression = lifeExpression(lifeState, index, point.phase, seconds, pulse, motion);
    const breathing = expression.scale * (1 + pulse * (0.007 + motion * 0.02) * activity);
    let x =
      centerX +
      (shapedX + shapedZ * depthFactor + drift + expression.x) *
        scaleX *
        breathing;
    let y =
      centerY +
      (-shapedY + shapedZ * 0.17 + drift * 0.35 + expression.y) *
        scaleY *
        breathing;

    y += scroll.velocity * Math.sin(point.phase + index * 0.07) * 46 * ratio;

    if (pointer.active && activity > 0.04) {
      x += pointer.normalizedX * shapedY * minSide * 0.085;
      y += pointer.normalizedY * shapedX * minSide * 0.04;
      const dx = x - pointer.x;
      const dy = y - pointer.y;
      const distance = Math.hypot(dx, dy);
      if (distance > 0 && distance < pointerRadius) {
        const force =
          Math.pow(1 - distance / pointerRadius, 2) *
          (12 + motion * 20 + pointer.speed * 16) *
          ratio;
        x += (dx / distance) * force;
        y += (dy / distance) * force;
      }
    }

    const visible = index < activeCount;
    const baseAlpha = params.active
      ? visible
        ? 0.22 + params.saturation * 0.68
        : 0.065
      : visible
        ? 0.36
        : 0.035;
    const emissionAge = seconds - emissionStarted;
    const emissionStrength =
      emissionAge >= 0 && emissionAge <= 2.2 ? 1 - emissionAge / 2.2 : 0;
    const detaching =
      emissionStrength > 0 && index % 9 === 0 && point.x > -0.28;
    const alpha = Math.max(
      0.035,
      baseAlpha *
        (0.24 + activity * 0.76) *
        point.weight *
        (detaching ? 1 - emissionStrength * 0.84 : 1),
    );
    context.globalAlpha = alpha;
    const rainbowIndex =
      (index +
        (index % 2 === 0 ? 0 : Math.round(params.disagreement_phase * 3)) +
        Math.floor(seconds * (0.35 + motion * 0.8)) +
        Math.floor(point.phase * 2)) %
      RAINBOW_COLORS.length;
    context.fillStyle =
      activity > 0.08
        ? highContrast
          ? rainbowIndex % 2 === 0
            ? "#9fc2ff"
            : "#f6b3ff"
          : lifeState === "doubt" && index % 5 === 0
            ? accent
            : RAINBOW_COLORS[(rainbowIndex + RAINBOW_COLORS.length) % RAINBOW_COLORS.length]
        : inactive;
    context.fillText(activity > 0.08 ? point.glyph : index % 3 === 0 ? "0" : "·", x, y);
    draws += 1;
  }
  context.globalAlpha = 1;

  draws += drawDigitRiver(
    context,
    width,
    height,
    particles,
    seconds,
    scroll.velocity,
    ratio,
    activity,
  );

  if (!params.active) {
    context.fillStyle = highContrast ? "rgba(5,7,10,0.12)" : "rgba(255,255,255,0.08)";
    context.fillRect(0, 0, width, height);
    draws += 1;
  }

  return draws;
}

function lifeExpression(
  state: LifeStateId,
  index: number,
  phase: number,
  seconds: number,
  pulse: number,
  motion: number,
): { x: number; y: number; scale: number } {
  switch (state) {
    case "construct":
      return { x: 0, y: Math.sin(seconds * 0.42 + phase) * 0.004, scale: 1 };
    case "flow":
      return {
        x: Math.sin(seconds * (0.9 + motion) + phase) * (0.024 + motion * 0.035),
        y: Math.cos(seconds * 0.55 + phase) * 0.012,
        scale: 1 + pulse * 0.01,
      };
    case "rest":
      return { x: 0, y: Math.sin(seconds * 0.2 + phase) * 0.004, scale: 1 + pulse * 0.006 };
    case "grow":
      return {
        x: Math.sin(seconds * 0.32 + phase) * 0.012,
        y: Math.sin(seconds * 0.27 + phase + index * 0.01) * 0.018,
        scale: 1.025 + pulse * 0.012,
      };
    case "sound":
      return {
        x: Math.sin(seconds * 0.58 + phase) * 0.013,
        y: Math.cos(seconds * 0.72 + phase) * 0.022,
        scale: 1 + pulse * 0.009,
      };
    case "doubt":
      return {
        x: (index % 2 === 0 ? -1 : 1) * 0.024 + Math.sin(seconds * 1.4 + phase) * 0.012,
        y: Math.cos(seconds * 1.1 + phase) * 0.01,
        scale: 0.96 + pulse * 0.006,
      };
    case "echo":
      return {
        x: Math.cos(seconds * 0.44 + phase) * 0.022,
        y: Math.sin(seconds * 0.44 + phase) * 0.018,
        scale: 1.018 + pulse * 0.012,
      };
  }
}

function drawDigitRiver(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
  particles: readonly Particle[],
  seconds: number,
  scrollVelocity: number,
  ratio: number,
  activity: number,
): number {
  const count = Math.min(96, particles.length);
  context.save();
  context.font = `${Math.max(7 * ratio, Math.min(11 * ratio, height / 72))}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  for (let index = 0; index < count; index += 1) {
    const particle = particles[index];
    const progress = wrap01(
      index / count + seconds * (0.008 + particle.speedFactor * 0.003) + scrollVelocity * 0.08,
    );
    const x = progress * width;
    const y = height * 0.92 + Math.sin(seconds * 0.35 + particle.phase) * 5 * ratio;
    context.globalAlpha = (0.08 + activity * 0.22) + (index % 5) * 0.035;
    context.fillStyle = RAINBOW_COLORS[index % RAINBOW_COLORS.length];
    context.fillText(String((index * 7 + 3) % 10), x, y);
  }
  context.restore();
  return count;
}

function wrap01(value: number): number {
  return ((value % 1) + 1) % 1;
}

function setTargetGeometry(
  next: SpatialPoint[],
  nextTheme: SpatialThemeId,
  pointCount: number,
  currentRef: { current: MutablePoint[] },
  fromRef: { current: MutablePoint[] },
  targetRef: { current: SpatialPoint[] },
  alternateRef: { current: SpatialPoint[] },
  particlesRef: { current: Particle[] },
  visualThemeRef: { current: SpatialThemeId },
  morphRef: { current: number },
  immediate: boolean,
): void {
  if (currentRef.current.length !== next.length) {
    currentRef.current = clonePoints(next);
  }
  fromRef.current = clonePoints(
    currentRef.current.length === next.length ? currentRef.current : next,
  );
  targetRef.current = next;
  alternateRef.current = createThemePoints(alternateTheme(nextTheme), pointCount);
  particlesRef.current = seedParticles(
    VISUAL_SEED + nextTheme.charCodeAt(0) * 17,
    pointCount,
  );
  visualThemeRef.current = nextTheme;
  if (immediate) {
    currentRef.current = clonePoints(next);
    fromRef.current = clonePoints(next);
    morphRef.current = 1;
  } else {
    morphRef.current = 0;
  }
}

function alternateTheme(theme: SpatialThemeId): SpatialThemeId {
  switch (theme) {
    case "floorplan":
    case "volume":
      return "atrium";
    case "lounge":
      return "sofa";
    case "sofa":
      return "lounge";
    case "floor_lamp":
      return "atrium";
    case "atrium":
      return "floor_lamp";
    case "passage":
      return "abstract_presence";
    case "abstract_presence":
      return "passage";
    case "garden":
      return "atrium";
    case "studio":
      return "volume";
  }
}

function createTransitionRiverPoints(
  count: number,
  state: LifeStateId,
): SpatialPoint[] {
  const salt = state.charCodeAt(0) + state.charCodeAt(state.length - 1);
  return Array.from({ length: count }, (_, index) => {
    const lane = ((index * 5 + salt) % 7) - 3;
    const progress = ((index * 37 + salt * 11) % count) / Math.max(1, count - 1);
    return {
      x: -1.08 + progress * 2.16,
      y: lane * 0.055 + Math.sin(progress * Math.PI * 4 + salt) * 0.035,
      z: (((index * 17 + salt) % 29) / 28 - 0.5) * 0.2,
      glyph: String((index * 7 + salt) % 10),
      phase: progress * Math.PI * 2,
      weight: 0.76 + ((index + salt) % 5) * 0.08,
    };
  });
}

function prefersReducedMotion(setting: boolean): boolean {
  return (
    setting ||
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true
  );
}

function clonePoints(points: readonly SpatialPoint[]): MutablePoint[] {
  return points.map((point) => ({ ...point }));
}

function mix(start: number, end: number, progress: number): number {
  return start + (end - start) * Math.max(0, Math.min(1, progress));
}

function easeInOutCubic(value: number): number {
  const progress = Math.max(0, Math.min(1, value));
  return progress < 0.5
    ? 4 * progress * progress * progress
    : 1 - Math.pow(-2 * progress + 2, 3) / 2;
}
