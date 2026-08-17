"""Deterministic mock fixture builders shared by the generators and tests."""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, timedelta

from .actions import AgentActionDecision
from .council import (
    AgentChallenge,
    AgentClaim,
    AgreementSummary,
    AnalysisStep,
    CouncilCallRecord,
    CouncilCycleDetail,
    CouncilResult,
    PolicyRejection,
    Provenance,
    ReadingLayer,
    SkepticAssessment,
    SoundConsensusMotion,
    SpatialLifeInteraction,
    SpecialistPresentation,
    SystematicReading,
)
from .evidence import (
    CalibrationSummary,
    EvidencePacket,
    EvidenceValue,
    QualitySummary,
    TopologySummary,
    WindowSummary,
)
from .frames import CsiQuality, NormalizedCsiFrame, SourceManifest
from .signals import (
    DepthProbabilities,
    DepthZone,
    FeatureWindow,
    LinkFeatures,
    MotionSignal,
    OccupancyDensity,
    OccupancyProbabilities,
    SignalTriplet,
)

SEED = 0xC5F15EED
SESSION_ID = "session-mock-fixed-v1"
PROFILE_ID = "demo_room_v1"
RAW_REF = "raw://fixtures/walk_through/raw.csi.zst"
BASE_TIME = datetime(2026, 8, 6, 8, 0, 0, tzinfo=UTC)


def fake_hash(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def build_frames() -> list[NormalizedCsiFrame]:
    rng = random.Random(SEED)
    host_base_ns = int(BASE_TIME.timestamp() * 1_000_000_000)
    frames: list[NormalizedCsiFrame] = []
    for link_index, link_id in enumerate(("rx-a", "rx-b")):
        for seq in range(12):
            frames.append(
                NormalizedCsiFrame(
                    schema_version="1.0.0",
                    session_id=SESSION_ID,
                    source_mode="mock",
                    link_id=link_id,
                    rx_id=link_id,
                    tx_id_hash=fake_hash("tx-fixed"),
                    seq=seq,
                    device_ts_us=seq * 10_000,
                    host_ts_ns=(
                        host_base_ns + link_index * 1_000_000 + seq * 100_000
                    ),
                    channel=6,
                    bandwidth_mhz=20,
                    rssi_dbm=round(rng.uniform(-70.0, -55.0), 2),
                    noise_floor_dbm=round(rng.uniform(-100.0, -90.0), 2),
                    rate=54,
                    secondary_channel=None,
                    ltf_mode="HT",
                    first_word_invalid=False,
                    csi_iq=[rng.randint(-128, 127) for _ in range(128)],
                    quality=CsiQuality(
                        parse_ok=True,
                        sequence_gap=0,
                        timestamp_monotonic=True,
                        notes=[],
                    ),
                )
            )
    return frames


def _link_features(
    *,
    packet_coverage: float,
    correlation: float,
    temporal_rms: float,
) -> LinkFeatures:
    return LinkFeatures(
        packet_coverage=packet_coverage,
        subcarrier_coverage=0.98,
        amplitude_median=[0.9, 0.91, 0.92, 0.9, 0.88, 0.87],
        amplitude_mad=[0.01, 0.012, 0.011, 0.013, 0.012, 0.01],
        temporal_diff_rms=temporal_rms,
        spectral_band_energy={"0-1Hz": 0.02, "1-4Hz": 0.01, "4-8Hz": 0.005},
        shape_correlation_to_baseline=correlation,
        quality_flags=[],
    )


def build_windows() -> list[FeatureWindow]:
    calm = FeatureWindow(
        schema_version="1.0.0",
        session_id=SESSION_ID,
        window_id="window-0001-calm",
        source_mode="mock",
        start_ns=0,
        end_ns=2_000_000_000,
        stride_ms=250,
        topology_hash=fake_hash("topology-two-rx"),
        calibration_profile_id=PROFILE_ID,
        links={
            "rx-a": _link_features(packet_coverage=0.99, correlation=0.98, temporal_rms=0.008),
            "rx-b": _link_features(packet_coverage=0.98, correlation=0.97, temporal_rms=0.009),
        },
        paired_packet_coverage=0.95,
        feature_version="features-v1",
    )
    moving = calm.model_copy(
        update={
            "window_id": "window-0002-moving",
            "start_ns": 2_250_000_000,
            "end_ns": 4_250_000_000,
            "links": {
                "rx-a": _link_features(packet_coverage=0.97, correlation=0.55, temporal_rms=0.31),
                "rx-b": _link_features(packet_coverage=0.96, correlation=0.61, temporal_rms=0.27),
            },
            "paired_packet_coverage": 0.93,
        }
    )
    return [calm, moving]


def _triplet_idle() -> SignalTriplet:
    return SignalTriplet(
        schema_version="1.0.0",
        session_id=SESSION_ID,
        window_id="window-0001-calm",
        source_mode="mock",
        started_at=BASE_TIME,
        ended_at=BASE_TIME + timedelta(seconds=2),
        motion=MotionSignal(value=0.05, state="idle", confidence=0.9),
        occupancy_density=OccupancyDensity(
            probabilities=OccupancyProbabilities(low=0.8, medium=0.15, high=0.03, unknown=0.02),
            state="low",
            confidence=0.85,
        ),
        depth_zone=DepthZone(
            probabilities=DepthProbabilities(near=0.1, mid=0.7, far=0.15, unknown=0.05),
            state="mid",
            confidence=0.7,
        ),
        sensor_confidence_cap=0.9,
        evidence_refs=[f"{RAW_REF}#window-0001"],
        status="ok",
    )


def _triplet_moving() -> SignalTriplet:
    return SignalTriplet(
        schema_version="1.0.0",
        session_id=SESSION_ID,
        window_id="window-0002-moving",
        source_mode="mock",
        started_at=BASE_TIME + timedelta(seconds=2.25),
        ended_at=BASE_TIME + timedelta(seconds=4.25),
        motion=MotionSignal(value=0.7, state="moving", confidence=0.8),
        occupancy_density=OccupancyDensity(
            probabilities=OccupancyProbabilities(low=0.1, medium=0.75, high=0.1, unknown=0.05),
            state="medium",
            confidence=0.75,
        ),
        depth_zone=DepthZone(
            probabilities=DepthProbabilities(near=0.72, mid=0.2, far=0.05, unknown=0.03),
            state="near",
            confidence=0.68,
        ),
        sensor_confidence_cap=0.8,
        evidence_refs=[f"{RAW_REF}#window-0002"],
        status="ok",
    )


def _triplet_unknown() -> SignalTriplet:
    return SignalTriplet(
        schema_version="1.0.0",
        session_id=SESSION_ID,
        window_id="window-0003-insufficient",
        source_mode="mock",
        started_at=BASE_TIME + timedelta(seconds=4.5),
        ended_at=BASE_TIME + timedelta(seconds=6.5),
        motion=MotionSignal(value=0.0, state="unknown", confidence=0.2),
        occupancy_density=OccupancyDensity(
            probabilities=OccupancyProbabilities(low=0.0, medium=0.0, high=0.0, unknown=1.0),
            state="unknown",
            confidence=0.2,
        ),
        depth_zone=DepthZone(
            probabilities=DepthProbabilities(near=0.0, mid=0.0, far=0.0, unknown=1.0),
            state="unknown",
            confidence=0.2,
        ),
        sensor_confidence_cap=0.2,
        evidence_refs=[f"{RAW_REF}#window-0003"],
        status="insufficient_signal",
    )


def build_triplets() -> list[SignalTriplet]:
    return [_triplet_idle(), _triplet_moving(), _triplet_unknown()]


def build_evidence(triplet: SignalTriplet, window: FeatureWindow) -> EvidencePacket:
    manifest = SourceManifest(
        schema_version="wifi-source.v1",
        session_id=SESSION_ID,
        source_mode="mock",
        session_started_at=BASE_TIME,
        link_ids=["rx-a", "rx-b"],
        firmware_versions={"csi_tx": "0.0.0-mock", "csi_rx": "0.0.0-mock"},
        topology_hash=fake_hash("topology-two-rx"),
        replay_ref="replay://fixtures/walk_through",
    )
    return EvidencePacket.create(
        schema_version="wifi-evidence.v1",
        session_id=SESSION_ID,
        cycle_id="cycle-0001",
        sequence=1,
        captured_at=BASE_TIME + timedelta(seconds=4.3),
        source_manifest=manifest,
        window_summary=WindowSummary(
            window_id=window.window_id,
            start_ns=window.start_ns,
            end_ns=window.end_ns,
            stride_ms=window.stride_ms,
            links=window.links,
            paired_packet_coverage=window.paired_packet_coverage,
        ),
        topology=TopologySummary(
            topology_hash=manifest.topology_hash,
            link_ids=["rx-a", "rx-b"],
            degraded_links=[],
            depth_output_allowed=True,
        ),
        calibration=CalibrationSummary(
            calibration_profile_id=PROFILE_ID,
            profile_hash=fake_hash(PROFILE_ID),
            calibrated_at=BASE_TIME - timedelta(hours=1),
            room_conditions="empty room, desks at 3 m",
        ),
        quality=QualitySummary(
            overall_status="ok",
            packet_coverage=0.96,
            link_health={"rx-a": "ok", "rx-b": "ok"},
            quality_flags=[],
        ),
        signals=triplet,
        evidence_index={
            "signals/motion/value": EvidenceValue(
                path="signals/motion/value",
                value=triplet.motion.value,
                unit="ratio",
                description="window motion intensity proxy",
            ),
            "signals/motion/state": EvidenceValue(
                path="signals/motion/state",
                value=triplet.motion.state,
                description="motion state",
            ),
            "signals/occupancy/state": EvidenceValue(
                path="signals/occupancy/state",
                value=triplet.occupancy_density.state,
                description="occupancy density proxy state",
            ),
            "signals/depth/state": EvidenceValue(
                path="signals/depth/state",
                value=triplet.depth_zone.state,
                description="depth zone proxy state",
            ),
            "quality/packet_coverage": EvidenceValue(
                path="quality/packet_coverage",
                value=0.96,
                unit="ratio",
                description="paired packet coverage",
            ),
            "quality/overall_status": EvidenceValue(
                path="quality/overall_status",
                value=triplet.status,
                description="overall quality status",
            ),
            "quality/paired_coverage": EvidenceValue(
                path="quality/paired_coverage",
                value=0.95,
                unit="ratio",
                description="paired packet coverage",
            ),
            "sensor/sensor_confidence_cap": EvidenceValue(
                path="sensor/sensor_confidence_cap",
                value=triplet.sensor_confidence_cap,
                unit="ratio",
                description="sensor confidence cap",
            ),
            "topology/depth_output_allowed": EvidenceValue(
                path="topology/depth_output_allowed",
                value=True,
                description="depth output allowed",
            ),
        },
        raw_ref=RAW_REF,
    )


def build_evidence_packets() -> list[EvidencePacket]:
    return [build_evidence(build_triplets()[1], build_windows()[1])]


def build_agent_claims() -> list[AgentClaim]:
    packet = build_evidence_packets()[0]
    ref = f"evidence://{packet.evidence_hash}/signals/motion/value"
    return [
        AgentClaim(
            schema_version="agent-claim.v1",
            claim_id="claim-0001",
            cycle_id=packet.cycle_id,
            agent_id="agent-feng_shui-0001",
            agent_version="mock-council.v1",
            role="feng_shui",
            lens="metaphor",
            kind="observation",
            state="proposed",
            proposition="以[qi (气) as environmental flow]视角解读当前空间意象(隐喻解读). ",
            stance="supports",
            evidence_refs=[ref, f"evidence://{packet.evidence_hash}/signals/motion/state"],
            sources=["https://pmc.ncbi.nlm.nih.gov/articles/PMC10558748/"],
            analysis_steps=[
                AnalysisStep(
                    step_id="observe",
                    phase="observe",
                    title="观察信号",
                    text=(
                        "读取证据包标量: motion=micro_motion, "
                        "occupancy=low, depth=near; 仅引用标量,未读取 raw CSI。"
                    ),
                    evidence_refs=[
                        f"evidence://{packet.evidence_hash}/signals/motion/state",
                        f"evidence://{packet.evidence_hash}/signals/occupancy/state",
                        f"evidence://{packet.evidence_hash}/signals/depth/state",
                    ],
                ),
                AnalysisStep(
                    step_id="retrieve",
                    phase="retrieve",
                    title="检索知识库",
                    text=(
                        "从知识库命中主概念『qi (气) as environmental flow』"
                        "(Empirical and quantitative studies of Feng Shui); "
                        "备用视角『藏风聚气』。"
                    ),
                    evidence_refs=[
                        f"evidence://{packet.evidence_hash}/quality/overall_status"
                    ],
                ),
                AnalysisStep(
                    step_id="map",
                    phase="map",
                    title="意象映射",
                    text=(
                        "motion_micro_motion -> 气动; occupancy_low -> 气散/开阔; "
                        "depth_near -> 明堂近"
                    ),
                    evidence_refs=[
                        f"evidence://{packet.evidence_hash}/signals/motion/state"
                    ],
                ),
                AnalysisStep(
                    step_id="reason",
                    phase="reason",
                    title="推理",
                    text=(
                        "把三种标量读成同一场气的三种侧面:流、聚、远近。"
                        "读法成立的前提是标定与拓扑未变。"
                    ),
                    evidence_refs=[
                        f"evidence://{packet.evidence_hash}/quality/overall_status"
                    ],
                ),
                AnalysisStep(
                    step_id="conclude",
                    phase="conclude",
                    title="结论",
                    text=(
                        "收敛为命题: 以[qi (气) as environmental flow]视角解读"
                        "当前空间意象(隐喻解读)。"
                    ),
                    evidence_refs=[
                        f"evidence://{packet.evidence_hash}/signals/motion/state"
                    ],
                ),
            ],
            systematic_reading=SystematicReading(
                headline="以[qi (气) as environmental flow]视角解读当前空间意象(隐喻解读)。",
                scene_sketch=(
                    "如果此刻有风,它会在近前慢慢转向;空气带着疏朗的密度,"
                    "安静得像一场刚醒的呼吸。气不急着聚,也不急着散,"
                    "整个房间像一张还没落定的棋局。"
                ),
                layers=[
                    ReadingLayer(
                        signal="motion",
                        state="micro_motion",
                        metaphor="气动",
                        explanation=(
                            "气流意象读作「微动」:运动标量描述的是代理变化,"
                            "不是任何个体的具体动作。"
                        ),
                    ),
                    ReadingLayer(
                        signal="occupancy",
                        state="low",
                        metaphor="气散/开阔",
                        explanation=(
                            "气局意象读作「疏朗」:占用密度描述遮挡与空间充盈度,"
                            "不是人数。"
                        ),
                    ),
                    ReadingLayer(
                        signal="depth",
                        state="near",
                        metaphor="明堂近",
                        explanation=(
                            "明堂远近读作「近前」:纵深是相对层级,不是米制距离。"
                        ),
                    ),
                ],
                narrative=(
                    "按青禾的读法,这间房的气是缓的、散的、近的:"
                    "气流意象读作「微动」,气局意象读作「疏朗」,"
                    "明堂远近读作「近前」。这不是占卜,也不是对命运的判断;"
                    "只是把标量读成一场呼吸。"
                ),
                boundary_notes=[
                    "气、明堂、吉凶都是文化隐喻,不代表真实气流或运势。",
                    "本解读不产生任何测量值,也不改变传感器置信。",
                ],
                multimodal_hints=[
                    "若接入声学模态,可对照环境声级与“气动”意象是否一致,但需独立标定。",
                    "若接入温湿度/光照模态,可验证风感意象与通风条件的相关性;仍属隐喻对照。",
                ],
            ),
            presentation=SpecialistPresentation(
                role="feng_shui",
                contribution="space_flow",
                contribution_label="看见空间的流",
                state="dispersing",
                state_label="散",
                analysis=(
                    "活动轻微变化、充盈代理偏低、相对纵深偏近;"
                    "此刻的流读作「散」。这是文化叙事隐喻。"
                ),
                effect="scatter",
            ),
            assumptions=["标定 profile 与当前拓扑匹配"],
            alternative_explanations=["无线干扰或结构变化也可能形成此意象"],
            falsification_test="更换标定/拓扑后若意象不重现则推翻. ",
            reasoning_summary="仅引用证据包标量,按知识库概念做隐喻映射. ",
        ),
        AgentClaim(
            schema_version="agent-claim.v1",
            claim_id="claim-0002",
            cycle_id=packet.cycle_id,
            agent_id="agent-architecture-0002",
            agent_version="mock-council.v1",
            role="architecture",
            lens="metaphor",
            kind="limitation",
            state="proposed",
            proposition="空间层级为相对代理,不提供米制距离(隐喻解读). ",
            stance="neutral",
            evidence_refs=[f"evidence://{packet.evidence_hash}/signals/depth/state"],
            sources=["https://cup.columbia.edu/book/proxemics-and-the-architecture-of-social-interaction/9781941"],
            presentation=SpecialistPresentation(
                role="architecture",
                contribution="space_form",
                contribution_label="看见空间的形",
                state="expanding",
                state_label="展开",
                analysis=(
                    "当前房间的充盈代理偏低、相对纵深偏近;"
                    "空间边界读作「展开」。"
                ),
                effect="expand",
            ),
            assumptions=[],
            alternative_explanations=[],
            falsification_test="无可证伪性要求(限制性说明). ",
            reasoning_summary="重申隐喻与测量边界. ",
        ),
    ]


def build_agent_challenges() -> list[AgentChallenge]:
    packet = build_evidence_packets()[0]
    claim = build_agent_claims()[0]
    return [
        AgentChallenge(
            schema_version="agent-challenge.v1",
            challenge_id="challenge-0001",
            target_claim_id=claim.claim_id,
            challenger_agent_id="agent-skeptic-0001",
            category="confound",
            proposed_severity="material",
            statement="干扰注入可能伪造“气动/流通”意象,而非真实环境变化. ",
            evidence_refs=[f"evidence://{packet.evidence_hash}/quality/packet_coverage"],
            resolution_test="对照无实体运动但有干扰注入的录制,若扰动仍升高则支持干扰假说. ",
            status="open",
            assessment=SkepticAssessment(
                evidence_status="limited",
                evidence_label="证据有限",
                withhold_judgment=True,
                rationale="干扰注入仍可能形成相似代理组合。",
                next_validation="对照无实体运动但有干扰注入的下一周期。",
            ),
        )
    ]


def build_policy_rejections() -> list[PolicyRejection]:
    packet = build_evidence_packets()[0]
    return [
        PolicyRejection(
            schema_version="policy-rejection.v1",
            rejection_id="rejection-0001",
            cycle_id=packet.cycle_id,
            target_id="claim-bad-0001",
            agent_id="agent-feng_shui-bad",
            role="feng_shui",
            reason_code="unknown_evidence_ref",
            detail="evidence ref 不在当前 evidence_hash 中",
            rejected_at=BASE_TIME + timedelta(seconds=5),
        )
    ]


def build_council_calls() -> list[CouncilCallRecord]:
    packet = build_evidence_packets()[0]
    return [
        CouncilCallRecord(
            schema_version="council-call.v1",
            call_id="call-0001",
            cycle_id=packet.cycle_id,
            role="feng_shui",
            phase="propose",
            model="mock",
            prompt_version="council-prompt.v1",
            evidence_hash=packet.evidence_hash,
            status="ok",
            latency_ms=1,
            attempts=1,
        )
    ]


def build_agent_action_decisions() -> list[AgentActionDecision]:
    packet = build_evidence_packets()[0]
    return [
        AgentActionDecision(
            schema_version="agent-action-decision.v1",
            decision_id=f"action-{packet.session_id}-{packet.cycle_id}",
            session_id=packet.session_id,
            cycle_id=packet.cycle_id,
            evidence_hash=packet.evidence_hash,
            decided_at=BASE_TIME + timedelta(seconds=5),
            source_mode="mock",
            quality_status="ok",
            quality_flags=[],
            action_type="ambient_light_preview",
            execution_status="simulated_preview",
            target="inference_field_preview",
            reason_code="simulated_source_preview",
            explanation="仅在推断场中模拟环境光反应,不触发外部设备。",
            evidence_refs=[
                f"evidence://{packet.evidence_hash}/quality/overall_status",
                f"evidence://{packet.evidence_hash}/sensor/sensor_confidence_cap",
            ],
            decision_confidence=packet.signals.depth_zone.confidence,
            sensor_confidence_cap=packet.signals.sensor_confidence_cap,
        )
    ]


def build_council_results() -> list[CouncilResult]:
    packet = build_evidence_packets()[0]
    claims = build_agent_claims()
    action_decision = build_agent_action_decisions()[0]
    return [
        CouncilResult(
            schema_version="council-result.v1",
            cycle_id=packet.cycle_id,
            evidence_hash=packet.evidence_hash,
            status="supported",
            headline="多视角受限解读",
            summary="专家主张引用同一证据包,无未解决质疑. ",
            accepted_claim_ids=[claims[0].claim_id],
            unresolved_challenge_ids=[],
            alternatives=["无线干扰或结构变化也可能形成此意象"],
            limitations=["隐喻解读不等于测量;代理信号,非影像或人数"],
            sensor_confidence_cap=packet.signals.sensor_confidence_cap,
            model_support=packet.signals.motion.confidence,
            display_confidence=packet.signals.motion.confidence,
            interpretation_agreement=AgreementSummary(
                participants=2,
                supporting=1,
                contradicting=0,
                unresolved_challenges=0,
                agreement_ratio=0.5,
            ),
            visual_parameters={"palette": "proxy_blue", "shape": "rings"},
            audio_parameters={"enabled": "false", "tone": "neutral"},
            sound_motion=SoundConsensusMotion(
                rhythm="缓拍",
                pitch="低",
                distance="近",
                thickness="薄",
                synchrony="部分同步",
            ),
            life_interaction=SpatialLifeInteraction(
                state="expanding",
                state_label="正在展开",
                message="我正在展开:活动只有轻微变化,房间边界偏松,层次偏近。",
                wish="如果这正是你想记住的时刻,请保存我并与下一周期对照。",
                effect="expand",
            ),
            action_decision=action_decision,
            provenance=Provenance(
                contracts_version="1.0.0",
                features_version="features-v2",
                calibration_profile_id=PROFILE_ID,
                agent_versions={"feng_shui": "mock-council.v1"},
                models={"feng_shui": "mock"},
                policy_version="policy-v1",
                generated_at=BASE_TIME + timedelta(seconds=5),
            ),
        )
    ]


def build_council_cycle_details() -> list[CouncilCycleDetail]:
    packet = build_evidence_packets()[0]
    result = build_council_results()[0]
    return [
        CouncilCycleDetail(
            schema_version="council-cycle.v1",
            cycle_id=packet.cycle_id,
            evidence_hash=packet.evidence_hash,
            status=result.status,
            phase="commit",
            started_at=BASE_TIME + timedelta(seconds=4.4),
            finished_at=BASE_TIME + timedelta(seconds=5.0),
            deadline_s=15.0,
            claims=build_agent_claims(),
            challenges=build_agent_challenges(),
            rejections=[],
            calls=build_council_calls(),
            result=result,
        )
    ]
