# scripts/rules_engine.py
from dataclasses import dataclass, field

GOOD = "good"
RENEW_CREATIVE = "renew_creative"
KILL_CANDIDATE = "kill_candidate"
INSUFFICIENT_DATA = "insufficient_data"

FREQUENCY_FATIGUE_THRESHOLD = 3.5
CTR_TREND_BAD_THRESHOLD_PCT = -25.0
CVR_TREND_BAD_THRESHOLD_PCT = -25.0
CPA_TREND_BAD_THRESHOLD_PCT = 30.0
CREATIVE_AGE_FALLBACK_DAYS = 14  # 2 weeks, used only when trend data is missing
MIN_IMPRESSIONS_FOR_SIGNAL = 1000
MIN_DAYS_ACTIVE_FOR_SIGNAL = 3
NO_SALES_SPEND_THRESHOLD = 50.0  # account currency units; adjustable per spec section 10

VERDICT_PRIORITY = [KILL_CANDIDATE, RENEW_CREATIVE, INSUFFICIENT_DATA, GOOD]


@dataclass
class CampaignMetrics:
    campaign_id: str
    campaign_name: str
    spend: float
    impressions: int
    purchases: int
    cost_per_purchase: float | None
    ctr: float
    frequency: float
    quality_ranking: str  # "above_average" | "average" | "below_average" | "unknown"
    ctr_trend_pct: float | None
    cvr_trend_pct: float | None
    cpa_trend_pct: float | None
    has_blocking_errors: bool
    days_since_last_creative: int | None
    days_active: int


@dataclass
class VerdictResult:
    verdict: str
    reasons: list[str] = field(default_factory=list)


def _has_enough_data(m: CampaignMetrics) -> bool:
    return m.impressions >= MIN_IMPRESSIONS_FOR_SIGNAL and m.days_active >= MIN_DAYS_ACTIVE_FOR_SIGNAL


def classify_campaign(m: CampaignMetrics) -> VerdictResult:
    # Blocking delivery errors always win, regardless of data volume.
    if m.has_blocking_errors:
        return VerdictResult(KILL_CANDIDATE, ["Error de entrega bloqueante activo"])

    if not _has_enough_data(m):
        return VerdictResult(
            INSUFFICIENT_DATA,
            [f"Solo {m.impressions} impresiones / {m.days_active} días activa — todavía no hay señal confiable"],
        )

    reasons_kill = []
    if (
        m.frequency > FREQUENCY_FATIGUE_THRESHOLD
        and m.cvr_trend_pct is not None
        and m.cvr_trend_pct <= CVR_TREND_BAD_THRESHOLD_PCT
        and m.cpa_trend_pct is not None
        and m.cpa_trend_pct >= CPA_TREND_BAD_THRESHOLD_PCT
    ):
        reasons_kill.append(
            f"Frequency {m.frequency:.2f} + CVR {m.cvr_trend_pct:.1f}% + CPA +{m.cpa_trend_pct:.1f}% sostenido"
        )
    if m.purchases == 0 and m.spend > NO_SALES_SPEND_THRESHOLD:
        reasons_kill.append(f"${m.spend:.2f} de gasto sin ventas en {m.days_active} días")
    if reasons_kill:
        return VerdictResult(KILL_CANDIDATE, reasons_kill)

    reasons_renew = []
    if m.frequency > FREQUENCY_FATIGUE_THRESHOLD:
        reasons_renew.append(f"Frequency {m.frequency:.2f} > {FREQUENCY_FATIGUE_THRESHOLD}")
    if m.quality_ranking == "below_average":
        reasons_renew.append("Quality Ranking: Below Average")
    if m.ctr_trend_pct is not None and m.ctr_trend_pct <= CTR_TREND_BAD_THRESHOLD_PCT:
        reasons_renew.append(f"CTR cayó {m.ctr_trend_pct:.1f}% vs. período anterior")
    if m.cvr_trend_pct is not None and m.cvr_trend_pct <= CVR_TREND_BAD_THRESHOLD_PCT:
        reasons_renew.append(f"CVR cayó {m.cvr_trend_pct:.1f}% vs. período anterior")
    if (
        not reasons_renew
        and m.ctr_trend_pct is None
        and m.cvr_trend_pct is None
        and m.days_since_last_creative is not None
        and m.days_since_last_creative > CREATIVE_AGE_FALLBACK_DAYS
    ):
        reasons_renew.append(
            f"Sin datos de tendencia suficientes y {m.days_since_last_creative} días "
            f"(> {CREATIVE_AGE_FALLBACK_DAYS} días) sin creativo nuevo"
        )
    if reasons_renew:
        return VerdictResult(RENEW_CREATIVE, reasons_renew)

    return VerdictResult(GOOD, ["Sin errores, ranking y tendencias dentro de lo esperado"])


def rollup_campaign_verdict(ad_verdicts: list[str]) -> str:
    for verdict in VERDICT_PRIORITY:
        if verdict in ad_verdicts:
            return verdict
    return INSUFFICIENT_DATA
