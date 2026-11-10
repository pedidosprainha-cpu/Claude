@file:OptIn(ExperimentalMaterial3Api::class)

package com.fxengine.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.fxengine.app.data.Catalog
import com.fxengine.app.ui.theme.Fx

/**
 * Pick one instrument ([multi] = false) or a custom list ([multi] = true) from the 32 the engine covers.
 */
@Composable
fun AssetPickerSheet(
    title: String,
    selected: Set<String>,
    multi: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (List<String>) -> Unit,
) {
    val sheet = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheet, containerColor = Fx.Bg) {
        AssetPickerContent(title, selected, multi, onDismiss, onConfirm)
    }
}

@Composable
fun AssetPickerContent(
    title: String,
    selected: Set<String>,
    multi: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (List<String>) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    var chosen by remember { mutableStateOf(selected) }
    val q = query.trim().uppercase().replace("/", "")
    val shown = Catalog.all.filter {
        q.isEmpty() || it.symbol.contains(q) || it.name.uppercase().contains(query.trim().uppercase())
    }
    Column(Modifier.padding(horizontal = 16.dp)) {
        Text(title, color = Fx.Text, fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = query, onValueChange = { query = it }, singleLine = true,
            leadingIcon = { Icon(Icons.Filled.Search, null) },
            placeholder = { Text("Buscar: EURUSD, iene, ouro…") },
            modifier = Modifier.fillMaxWidth(),
        )
        if (multi) {
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = { chosen = Catalog.all.map { it.symbol }.toSet() }) { Text("Todos") }
                TextButton(onClick = { chosen = Catalog.all.filter { it.group != "Metais" }.map { it.symbol }.toSet() }) { Text("Forex") }
                TextButton(onClick = { chosen = Catalog.all.filter { it.group == "Metais" }.map { it.symbol }.toSet() }) { Text("Metais") }
                TextButton(onClick = { chosen = emptySet() }) { Text("Limpar") }
            }
        }
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 460.dp)) {
            for (g in Catalog.groups) {
                val items = shown.filter { it.group == g }
                if (items.isEmpty()) continue
                item {
                    Text(g, color = Fx.Muted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(top = 12.dp, bottom = 4.dp))
                }
                items(items, key = { it.symbol }) { inst ->
                    val on = inst.symbol in chosen
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp))
                            .background(if (on) Fx.SurfaceHigh else Fx.Bg)
                            .clickable {
                                if (multi) {
                                    chosen = if (on) chosen - inst.symbol else chosen + inst.symbol
                                } else {
                                    onConfirm(listOf(inst.symbol))
                                }
                            }
                            .padding(horizontal = 8.dp, vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (multi) {
                            Checkbox(checked = on, onCheckedChange = {
                                chosen = if (on) chosen - inst.symbol else chosen + inst.symbol
                            })
                        } else {
                            RadioButton(selected = on, onClick = { onConfirm(listOf(inst.symbol)) })
                        }
                        Spacer(Modifier.width(6.dp))
                        Column {
                            Text(inst.symbol, color = Fx.Text, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            Text(inst.name, color = Fx.Muted, fontSize = 12.sp)
                        }
                    }
                }
            }
        }
        if (multi) {
            Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onDismiss, modifier = Modifier.weight(1f)) { Text("Cancelar") }
                Button(
                    onClick = { onConfirm(Catalog.all.map { it.symbol }.filter { it in chosen }) },
                    enabled = chosen.isNotEmpty(), modifier = Modifier.weight(1f),
                ) { Text("Usar ${chosen.size} ativo(s)") }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}
