package com.bitora.android.operation

import com.bitora.android.foundation.network.PairedDeviceIdentity
import org.junit.Assert.assertEquals
import org.junit.Test

class LogisticsDecisionTest {
    private val identity = PairedDeviceIdentity("log-1", 1, 18, "LAB", "LOGISTICS", "event:18:LOGISTICS", setOf("VALIDATE_ACCESS", "SCAN_QR", "SYNC_DATASET"), "https://lab.invalid", "LAB-A7-18-007", "secret")
    private val payload = """{"device":{"profile":"LOGISTICS"},"vehicle_permits":[{"token":"BITORA:A7:VALID","event_id":18,"status":"ACTIVE","checkpoint":"logistics-main"},{"token":"BITORA:A7:DENY","event_id":18,"status":"REVOKED","checkpoint":"logistics-main"}]}"""
    @Test fun allowDuplicateAndRevoke() {
        assertEquals("VEHICLE_ALLOWED", evaluateLogistics(identity,payload,1,18,2_000_000_000,"BITORA:A7:VALID",false,1_900_000_000).reasonCode)
        assertEquals("ALREADY_ENTERED", evaluateLogistics(identity,payload,1,18,2_000_000_000,"BITORA:A7:VALID",true,1_900_000_000).reasonCode)
        assertEquals("PERMIT_REVOKED", evaluateLogistics(identity,payload,1,18,2_000_000_000,"BITORA:A7:DENY",false,1_900_000_000).reasonCode)
    }
    @Test fun isolationAndAuthorization() {
        assertEquals("WRONG_EVENT", evaluateLogistics(identity,payload,1,19,2_000_000_000,"BITORA:A7:VALID",false,1_900_000_000).reasonCode)
        assertEquals("DATASET_EXPIRED", evaluateLogistics(identity,payload,1,18,1_800_000_000,"BITORA:A7:VALID",false,1_900_000_000).reasonCode)
        assertEquals("DEVICE_NOT_AUTHORIZED", evaluateLogistics(identity.copy(profile="SERVICE"),payload,1,18,2_000_000_000,"BITORA:A7:VALID",false,1_900_000_000).reasonCode)
    }
}
