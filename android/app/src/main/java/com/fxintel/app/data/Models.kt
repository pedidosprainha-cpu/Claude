package com.fxintel.app.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class Quote(
    val symbol: String = "",
    val bid: Double = 0.0,
    val ask: Double = 0.0,
    val mid: Double? = null,
    val spread_pips: Double? = null,
    val spread_source: String = "",
    val time: String = "",
    val source: String = "",
    val age_s: Double? = null,
    val change_pct: Double? = null,
)

@Serializable
data class QuotesResp(val at: String? = null, val market_open: Boolean = true, val data: Map<String, Quote> = emptyMap())

@Serializable
data class Gate(val gate: String = "", val passed: Boolean = false, val detail: String = "")

@Serializable
data class RefQuote(
    val bid: Double = 0.0, val ask: Double = 0.0, val mid: Double? = null, val spread_pips: Double? = null,
    val spread_source: String = "", val time: String = "", val source: String = "", val age_s: Double? = null,
)

@Serializable
data class Level(val price: Double = 0.0, val pips: Double? = null, val basis: String? = null, val side: String? = null)

@Serializable
data class TakeProfit(val label: String = "", val price: Double = 0.0, val pips: Double? = null, val rr: Double? = null, val basis: String? = null)

@Serializable
data class RiskReward(val rr_tp1: Double? = null, val rr_tp2: Double? = null, val rr_net_tp1: Double? = null, val cost_r: Double? = null)

@Serializable
data class Probability(
    val model_p: Double? = null, val calibrated_p: Double? = null, val ci90: List<Double?>? = null,
    val n_oos_bin: Int? = null, val event: String = "", val method: String = "",
)

@Serializable
data class Confidence(val level: String = "", val limitations: List<String> = emptyList())

@Serializable
data class Justification(
    val technical: List<String> = emptyList(), val fundamental: List<String> = emptyList(),
    val quantitative: List<String> = emptyList(),
)

@Serializable
data class Validity(val valid_until: String = "", val minutes: Int = 0)

@Serializable
data class Scenarios(val principal: String = "", val alternativo: String = "", val riscos: List<String> = emptyList())

@Serializable
data class Sizing(
    val ok: Boolean = false, val lots: Double? = null, val risk_amount: Double? = null, val risk_pct: Double? = null,
    val account_currency: String? = null, val margin: Double? = null, val reason: String? = null,
)

@Serializable
data class RiskEval(val approved: Boolean = false, val reasons: List<String> = emptyList(), val sizing: Sizing? = null)

@Serializable
data class Candidate(
    val id: String? = null,
    val instrument: String = "",
    val direction: String = "",
    val setup: String = "",
    val setup_name: String = "",
    val execution_type: String = "",
    val reference_quote: RefQuote = RefQuote(),
    val entry: Level = Level(),
    val stop_loss: Level = Level(),
    val take_profit: List<TakeProfit> = emptyList(),
    val risk_reward: RiskReward = RiskReward(),
    val probability: Probability = Probability(),
    val expected_value_r: Double? = null,
    val expected_value_r_ci_low: Double? = null,
    val confidence: Confidence = Confidence(),
    val score: Double = 0.0,
    val justification: Justification = Justification(),
    val invalidation: List<String> = emptyList(),
    val validity: Validity = Validity(),
    val scenarios: Scenarios = Scenarios(),
    val gates: List<Gate> = emptyList(),
    val risk: RiskEval? = null,
    val execution_note: String? = null,
    val has_setup: Boolean = true,
    val rank: Int? = null,
    val status: String? = null,          // SINAL | ELEGIVEL | OBSERVACAO | AGUARDANDO_GATILHO
    val status_text: String? = null,
    val blocked_by: List<String> = emptyList(),
)

@Serializable
data class NextEvent(val currency: String = "", val title: String = "", val time: String = "")

@Serializable
data class MarketRow(
    val symbol: String = "",
    val trend: Map<String, Int> = emptyMap(),
    val alignment: Double? = null,
    val regime: String? = null,
    val fundamental_score: Double? = null,
    val event_block: String? = null,
    val next_event: NextEvent? = null,
    val candidates: Int = 0,
    val error: String? = null,
)

@Serializable
data class OosMetrics(val bss: Double? = null, val auc: Double? = null, val n: Int? = null, val brier: Double? = null)

@Serializable
data class ModelStatus(
    val available: Boolean = false, val validated: Boolean = false, val trained_at: String? = null,
    val age_hours: Double? = null, val oos_metrics: OosMetrics? = null, val oos_holdout_metrics: OosMetrics? = null,
    val validation_rule: String? = null, val message: String? = null,
)

@Serializable
data class EconEvent(val title: String = "", val currency: String = "", val time: String = "", val impact: String = "")

@Serializable
data class Fundamentals(
    val strength_5d: Map<String, Double> = emptyMap(),
    val upcoming_events: List<EconEvent> = emptyList(),
    val calendar_ok: Boolean = true,
    val central_banks_as_of: String? = null,
)

@Serializable
data class Analysis(
    val id: String = "",
    val created_at: String = "",
    val status: String = "",
    val headline: String = "",
    val signal: Candidate? = null,
    val no_signal_reasons: List<String> = emptyList(),
    val observations: List<Candidate> = emptyList(),
    val ranking: List<Candidate> = emptyList(),   // 5 melhores oportunidades por nota
    val market: List<MarketRow> = emptyList(),
    val model: ModelStatus? = null,
    val fundamentals: Fundamentals? = null,
    val elapsed_ms: Double? = null,
    val trigger: String? = null,
    val disclaimer: String = "",
)

@Serializable
data class Bar(val t: Long = 0, val o: Double = 0.0, val h: Double = 0.0, val l: Double = 0.0, val c: Double = 0.0)

@Serializable
data class ChartResp(val symbol: String = "", val tf: String = "", val digits: Int = 5, val bars: List<Bar> = emptyList())

@Serializable
data class SignalRow(
    val id: String = "", val created_at: String = "", val symbol: String = "", val direction: String = "",
    val entry: Double? = null, val sl: Double? = null, val tp1: Double? = null, val tp2: Double? = null,
    val valid_until: String? = null, val status: String = "", val outcome_r: Double? = null,
)

@Serializable
data class SignalStats(val total: Int = 0, val active: Int = 0, val closed: Int = 0, val avg_r: Double? = null)

@Serializable
data class SignalsResp(val stats: SignalStats = SignalStats(), val items: List<SignalRow> = emptyList())

@Serializable
data class AnalysisRow(
    val id: String = "", val created_at: String = "", val status: String = "", val symbol: String? = null,
    val direction: String? = null, val score: Double? = null, val elapsed_ms: Double? = null,
)

@Serializable
data class AlertItem(
    val id: Long = 0, val ts: String = "", val kind: String = "", val severity: String = "",
    val symbol: String? = null, val message: String = "",
)

@Serializable
data class ProviderHealth(
    val name: String = "", val ok: Boolean = true, val last_latency_ms: Double? = null,
    val requests: Int = 0, val failures: Int = 0, val last_error: String? = null,
)

@Serializable
data class Providers(val providers: List<ProviderHealth> = emptyList(), val oanda_configured: Boolean = false)

@Serializable
data class HealthModel(val available: Boolean? = null, val validated: Boolean? = null, val age_hours: Double? = null)

@Serializable
data class Health(
    val status: String = "", val version: String = "", val uptime_s: Double = 0.0, val market_open: Boolean = false,
    val quotes_at: String? = null, val database: Boolean = false, val degraded: List<String> = emptyList(),
    val providers: Providers = Providers(), val model: HealthModel = HealthModel(),
    val heartbeat_age_s: Map<String, Double> = emptyMap(), val training: Boolean = false,
)

@Serializable
data class WsMessage(
    val type: String = "", val at: String? = null, val data: kotlinx.serialization.json.JsonElement? = null,
    val quotes: Map<String, Quote>? = null,
)

typealias SettingsJson = JsonObject
