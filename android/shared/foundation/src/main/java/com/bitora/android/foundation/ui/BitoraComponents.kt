package com.bitora.android.foundation.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bitora.android.foundation.model.BitoraDatasetStatus
import com.bitora.android.foundation.model.BitoraDeviceStatus
import com.bitora.android.foundation.model.BitoraEdgeStatus
import com.bitora.android.foundation.theme.BitoraColors

@Composable
fun BitoraButton(label: String, modifier: Modifier = Modifier, onClick: () -> Unit = {}) {
    Button(
        onClick = onClick,
        modifier = modifier,
        colors = ButtonDefaults.buttonColors(containerColor = BitoraColors.Success),
        shape = RoundedCornerShape(8.dp),
    ) {
        Text(label)
    }
}

@Composable
fun BitoraSecondaryButton(label: String, modifier: Modifier = Modifier, onClick: () -> Unit = {}) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier,
        border = BorderStroke(1.dp, BitoraColors.Border),
        shape = RoundedCornerShape(8.dp),
    ) {
        Text(label)
    }
}

@Composable
fun BitoraCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, BitoraColors.Border),
        colors = CardDefaults.cardColors(containerColor = BitoraColors.Card),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(16.dp)) {
            content()
        }
    }
}

@Composable
fun BitoraStatusBadge(label: String, tone: StatusTone, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(999.dp),
        color = tone.color.copy(alpha = 0.12f),
        border = BorderStroke(1.dp, tone.color.copy(alpha = 0.25f)),
    ) {
        Text(
            text = "${tone.symbol} $label",
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            color = tone.color,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
fun BitoraTopBar(title: String, subtitle: String, trailing: @Composable () -> Unit = {}) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(BitoraColors.Ink)
            .padding(horizontal = 20.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            Text("BITORA", color = Color.White, style = MaterialTheme.typography.titleMedium)
            Text(title, color = BitoraColors.ArenaLight, style = MaterialTheme.typography.bodyMedium)
            Text(subtitle, color = Color.White.copy(alpha = 0.72f), style = MaterialTheme.typography.bodyMedium)
        }
        trailing()
    }
}

@Composable
fun BitoraDeviceStatus(
    deviceStatus: BitoraDeviceStatus,
    edgeStatus: BitoraEdgeStatus,
    datasetStatus: BitoraDatasetStatus,
    modifier: Modifier = Modifier,
) {
    BitoraCard(modifier) {
        StatusLine("Device", deviceStatus.name, deviceTone(deviceStatus))
        Spacer(Modifier.height(10.dp))
        StatusLine("Edge", edgeStatus.name, edgeTone(edgeStatus))
        Spacer(Modifier.height(10.dp))
        StatusLine("Dataset", datasetStatus.name, datasetTone(datasetStatus))
    }
}

@Composable
fun BitoraEmptyState(title: String, detail: String, modifier: Modifier = Modifier) {
    BitoraCard(modifier) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(6.dp))
        Text(detail, color = BitoraColors.Offline)
    }
}

@Composable
fun BitoraLoadingState(label: String, modifier: Modifier = Modifier) {
    BitoraStatusBadge(label, StatusTone.Neutral, modifier)
}

@Composable
fun BitoraErrorState(label: String, modifier: Modifier = Modifier) {
    BitoraStatusBadge(label, StatusTone.Error, modifier)
}

@Composable
private fun StatusLine(label: String, value: String, tone: StatusTone) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = BitoraColors.Offline)
        BitoraStatusBadge(value, tone)
    }
}

enum class StatusTone(val color: Color, val symbol: String) {
    Success(BitoraColors.Success, "OK"),
    Warning(BitoraColors.Warning, "WARN"),
    Error(BitoraColors.Error, "ERR"),
    Offline(BitoraColors.Offline, "OFF"),
    Neutral(BitoraColors.ArenaDark, "INFO"),
}

fun deviceTone(status: BitoraDeviceStatus): StatusTone = when (status) {
    BitoraDeviceStatus.PAIRED,
    BitoraDeviceStatus.ACTIVE -> StatusTone.Success
    BitoraDeviceStatus.PAIRING_PENDING,
    BitoraDeviceStatus.PROVISIONED -> StatusTone.Warning
    BitoraDeviceStatus.PAIRING_REQUIRED,
    BitoraDeviceStatus.UNPAIRED -> StatusTone.Offline
    BitoraDeviceStatus.SUSPENDED,
    BitoraDeviceStatus.REVOKED -> StatusTone.Error
}

fun edgeTone(status: BitoraEdgeStatus): StatusTone = when (status) {
    BitoraEdgeStatus.ONLINE -> StatusTone.Success
    BitoraEdgeStatus.CONNECTING,
    BitoraEdgeStatus.DEGRADED,
    BitoraEdgeStatus.STALE -> StatusTone.Warning
    BitoraEdgeStatus.NOT_CONFIGURED,
    BitoraEdgeStatus.OFFLINE -> StatusTone.Offline
    BitoraEdgeStatus.ERROR -> StatusTone.Error
}

fun datasetTone(status: BitoraDatasetStatus): StatusTone = when (status) {
    BitoraDatasetStatus.CURRENT -> StatusTone.Success
    BitoraDatasetStatus.STALE -> StatusTone.Warning
    BitoraDatasetStatus.NOT_AVAILABLE,
    BitoraDatasetStatus.EXPIRED,
    BitoraDatasetStatus.INVALID -> StatusTone.Offline
}
