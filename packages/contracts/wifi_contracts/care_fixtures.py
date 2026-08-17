"""Deterministic fictional ageing-in-place scenario used by API and fixtures."""

# The strings are user-facing Chinese copy; full-width punctuation is intentional.
# ruff: noqa: RUF001

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .care import (
    CareEventType,
    CareInputSource,
    CareMomentEvidenceCore,
    CareMomentFacts,
    CareMomentKey,
    CareObservationSource,
    CareObservationValue,
    CareSuggestionKind,
    CareSuggestionReasonCode,
    CareSuggestionTarget,
    SimulatedActivityEntry,
    SimulatedCareMoment,
    SimulatedCareScenario,
    SimulatedCareSuggestion,
    SimulatedExternalObservation,
    SimulatedHomeLayout,
    SimulatedHomeZone,
    SimulatedResidentProfile,
    canonical_care_evidence_hash,
)
from .signals import (
    DepthProbabilities,
    DepthState,
    DepthZone,
    MotionSignal,
    MotionState,
    OccupancyDensity,
    OccupancyProbabilities,
    OccupancyState,
    SignalTriplet,
)

CARE_TIMEZONE = timezone(timedelta(hours=8))
CARE_DAY_START = datetime(2026, 8, 13, 6, 0, tzinfo=CARE_TIMEZONE)
CARE_SCENARIO_ID = "ageing-in-place-fictional-day-v1"


def _at(hours: int, minutes: int, *, next_day: bool = False) -> datetime:
    moment = CARE_DAY_START.replace(hour=hours, minute=minutes)
    return moment + (timedelta(days=1) if next_day else timedelta())


def _external_observations(
    *,
    event_id: str,
    zone_id: str,
    occurred_at: datetime,
    values: list[tuple[CareObservationSource, CareObservationValue]],
) -> list[SimulatedExternalObservation]:
    return [
        SimulatedExternalObservation(
            observation_id=f"observation-{event_id}-{source}",
            simulation_only=True,
            source=source,
            observed_at=occurred_at - timedelta(seconds=30),
            valid_until=occurred_at + timedelta(minutes=2),
            zone_id=zone_id,
            quality_status="ok",
            session_id=CARE_SCENARIO_ID,
            event_id=event_id,
            value=value,
        )
        for source, value in values
    ]


def _proxy_triplet(
    *,
    event_id: str,
    ended_at: datetime,
    sensor_cap: float,
    motion_value: float,
    motion_state: MotionState,
    motion_confidence: float,
    occupancy_probabilities: tuple[float, float, float, float],
    occupancy_state: OccupancyState,
    occupancy_confidence: float,
    depth_probabilities: tuple[float, float, float, float],
    depth_state: DepthState,
    depth_confidence: float,
) -> SignalTriplet:
    """Build one hash-bound final proxy window for a simulated care event."""
    window_id = f"{event_id}-proxy-final"
    occupancy_low, occupancy_medium, occupancy_high, occupancy_unknown = (
        occupancy_probabilities
    )
    depth_near, depth_mid, depth_far, depth_unknown = depth_probabilities
    return SignalTriplet(
        schema_version="1.0.0",
        session_id=CARE_SCENARIO_ID,
        window_id=window_id,
        source_mode="mock",
        started_at=ended_at - timedelta(milliseconds=250),
        ended_at=ended_at,
        motion=MotionSignal(
            value=motion_value,
            state=motion_state,
            confidence=motion_confidence,
        ),
        occupancy_density=OccupancyDensity(
            probabilities=OccupancyProbabilities(
                low=occupancy_low,
                medium=occupancy_medium,
                high=occupancy_high,
                unknown=occupancy_unknown,
            ),
            state=occupancy_state,
            confidence=occupancy_confidence,
        ),
        depth_zone=DepthZone(
            probabilities=DepthProbabilities(
                near=depth_near,
                mid=depth_mid,
                far=depth_far,
                unknown=depth_unknown,
            ),
            state=depth_state,
            confidence=depth_confidence,
        ),
        sensor_confidence_cap=sensor_cap,
        evidence_refs=[
            f"fixture://{CARE_SCENARIO_ID}/proxy/{window_id}",
        ],
        status="ok",
    )


def _evidence_core(
    *,
    event_id: str,
    timeline_entry_id: str,
    event_type: CareEventType,
    occurred_at: datetime,
    zone_id: str,
    duration: float,
    threshold: float,
    sources: list[CareInputSource],
    sensor_cap: float,
    observations: list[tuple[CareObservationSource, CareObservationValue]],
    proxy_triplet: SignalTriplet,
) -> CareMomentEvidenceCore:
    return CareMomentEvidenceCore(
        schema_version="care-evidence-core.v2",
        event_id=event_id,
        timeline_entry_id=timeline_entry_id,
        event_type=event_type,
        occurred_at=occurred_at,
        zone_id=zone_id,
        observed_duration_min=duration,
        threshold_min=threshold,
        threshold_comparison="exceeded" if duration > threshold else "within",
        input_sources=sources,
        external_observations=_external_observations(
            event_id=event_id,
            zone_id=zone_id,
            occurred_at=occurred_at,
            values=observations,
        ),
        proxy_triplet=proxy_triplet,
        sensor_confidence_cap=sensor_cap,
    )


def _suggestions(
    *,
    moment: CareMomentKey,
    evidence_hash: str,
    conclusion_confidence: float,
    sensor_cap: float,
    active: set[CareSuggestionKind],
) -> list[SimulatedCareSuggestion]:
    ref = f"evidence://{evidence_hash}/evidence_core"
    targets: dict[CareSuggestionKind, CareSuggestionTarget] = {
        "ambient_light_preview": "ui_light_preview",
        "voice_checkin_preview": "speaker_script_preview",
        "family_notification_draft": "family_message_draft",
        "robot_inspection_preview": "robot_task_preview",
    }
    copy: dict[CareMomentKey, dict[CareSuggestionKind, tuple[str, str, str]]] = {
        "routine": {
            "ambient_light_preview": (
                "保持当前环境光",
                "当前模拟记录在日常阈值内，无需改变灯光。",
                "预演：维持当前光线，不调用智能家居。",
            ),
            "voice_checkin_preview": (
                "暂不语音打扰",
                "没有达到主动询问阈值，保留安静。",
                "暂缓：不播放语音，仅展示判断。",
            ),
            "family_notification_draft": (
                "不生成家属提醒",
                "日常片段不需要占用家属注意力。",
                "暂缓：没有创建或发送家属消息。",
            ),
            "robot_inspection_preview": (
                "机器人保持待机",
                "当前模拟事实没有触发查看需要。",
                "暂缓：不创建机器人任务。",
            ),
        },
        "bathroom_timeout": {
            "ambient_light_preview": (
                "提高走廊照明",
                "先在界面预演从卫生间到客厅的柔和照明。",
                "预演：走廊灯缓慢提高到 40%，未调用灯具。",
            ),
            "voice_checkin_preview": (
                "先礼貌询问",
                "用一句短话确认是否需要帮助，避免直接升级。",
                "语音脚本：您在卫生间有一会儿了，需要我帮您联系家人吗？",
            ),
            "family_notification_draft": (
                "准备家属消息",
                "仅生成草稿，等待本人无回应和人工确认后才可能发送。",
                "消息草稿：卫生间区域模拟停留 31 分钟，尚未确认是否需要帮助。",
            ),
            "robot_inspection_preview": (
                "准备门外查看任务",
                "仅预演机器人到卫生间门外进行非影像语音确认。",
                "任务预演：移动至卫生间门外并询问，不进入、不拍摄。",
            ),
        },
        "fall_drill": {
            "ambient_light_preview": (
                "打开应急照明预演",
                "为人工跌倒演练展示高优先级照明方案。",
                "预演：客厅与走廊灯全亮，未调用灯具。",
            ),
            "voice_checkin_preview": (
                "立即语音确认脚本",
                "先询问能否回应，并说明这是演练中的动作草案。",
                "语音脚本：演练出现风险信号，您能听到我吗？",
            ),
            "family_notification_draft": (
                "生成高优先级家属草稿",
                "草稿包含演练标识、区域和未知项，不会自动发送。",
                "消息草稿：客厅出现人工跌倒演练标签，当前是否受伤仍未知。",
            ),
            "robot_inspection_preview": (
                "机器人查看任务预演",
                "预演机器人在人工确认后前往客厅进行语音查看。",
                "任务预演：前往客厅安全距离处，语音确认并等待人工接管。",
            ),
        },
        "pet_night": {
            "ambient_light_preview": (
                "保持夜灯低亮",
                "外部模拟标签标为宠物，仅预演低亮度路径灯。",
                "预演：夜灯维持 10%，未调用灯具。",
            ),
            "voice_checkin_preview": (
                "不唤醒老人",
                "外部标签已把这一片段标为宠物活动。",
                "暂缓：不播放语音；Wi-Fi 代理本身不能识别宠物。",
            ),
            "family_notification_draft": (
                "不打扰家属",
                "该模拟片段不升级为老人异常。",
                "暂缓：没有创建或发送家属消息。",
            ),
            "robot_inspection_preview": (
                "机器人保持待机",
                "外部模拟标签已解释活动来源，不创建查看任务。",
                "暂缓：不创建机器人任务。",
            ),
        },
    }
    ordered_kinds: tuple[CareSuggestionKind, ...] = (
        "ambient_light_preview",
        "voice_checkin_preview",
        "family_notification_draft",
        "robot_inspection_preview",
    )
    suggestions: list[SimulatedCareSuggestion] = []
    for kind in ordered_kinds:
        title, detail, preview_copy = copy[moment][kind]
        enabled = kind in active
        reason_code: CareSuggestionReasonCode
        if enabled:
            reason_code = (
                "human_confirmation_required"
                if kind
                in {
                    "voice_checkin_preview",
                    "family_notification_draft",
                    "robot_inspection_preview",
                }
                else "scenario_preview_only"
            )
        elif moment == "pet_night":
            reason_code = "external_label_resolved"
        else:
            reason_code = "not_needed"
        suggestions.append(
            SimulatedCareSuggestion(
                suggestion_id=f"suggestion-{moment}-{kind}",
                kind=kind,
                title=title,
                detail=detail,
                preview_copy=preview_copy,
                execution_status="simulated_preview" if enabled else "withheld",
                target=targets[kind] if enabled else "none",
                reason_code=reason_code,
                requires_human_confirmation=kind != "ambient_light_preview",
                external_execution_allowed=False,
                evidence_refs=[
                    f"{ref}/event_id",
                    f"{ref}/zone_id",
                    f"{ref}/threshold_comparison",
                    f"{ref}/proxy_triplet/window_id",
                    f"{ref}/proxy_triplet/status",
                ],
                action_confidence=conclusion_confidence,
                sensor_confidence_cap=sensor_cap,
            )
        )
    return suggestions


def _facts(
    *,
    evidence_hash: str,
    zone_id: str,
    zone_label: str,
    duration: float,
    threshold: float,
    sources: list[CareInputSource],
    plain_facts: list[str],
    unknowns: list[str],
) -> CareMomentFacts:
    return CareMomentFacts(
        zone_id=zone_id,
        zone_label=zone_label,
        observed_duration_min=duration,
        threshold_min=threshold,
        threshold_comparison="exceeded" if duration > threshold else "within",
        input_sources=sources,
        plain_facts=plain_facts,
        unknowns=unknowns,
        evidence_refs=[
            f"evidence://{evidence_hash}/evidence_core/observed_duration_min",
            f"evidence://{evidence_hash}/evidence_core/threshold_min",
            f"evidence://{evidence_hash}/evidence_core/input_sources",
            f"evidence://{evidence_hash}/evidence_core/proxy_triplet/window_id",
            f"evidence://{evidence_hash}/evidence_core/proxy_triplet/motion/value",
        ],
    )


def _resident() -> SimulatedResidentProfile:
    return SimulatedResidentProfile(
        profile_id="resident-anon-sim-001",
        display_name="A-01（匿名模拟老人）",
        profile_origin="fictional_simulation",
        age_band="75-79",
        living_arrangement="lives_alone_simulation",
        mobility_context=[
            "室内步速较慢（场景设定）",
            "外出时使用手杖（场景设定）",
        ],
        household_context=[
            "独居（场景设定）",
            "家中有一只猫（场景设定）",
            "女儿住在同城（场景设定）",
        ],
        care_preferences=[
            "先语音询问本人，再考虑联系家属",
            "无明确风险时尽量少打扰",
            "任何机器人或智能家居动作都需人工确认",
        ],
        contains_real_person_data=False,
    )


def _home() -> SimulatedHomeLayout:
    zone_source: list[CareInputSource] = [
        "simulated_wifi_proxy",
        "simulated_external_zone_presence",
    ]
    return SimulatedHomeLayout(
        home_id="home-sim-58m2-001",
        label="58㎡ 一室一厅原居养老模拟户型",
        layout_source="simulated_fixture_not_sensor_inferred",
        approximate_area_m2=58.0,
        zones=[
            SimulatedHomeZone(
                zone_id="entry",
                label="玄关",
                approximate_area_m2=4.0,
                adjacent_zone_ids=["living_room"],
                simulated_inputs=zone_source,
            ),
            SimulatedHomeZone(
                zone_id="living_room",
                label="客厅",
                approximate_area_m2=20.0,
                adjacent_zone_ids=["entry", "bedroom", "kitchen", "bathroom", "balcony"],
                simulated_inputs=[
                    *zone_source,
                    "simulated_external_multisensor_label",
                    "simulated_manual_fall_drill_label",
                ],
            ),
            SimulatedHomeZone(
                zone_id="bedroom",
                label="卧室",
                approximate_area_m2=14.0,
                adjacent_zone_ids=["living_room"],
                simulated_inputs=zone_source,
            ),
            SimulatedHomeZone(
                zone_id="kitchen",
                label="厨房",
                approximate_area_m2=8.0,
                adjacent_zone_ids=["living_room"],
                simulated_inputs=zone_source,
            ),
            SimulatedHomeZone(
                zone_id="bathroom",
                label="卫生间",
                approximate_area_m2=6.0,
                adjacent_zone_ids=["living_room"],
                simulated_inputs=[
                    "simulated_wifi_proxy",
                    "simulated_external_zone_presence",
                    "simulated_clock",
                    "simulated_care_rule",
                ],
            ),
            SimulatedHomeZone(
                zone_id="balcony",
                label="阳台",
                approximate_area_m2=6.0,
                adjacent_zone_ids=["living_room"],
                simulated_inputs=zone_source,
            ),
        ],
        notes=[
            "户型、区域和面积全部来自虚构 fixture，不由 Wi-Fi CSI 重建。",
            "区域标签来自模拟外部 presence 输入，当前 CSI 不识别具体房间。",
        ],
    )


def _timeline() -> list[SimulatedActivityEntry]:
    zone_inputs: list[CareInputSource] = [
        "simulated_wifi_proxy",
        "simulated_external_zone_presence",
        "simulated_clock",
    ]
    return [
        SimulatedActivityEntry(
            entry_id="timeline-01-wake",
            started_at=_at(6, 35),
            ended_at=_at(6, 43),
            zone_id="bedroom",
            activity_label="起床与缓慢活动（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="模拟活动强度从安静过渡到轻微活动。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-02-morning-bathroom",
            started_at=_at(6, 45),
            ended_at=_at(6, 52),
            zone_id="bathroom",
            activity_label="晨间卫生间停留（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="7 分钟，低于场景设定的 20 分钟关注阈值。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-03-breakfast",
            started_at=_at(6, 58),
            ended_at=_at(7, 25),
            zone_id="kitchen",
            activity_label="准备早餐（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="区域与活动名称来自模拟脚本，不是 CSI 行为识别。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-04-routine",
            started_at=_at(7, 30),
            ended_at=_at(7, 48),
            zone_id="living_room",
            activity_label="客厅日常活动（脚本）",
            status="routine",
            input_sources=[*zone_inputs, "simulated_care_rule"],
            event_id="care-event-routine",
            note="18 分钟，位于日常检查阈值内。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-05-balcony",
            started_at=_at(9, 20),
            ended_at=_at(9, 38),
            zone_id="balcony",
            activity_label="阳台停留（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="模拟区域 presence 与 Wi-Fi 活动代理共同变化。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-06-bathroom-timeout",
            started_at=_at(12, 14),
            ended_at=_at(12, 45),
            zone_id="bathroom",
            activity_label="卫生间连续停留（脚本）",
            status="warning",
            input_sources=[
                *zone_inputs,
                "simulated_care_rule",
            ],
            event_id="care-event-bathroom-timeout",
            note="31 分钟，超过虚构场景的 20 分钟关注阈值。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-07-lunch",
            started_at=_at(13, 5),
            ended_at=_at(13, 35),
            zone_id="kitchen",
            activity_label="午餐活动（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="事件后恢复到模拟日常片段。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-08-nap",
            started_at=_at(14, 10),
            ended_at=_at(15, 0),
            zone_id="bedroom",
            activity_label="午休（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="安静片段不自动等同于异常。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-09-fall-drill",
            started_at=_at(16, 17),
            ended_at=_at(16, 19),
            zone_id="living_room",
            activity_label="人工跌倒风险演练",
            status="drill",
            input_sources=[
                "simulated_wifi_proxy",
                "simulated_external_zone_presence",
                "simulated_manual_fall_drill_label",
                "simulated_care_rule",
                "simulated_clock",
            ],
            event_id="care-event-fall-drill",
            note="人工注入标签专用于演示；不代表当前硬件已验证跌倒检测。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-10-evening",
            started_at=_at(19, 5),
            ended_at=_at(21, 35),
            zone_id="living_room",
            activity_label="晚间客厅活动（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="模拟长时段日常活动。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-11-sleep",
            started_at=_at(22, 10),
            ended_at=_at(2, 15, next_day=True),
            zone_id="bedroom",
            activity_label="夜间安静片段（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="安静代理不等同于睡眠识别；活动名称来自脚本。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-12-pet-night",
            started_at=_at(2, 18, next_day=True),
            ended_at=_at(2, 22, next_day=True),
            zone_id="living_room",
            activity_label="外部模拟标签：宠物夜间活动",
            status="external_label",
            input_sources=[
                "simulated_wifi_proxy",
                "simulated_external_zone_presence",
                "simulated_external_multisensor_label",
                "simulated_clock",
            ],
            event_id="care-event-pet-night",
            note="宠物分类仅来自明确的模拟外部多传感器标签，非 CSI 识别。",
        ),
        SimulatedActivityEntry(
            entry_id="timeline-13-resume-quiet",
            started_at=_at(2, 24, next_day=True),
            ended_at=_at(5, 55, next_day=True),
            zone_id="bedroom",
            activity_label="夜间安静片段恢复（脚本）",
            status="routine",
            input_sources=zone_inputs,
            note="模拟场景回到安静代理状态。",
        ),
    ]


def _moments() -> list[SimulatedCareMoment]:
    routine_sources: list[CareInputSource] = [
        "simulated_wifi_proxy",
        "simulated_external_zone_presence",
        "simulated_clock",
        "simulated_care_rule",
    ]
    bathroom_sources: list[CareInputSource] = [
        "simulated_wifi_proxy",
        "simulated_external_zone_presence",
        "simulated_clock",
        "simulated_care_rule",
    ]
    fall_sources: list[CareInputSource] = [
        "simulated_wifi_proxy",
        "simulated_external_zone_presence",
        "simulated_manual_fall_drill_label",
        "simulated_care_rule",
        "simulated_clock",
    ]
    pet_sources: list[CareInputSource] = [
        "simulated_wifi_proxy",
        "simulated_external_zone_presence",
        "simulated_external_multisensor_label",
        "simulated_clock",
    ]
    routine_triplet = _proxy_triplet(
        event_id="care-event-routine",
        ended_at=_at(7, 48),
        sensor_cap=0.82,
        motion_value=0.3,
        motion_state="micro_motion",
        motion_confidence=0.8,
        occupancy_probabilities=(0.2, 0.64, 0.12, 0.04),
        occupancy_state="medium",
        occupancy_confidence=0.78,
        depth_probabilities=(0.16, 0.66, 0.14, 0.04),
        depth_state="mid",
        depth_confidence=0.76,
    )
    bathroom_triplet = _proxy_triplet(
        event_id="care-event-bathroom-timeout",
        ended_at=_at(12, 45),
        sensor_cap=0.78,
        motion_value=0.11,
        motion_state="micro_motion",
        motion_confidence=0.75,
        occupancy_probabilities=(0.08, 0.26, 0.62, 0.04),
        occupancy_state="high",
        occupancy_confidence=0.73,
        depth_probabilities=(0.62, 0.26, 0.08, 0.04),
        depth_state="near",
        depth_confidence=0.71,
    )
    fall_triplet = _proxy_triplet(
        event_id="care-event-fall-drill",
        ended_at=_at(16, 19),
        sensor_cap=0.74,
        motion_value=0.92,
        motion_state="fast_change",
        motion_confidence=0.73,
        occupancy_probabilities=(0.12, 0.58, 0.26, 0.04),
        occupancy_state="medium",
        occupancy_confidence=0.7,
        depth_probabilities=(0.64, 0.24, 0.08, 0.04),
        depth_state="near",
        depth_confidence=0.68,
    )
    pet_triplet = _proxy_triplet(
        event_id="care-event-pet-night",
        ended_at=_at(2, 22, next_day=True),
        sensor_cap=0.82,
        motion_value=0.56,
        motion_state="moving",
        motion_confidence=0.8,
        occupancy_probabilities=(0.58, 0.32, 0.06, 0.04),
        occupancy_state="low",
        occupancy_confidence=0.76,
        depth_probabilities=(0.12, 0.28, 0.56, 0.04),
        depth_state="far",
        depth_confidence=0.74,
    )
    routine_core = _evidence_core(
        event_id="care-event-routine",
        timeline_entry_id="timeline-04-routine",
        event_type="routine_check",
        occurred_at=_at(7, 48),
        zone_id="living_room",
        duration=18,
        threshold=45,
        sources=routine_sources,
        sensor_cap=0.82,
        observations=[
            ("simulated_wifi_proxy", "activity_change"),
            ("simulated_external_zone_presence", "zone_present"),
        ],
        proxy_triplet=routine_triplet,
    )
    bathroom_core = _evidence_core(
        event_id="care-event-bathroom-timeout",
        timeline_entry_id="timeline-06-bathroom-timeout",
        event_type="bathroom_duration_exceeded",
        occurred_at=_at(12, 45),
        zone_id="bathroom",
        duration=31,
        threshold=20,
        sources=bathroom_sources,
        sensor_cap=0.78,
        observations=[
            ("simulated_wifi_proxy", "activity_change"),
            ("simulated_external_zone_presence", "zone_present"),
        ],
        proxy_triplet=bathroom_triplet,
    )
    fall_core = _evidence_core(
        event_id="care-event-fall-drill",
        timeline_entry_id="timeline-09-fall-drill",
        event_type="suspected_fall_drill",
        occurred_at=_at(16, 19),
        zone_id="living_room",
        duration=2,
        threshold=1,
        sources=fall_sources,
        sensor_cap=0.74,
        observations=[
            ("simulated_wifi_proxy", "activity_change"),
            ("simulated_external_zone_presence", "zone_present"),
            ("simulated_manual_fall_drill_label", "fall_drill"),
        ],
        proxy_triplet=fall_triplet,
    )
    pet_core = _evidence_core(
        event_id="care-event-pet-night",
        timeline_entry_id="timeline-12-pet-night",
        event_type="pet_activity_external_label",
        occurred_at=_at(2, 22, next_day=True),
        zone_id="living_room",
        duration=4,
        threshold=5,
        sources=pet_sources,
        sensor_cap=0.82,
        observations=[
            ("simulated_wifi_proxy", "activity_change"),
            ("simulated_external_zone_presence", "zone_present"),
            ("simulated_external_multisensor_label", "pet"),
        ],
        proxy_triplet=pet_triplet,
    )
    routine_hash = canonical_care_evidence_hash(routine_core)
    bathroom_hash = canonical_care_evidence_hash(bathroom_core)
    fall_hash = canonical_care_evidence_hash(fall_core)
    pet_hash = canonical_care_evidence_hash(pet_core)
    return [
        SimulatedCareMoment(
            moment="routine",
            event_id="care-event-routine",
            timeline_entry_id="timeline-04-routine",
            event_type="routine_check",
            severity="normal",
            occurred_at=_at(7, 48),
            scenario_only=True,
            evidence_core=routine_core,
            evidence_hash=routine_hash,
            facts=_facts(
                evidence_hash=routine_hash,
                zone_id="living_room",
                zone_label="客厅",
                duration=18,
                threshold=45,
                sources=routine_sources,
                plain_facts=[
                    "区域：客厅（来自模拟外部区域标签）",
                    "持续：18 分钟",
                    "规则阈值：45 分钟",
                    "结果：仍在设定日常范围内",
                    "Wi-Fi 只提供活动、占用和相对纵深代理",
                ],
                unknowns=["不知道本人具体在做什么", "不知道本人主观感受"],
            ),
            headline="客厅片段在日常阈值内",
            conclusion=(
                "模拟记录显示客厅区域连续 18 分钟有稳定活动，低于 45 分钟"
                "关注阈值。Agent 保持安静，不把普通日常升级为异常。"
            ),
            what_agent_knows=[
                "模拟外部区域标签为客厅",
                "模拟时钟记录 18 分钟",
                "Wi-Fi 代理质量满足本场景展示",
            ],
            what_agent_does_not_know=[
                "不能由 CSI 知道具体行为",
                "不能确认身份、姿态或健康状态",
            ],
            interpretation_status="supported",
            conclusion_confidence=0.76,
            sensor_confidence_cap=0.82,
            suggestions=_suggestions(
                moment="routine",
                evidence_hash=routine_hash,
                conclusion_confidence=0.76,
                sensor_cap=0.82,
                active=set(),
            ),
        ),
        SimulatedCareMoment(
            moment="bathroom_timeout",
            event_id="care-event-bathroom-timeout",
            timeline_entry_id="timeline-06-bathroom-timeout",
            event_type="bathroom_duration_exceeded",
            severity="warning",
            occurred_at=_at(12, 45),
            scenario_only=True,
            evidence_core=bathroom_core,
            evidence_hash=bathroom_hash,
            facts=_facts(
                evidence_hash=bathroom_hash,
                zone_id="bathroom",
                zone_label="卫生间",
                duration=31,
                threshold=20,
                sources=bathroom_sources,
                plain_facts=[
                    "区域：卫生间（来自模拟外部区域标签）",
                    "持续：31 分钟",
                    "关注阈值：20 分钟",
                    "超出阈值：11 分钟",
                    "Wi-Fi 代理只补充活动变化，不识别具体行为",
                ],
                unknowns=[
                    "尚未确认本人是否需要帮助",
                    "不知道停留原因",
                    "不知道是否发生健康问题",
                ],
            ),
            headline="卫生间停留超过模拟关注阈值",
            conclusion=(
                "模拟记录显示卫生间区域已连续停留 31 分钟，比设定阈值多 11 分钟。"
                "这不是跌倒结论；Agent 先建议语音确认，再由人决定是否联系家属。"
            ),
            what_agent_knows=[
                "模拟区域标签为卫生间",
                "模拟时钟显示连续 31 分钟",
                "设定规则阈值为 20 分钟",
            ],
            what_agent_does_not_know=[
                "不知道停留原因",
                "不知道本人是否受伤或需要帮助",
                "CSI 不能识别具体行为或姿态",
            ],
            interpretation_status="supported",
            conclusion_confidence=0.72,
            sensor_confidence_cap=0.78,
            suggestions=_suggestions(
                moment="bathroom_timeout",
                evidence_hash=bathroom_hash,
                conclusion_confidence=0.72,
                sensor_cap=0.78,
                active={
                    "ambient_light_preview",
                    "voice_checkin_preview",
                    "family_notification_draft",
                    "robot_inspection_preview",
                },
            ),
        ),
        SimulatedCareMoment(
            moment="fall_drill",
            event_id="care-event-fall-drill",
            timeline_entry_id="timeline-09-fall-drill",
            event_type="suspected_fall_drill",
            severity="urgent_drill",
            occurred_at=_at(16, 19),
            scenario_only=True,
            evidence_core=fall_core,
            evidence_hash=fall_hash,
            facts=_facts(
                evidence_hash=fall_hash,
                zone_id="living_room",
                zone_label="客厅",
                duration=2,
                threshold=1,
                sources=fall_sources,
                plain_facts=[
                    "区域：客厅（来自模拟外部区域标签）",
                    "人工输入：跌倒风险演练标签",
                    "模拟 Wi-Fi 代理的单一演练快照显示活动突变",
                    "演练片段持续：2 分钟",
                    "演练规则阈值：1 分钟",
                    "当前硬件没有完成真实跌倒检测验证",
                ],
                unknowns=[
                    "真实环境中是否有人跌倒",
                    "是否受伤",
                    "是否能够自行起身",
                ],
            ),
            headline="人工跌倒演练触发高优先级预警",
            conclusion=(
                "这是人工注入的跌倒风险演练，不是当前硬件的真实检测结果。"
                "演示中，Agent 将其作为高优先级疑似风险：先语音确认，同时准备家属"
                "草稿与机器人查看任务，但全部停留在预演。"
            ),
            what_agent_knows=[
                "存在明确的人工跌倒演练标签",
                "模拟区域标签为客厅",
                "模拟 Wi-Fi 代理的单一演练快照显示活动突变",
            ],
            what_agent_does_not_know=[
                "不能确认真实跌倒",
                "不能识别姿态、身份或伤情",
                "尚无 Live 硬件跌倒检测验证",
            ],
            interpretation_status="supported",
            conclusion_confidence=0.74,
            sensor_confidence_cap=0.74,
            suggestions=_suggestions(
                moment="fall_drill",
                evidence_hash=fall_hash,
                conclusion_confidence=0.74,
                sensor_cap=0.74,
                active={
                    "ambient_light_preview",
                    "voice_checkin_preview",
                    "family_notification_draft",
                    "robot_inspection_preview",
                },
            ),
        ),
        SimulatedCareMoment(
            moment="pet_night",
            event_id="care-event-pet-night",
            timeline_entry_id="timeline-12-pet-night",
            event_type="pet_activity_external_label",
            severity="attention",
            occurred_at=_at(2, 22, next_day=True),
            scenario_only=True,
            evidence_core=pet_core,
            evidence_hash=pet_hash,
            facts=_facts(
                evidence_hash=pet_hash,
                zone_id="living_room",
                zone_label="客厅",
                duration=4,
                threshold=5,
                sources=pet_sources,
                plain_facts=[
                    "时间：02:18—02:22（模拟）",
                    "区域：客厅（来自模拟外部区域标签）",
                    "持续：4 分钟，低于 5 分钟关注阈值",
                    "来源分类：模拟外部多传感器标签标为宠物",
                    "Wi-Fi CSI 单独不能区分老人、访客或宠物",
                ],
                unknowns=[
                    "不知道宠物具体行为",
                    "不知道卧室内老人状态",
                    "若外部标签缺失则活动来源应保持未知",
                ],
            ),
            headline="夜间扰动由外部模拟标签标为宠物",
            conclusion=(
                "02:18 的 4 分钟活动由明确的模拟外部多传感器标签标为宠物。"
                "Agent 不把它升级为老人异常；Wi-Fi CSI 本身不能识别宠物。"
            ),
            what_agent_knows=[
                "模拟外部多传感器标签标为宠物",
                "模拟区域标签为客厅",
                "活动持续 4 分钟",
            ],
            what_agent_does_not_know=[
                "CSI 本身不能区分宠物与人",
                "不能据此判断卧室内老人状态",
                "不能识别宠物行为",
            ],
            interpretation_status="supported",
            conclusion_confidence=0.79,
            sensor_confidence_cap=0.82,
            suggestions=_suggestions(
                moment="pet_night",
                evidence_hash=pet_hash,
                conclusion_confidence=0.79,
                sensor_cap=0.82,
                active={"ambient_light_preview"},
            ),
        ),
    ]


def build_simulated_care_scenario(
    selected_moment: CareMomentKey = "bathroom_timeout",
) -> SimulatedCareScenario:
    """Build one stable fictional day with a deterministic selected moment."""
    moments = _moments()
    current_index = next(
        index for index, moment in enumerate(moments) if moment.moment == selected_moment
    )
    return SimulatedCareScenario(
        schema_version="simulated-care-scenario.v2",
        scenario_id=CARE_SCENARIO_ID,
        simulation_only=True,
        source_mode="mock",
        device_execution_enabled=False,
        resident=_resident(),
        home=_home(),
        day_started_at=CARE_DAY_START,
        day_ended_at=CARE_DAY_START + timedelta(days=1),
        timeline=_timeline(),
        moments=moments,
        selected_moment=selected_moment,
        current_index=current_index,
        truth_boundary=[
            "全部人物、户型、时间线、事件和规则都是确定性模拟数据。",
            "彩色数字是推断场，不是摄像头图像。",
            "当前 Wi-Fi CSI 只提供活动、占用密度和相对纵深代理。",
            "卫生间区域来自模拟外部区域标签，不由 CSI 识别。",
            "宠物分类只来自模拟外部多传感器标签，不由 CSI 识别。",
            "跌倒事件是人工演练标签，不代表当前硬件已具备真实跌倒检测。",
            "所有灯光、语音、家属消息和机器人任务只预演或暂缓，未执行。",
        ],
        generated_at=CARE_DAY_START,
    )
