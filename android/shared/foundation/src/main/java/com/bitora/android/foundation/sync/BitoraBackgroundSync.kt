package com.bitora.android.foundation.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.bitora.android.foundation.network.EndpointPolicy
import com.bitora.android.foundation.pairing.SecureDeviceIdentityStore
import com.bitora.android.foundation.persistence.A2LocalStore
import java.util.concurrent.TimeUnit

object BitoraBackgroundSync {
    private const val DEVICE_KIND = "device_kind"
    private const val ALLOW_LAB = "allow_lab"
    private const val SOFTWARE_VERSION = "software_version"

    fun schedule(context: Context, deviceKind: String, allowLabEndpoints: Boolean) {
        val appContext = context.applicationContext
        A2LocalStore(appContext).markBackgroundSync("SCHEDULED")
        val softwareVersion = runCatching {
            appContext.packageManager.getPackageInfo(appContext.packageName, 0).versionName.orEmpty()
        }.getOrDefault("")
        val input = workDataOf(
            DEVICE_KIND to deviceKind,
            ALLOW_LAB to allowLabEndpoints,
            SOFTWARE_VERSION to softwareVersion,
        )
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val periodic = PeriodicWorkRequestBuilder<BitoraSyncWorker>(15, TimeUnit.MINUTES)
            .setInputData(input)
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        val immediate = OneTimeWorkRequestBuilder<BitoraSyncWorker>()
            .setInputData(input)
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        val name = "bitora-${deviceKind.lowercase()}-sync"
        WorkManager.getInstance(appContext).enqueueUniquePeriodicWork(name, ExistingPeriodicWorkPolicy.UPDATE, periodic)
        WorkManager.getInstance(appContext).enqueueUniqueWork("$name-startup", ExistingWorkPolicy.REPLACE, immediate)
    }

    internal fun deviceKind(data: Data): String = data.getString(DEVICE_KIND) ?: ""
    internal fun allowLab(data: Data): Boolean = data.getBoolean(ALLOW_LAB, false)
    internal fun softwareVersion(data: Data): String = data.getString(SOFTWARE_VERSION) ?: ""
}

class BitoraSyncWorker(
    appContext: Context,
    parameters: WorkerParameters,
) : CoroutineWorker(appContext, parameters) {
    override suspend fun doWork(): Result {
        val localStore = A2LocalStore(applicationContext)
        localStore.markBackgroundSync("RUNNING")
        val identityStore = SecureDeviceIdentityStore(applicationContext)
        val identity = runCatching { identityStore.load() }.getOrNull() ?: run {
            localStore.markBackgroundSync("SKIPPED", "identity_missing")
            return Result.success()
        }
        val allowLab = BitoraBackgroundSync.allowLab(inputData)
        if (!EndpointPolicy.isAllowed(identity.edgeBaseUrl, allowLab)) {
            identityStore.clear()
            localStore.markBackgroundSync("FAILED", "edge_endpoint_not_allowed")
            return Result.failure(workDataOf("reason" to "edge_endpoint_not_allowed"))
        }
        val result = EdgeSyncEngine(applicationContext).sync(
            identity = identity,
            flushOperations = BitoraBackgroundSync.deviceKind(inputData) == "OPERATION",
            deviceKind = BitoraBackgroundSync.deviceKind(inputData),
            softwareVersion = BitoraBackgroundSync.softwareVersion(inputData),
            environment = if (allowLab) "LAB" else "PRODUCTION",
        )
        val output = workDataOf(
            "revision" to result.revision.orEmpty(),
            "acknowledged" to result.acknowledged,
            "pending" to result.pending,
            "reason" to result.reason.orEmpty(),
        )
        return if (result.success) {
            localStore.markBackgroundSync("SUCCESS")
            Result.success(output)
        } else {
            localStore.markBackgroundSync("RETRY", result.reason)
            Result.retry()
        }
    }
}
