package com.bitora.android.foundation.recovery

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.bitora.android.foundation.edge.EventDatasetEnvelope
import com.bitora.android.foundation.network.PairedDeviceIdentity
import com.bitora.android.foundation.pairing.SecureDeviceIdentityStore
import com.bitora.android.foundation.persistence.A2LocalStore
import com.bitora.android.foundation.persistence.LocalQueueItem
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PersistenceRecoveryInstrumentedTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Before
    @After
    fun clearState() {
        SecureDeviceIdentityStore(context).clear()
        context.deleteSharedPreferences("bitora_a2_local_store")
    }

    @Test
    fun encryptedIdentitySurvivesStoreRecreation() {
        val identity = PairedDeviceIdentity(
            deviceId = "instrumented-device",
            organizationId = 7,
            eventId = 18,
            eventName = "Recovery Test",
            profile = "DISPLAY",
            scope = "event:18:DISPLAY",
            capabilities = setOf("DISPLAY_CONTENT", "SYNC_DATASET"),
            edgeBaseUrl = "https://edge.bitora.test",
            datasetRevision = "REV-1",
            credentialToken = "instrumented-token",
        )

        SecureDeviceIdentityStore(context).save(identity)

        assertEquals(identity, SecureDeviceIdentityStore(context).load())
    }

    @Test
    fun datasetQueueAndWorkerStateSurviveStoreRecreation() = runBlocking {
        val store = A2LocalStore(context)
        store.saveActiveDataset(
            EventDatasetEnvelope(
                organizationId = 7,
                eventId = 18,
                revision = "REV-OFFLINE-1",
                schemaVersion = "v5.8",
                generatedAt = "2026-10-23T13:00:00Z",
                expiresAtEpochSeconds = 1_900_000_000,
                payloadJson = "{\"display_content\":{\"title\":\"Offline\"}}",
                checksum = "checksum",
                signature = "signature",
                signingKeyId = "instrumented-key",
            )
        )
        store.enqueue(
            LocalQueueItem(
                operationId = "operation-1",
                idempotencyKey = "idempotency-1",
                correlationId = "correlation-1",
                operationType = "ACCESS_ATTEMPT",
                payloadJson = "{\"decision\":\"ALLOW\"}",
                occurredAt = "2026-10-23T13:01:00Z",
                queuedAt = "2026-10-23T13:01:01Z",
                sequence = 1,
            )
        )
        store.markBackgroundSync("RETRY", "offline")

        val restored = A2LocalStore(context)
        assertEquals("REV-OFFLINE-1", restored.activeRevision())
        assertNotNull(restored.loadActiveDataset())
        assertEquals(1, restored.countPending())
        assertEquals("operation-1", restored.pending(10).single().operationId)
        assertEquals("RETRY: offline", restored.backgroundSyncLabel())
    }
}
