package com.bitora.android.foundation.recovery

import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.work.WorkManager
import com.bitora.android.foundation.sync.BitoraBackgroundSync
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class BackgroundSchedulingInstrumentedTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Test
    fun schedulesImmediateAndPeriodicRecoveryWork() {
        BitoraBackgroundSync.schedule(context, "DISPLAY", allowLabEndpoints = true)

        val workManager = WorkManager.getInstance(context)
        val periodic = workManager.getWorkInfosForUniqueWork("bitora-display-sync").get(10, TimeUnit.SECONDS)
        val startup = workManager.getWorkInfosForUniqueWork("bitora-display-sync-startup").get(10, TimeUnit.SECONDS)

        assertTrue(periodic.isNotEmpty())
        assertTrue(startup.isNotEmpty())
    }
}
