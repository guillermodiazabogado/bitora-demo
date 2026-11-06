package com.bitora.android.foundation.pairing

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.bitora.android.foundation.network.PairedDeviceIdentity

interface DeviceIdentityStore {
    fun save(identity: PairedDeviceIdentity)
    fun load(): PairedDeviceIdentity?
    fun clear()
}

class SecureDeviceIdentityStore(context: Context) : DeviceIdentityStore {
    private val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()

    private val prefs = EncryptedSharedPreferences.create(
        context,
        "bitora_device_identity",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    override fun save(identity: PairedDeviceIdentity) {
        prefs.edit()
            .putString("device_id", identity.deviceId)
            .putLong("organization_id", identity.organizationId)
            .putLong("event_id", identity.eventId)
            .putString("event_name", identity.eventName)
            .putString("profile", identity.profile)
            .putString("scope", identity.scope)
            .putString("capabilities", identity.capabilities.sorted().joinToString(","))
            .putString("edge_base_url", identity.edgeBaseUrl)
            .putString("dataset_revision", identity.datasetRevision)
            .putString("credential_token", identity.credentialToken)
            .apply()
    }

    override fun load(): PairedDeviceIdentity? {
        val deviceId = prefs.getString("device_id", null) ?: return null
        return PairedDeviceIdentity(
            deviceId = deviceId,
            organizationId = prefs.getLong("organization_id", 0),
            eventId = prefs.getLong("event_id", 0),
            eventName = prefs.getString("event_name", "") ?: "",
            profile = prefs.getString("profile", "") ?: "",
            scope = prefs.getString("scope", "") ?: "",
            capabilities = (prefs.getString("capabilities", "") ?: "")
                .split(",")
                .filter { it.isNotBlank() }
                .toSet(),
            edgeBaseUrl = prefs.getString("edge_base_url", "") ?: "",
            datasetRevision = prefs.getString("dataset_revision", null),
            credentialToken = prefs.getString("credential_token", "") ?: "",
        )
    }

    override fun clear() {
        prefs.edit().clear().apply()
    }
}
