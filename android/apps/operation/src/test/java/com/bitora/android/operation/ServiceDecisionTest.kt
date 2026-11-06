package com.bitora.android.operation

import com.bitora.android.foundation.network.PairedDeviceIdentity
import org.junit.Assert.assertEquals
import org.junit.Test

class ServiceDecisionTest {
    private val identity = PairedDeviceIdentity(
        deviceId = "service-1",
        organizationId = 1,
        eventId = 18,
        eventName = "LAB",
        profile = "SERVICE",
        scope = "event:18:SERVICE",
        capabilities = setOf("CONSUME_ENTITLEMENT", "SCAN_QR", "SYNC_DATASET"),
        edgeBaseUrl = "https://lab.invalid",
        datasetRevision = "LAB-A5-18-003",
        credentialToken = "secret",
    )

    private val payload = """{"device":{"profile":"SERVICE"},"service_entitlements":[{"token":"BITORA:A5:VALID","event_id":18,"status":"ACTIVE","display_name":"Coffee","service_point":"coffee-main","available":1},{"token":"BITORA:A5:DENY","event_id":18,"status":"REVOKED","display_name":"Revoked","service_point":"coffee-main","available":0}]}"""

    @Test
    fun validEntitlementConsumesAndDuplicateIsDenied() {
        val allowed = evaluateService(identity, payload, 1, 18, 2_000_000_000, "BITORA:A5:VALID", false, 1_900_000_000)
        val duplicate = evaluateService(identity, payload, 1, 18, 2_000_000_000, "BITORA:A5:VALID", true, 1_900_000_000)
        assertEquals(AccessDecision.ALLOW, allowed.decision)
        assertEquals("CONSUMED", allowed.reasonCode)
        assertEquals(AccessDecision.DENY, duplicate.decision)
        assertEquals("ALREADY_CONSUMED", duplicate.reasonCode)
    }

    @Test
    fun rejectsRevokedWrongEventExpiredAndUnauthorizedDevice() {
        assertEquals("REVOKED", evaluateService(identity, payload, 1, 18, 2_000_000_000, "BITORA:A5:DENY", false, 1_900_000_000).reasonCode)
        assertEquals("WRONG_EVENT", evaluateService(identity, payload, 1, 19, 2_000_000_000, "BITORA:A5:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("DATASET_EXPIRED", evaluateService(identity, payload, 1, 18, 1_800_000_000, "BITORA:A5:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("DEVICE_NOT_AUTHORIZED", evaluateService(identity.copy(profile = "RECEPTION"), payload, 1, 18, 2_000_000_000, "BITORA:A5:VALID", false, 1_900_000_000).reasonCode)
        assertEquals("DEVICE_NOT_AUTHORIZED", evaluateService(identity.copy(capabilities = setOf("SCAN_QR")), payload, 1, 18, 2_000_000_000, "BITORA:A5:VALID", false, 1_900_000_000).reasonCode)
    }
}
