package dev.dde.android.gateway

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit

class GatewayApiException(
    val errorFamily: String,
    detail: String,
    val httpStatus: Int,
    val retryable: Boolean? = null,
) : Exception("Gateway $errorFamily: $detail (HTTP $httpStatus)")

/**
 * OkHttp implementation of [GatewayTransport] — same six /v1 paths as
 * interfaces/dashboard/static/gateway.js (DDE-052 API parity).
 */
class OkHttpGatewayTransport(
    baseUrl: String,
) : GatewayTransport {
    // Keep OkHttpClient off the public constructor so :app does not need
    // okhttp on its compile classpath (gateway uses implementation, not api).
    private val client: OkHttpClient =
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    private val root = baseUrl.trimEnd('/')
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    private fun v1(path: String): String = "$root/v1$path"

    override suspend fun openSession(
        principalId: String,
        clientType: String,
        scopes: List<String>,
    ): String =
        withContext(Dispatchers.IO) {
            val body =
                JSONObject()
                    .put("principal_id", principalId)
                    .put("client_type", clientType)
                    .put("device_id", JSONObject.NULL)
                    .put("protocol_version", "1")
                    .put("scopes", JSONArray(scopes))
                    .put("subscriptions", JSONArray(listOf("mission")))
            val json = post(v1("/sessions"), body)
            json.getString("session_id")
        }

    override suspend fun resumeSession(
        sessionId: String,
        lastEventAt: String?,
    ): ResumeResult =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
            if (lastEventAt == null) {
                body.put("last_event_at", JSONObject.NULL)
            } else {
                body.put("last_event_at", lastEventAt)
            }
            val json = post(v1("/sessions/$sessionId/resume"), body)
            val session = json.getJSONObject("session")
            ResumeResult(
                sessionId = session.getString("session_id"),
                freshSnapshot = json.optBoolean("fresh_snapshot", false),
                eventCount = json.optJSONArray("events")?.length() ?: 0,
            )
        }

    override suspend fun closeSession(sessionId: String) {
        withContext(Dispatchers.IO) {
            post(v1("/sessions/$sessionId/close"), JSONObject())
        }
    }

    override suspend fun readMission(
        sessionId: String,
        principalId: String,
        missionId: String,
    ): Map<String, Any?> =
        withContext(Dispatchers.IO) {
            get(v1("/missions/$missionId"), sessionId, principalId).toMap()
        }

    override suspend fun readMissionControl(
        sessionId: String,
        principalId: String,
        missionId: String,
    ): Map<String, Any?> =
        withContext(Dispatchers.IO) {
            get(v1("/mission-control/$missionId"), sessionId, principalId).toMap()
        }

    override suspend fun acceptCommand(
        sessionId: String,
        principalId: String,
        commandId: String,
        idempotencyKey: String,
        targetType: String,
        targetId: String,
        commandType: String,
        parameters: Map<String, Any?>,
    ): Map<String, Any?> =
        withContext(Dispatchers.IO) {
            val params = JSONObject()
            for ((k, v) in parameters) {
                params.put(k, v ?: JSONObject.NULL)
            }
            val body =
                JSONObject()
                    .put("command_id", commandId)
                    .put("idempotency_key", idempotencyKey)
                    .put("principal_id", principalId)
                    .put("client_session_id", sessionId)
                    .put("target_type", targetType)
                    .put("target_id", targetId)
                    .put("command_type", commandType)
                    .put("parameters", params)
                    .put("requested_at", java.time.Instant.now().toString())
                    .put("protocol_version", "1")
            post(v1("/commands"), body).toMap()
        }

    private fun get(
        url: String,
        sessionId: String,
        principalId: String,
    ): JSONObject {
        val request =
            Request.Builder()
                .url(url)
                .get()
                .header("Accept", "application/json")
                .header("X-Session-Id", sessionId)
                .header("X-Principal-Id", principalId)
                .build()
        return execute(request)
    }

    private fun post(
        url: String,
        body: JSONObject,
    ): JSONObject {
        val request =
            Request.Builder()
                .url(url)
                .post(body.toString().toRequestBody(jsonMedia))
                .header("Accept", "application/json")
                .header("Content-Type", "application/json")
                .build()
        return execute(request)
    }

    private fun execute(request: Request): JSONObject {
        client.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            val json =
                if (text.isBlank()) {
                    JSONObject()
                } else {
                    try {
                        JSONObject(text)
                    } catch (_: Exception) {
                        JSONObject().put("message", text)
                    }
                }
            if (!response.isSuccessful) {
                val family =
                    when {
                        json.has("error_code") -> json.getString("error_code")
                        json.has("error_family") -> json.getString("error_family")
                        else -> "UNKNOWN"
                    }
                val detail =
                    when {
                        json.has("message") -> json.getString("message")
                        json.has("detail") -> json.get("detail").toString()
                        else -> response.message
                    }
                val retryable =
                    if (json.has("retryable")) json.getBoolean("retryable") else null
                throw GatewayApiException(family, detail, response.code, retryable)
            }
            return json
        }
    }
}

fun newIdempotencyKey(prefix: String): String = "$prefix-${UUID.randomUUID()}"

private fun JSONObject.toMap(): Map<String, Any?> {
    val out = linkedMapOf<String, Any?>()
    val keys = keys()
    while (keys.hasNext()) {
        val key = keys.next()
        val value = get(key)
        out[key] =
            when (value) {
                JSONObject.NULL -> null
                is JSONObject -> value.toMap()
                is JSONArray -> value.toList()
                else -> value
            }
    }
    return out
}

private fun JSONArray.toList(): List<Any?> {
    val out = ArrayList<Any?>(length())
    for (i in 0 until length()) {
        val value = get(i)
        out +=
            when (value) {
                JSONObject.NULL -> null
                is JSONObject -> value.toMap()
                is JSONArray -> value.toList()
                else -> value
            }
    }
    return out
}
