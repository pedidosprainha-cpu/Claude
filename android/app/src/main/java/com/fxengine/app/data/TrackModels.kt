package com.fxengine.app.data

import org.json.JSONObject

/** Live track record (fxengine/track.py): the app's own predictions scored on real candles. */
data class TrackInfo(
    val since: String?, val pending: Int,
    val alerts: Int, val alertHit: Double?, val others: Int, val otherHit: Double?, val pMeanAlert: Double?,
    val dirN: Int, val dirHit: Double?, val dirConfN: Int, val dirConfHit: Double?,
    val signalN: Int, val signalMeanR: Double?, val signalWin: Double?,
)

private fun JSONObject.tn(key: String): Double? = if (!has(key) || isNull(key)) null else optDouble(key).takeIf { !it.isNaN() }

fun parseTrack(t: JSONObject?): TrackInfo? {
    if (t == null || t.has("error")) return null
    val x = t.optJSONObject("explosion") ?: JSONObject()
    val s = t.optJSONObject("signal") ?: JSONObject()
    return TrackInfo(
        since = if (t.isNull("since")) null else t.optString("since"), pending = t.optInt("pending"),
        alerts = x.optInt("alerts"), alertHit = x.tn("alert_hit"), others = x.optInt("others"),
        otherHit = x.tn("other_hit"), pMeanAlert = x.tn("p_mean_alert"),
        dirN = x.optInt("dir_n"), dirHit = x.tn("dir_hit"), dirConfN = x.optInt("dir_conf_n"), dirConfHit = x.tn("dir_conf_hit"),
        signalN = s.optInt("n"), signalMeanR = s.tn("mean_r"), signalWin = s.tn("win"),
    )
}
