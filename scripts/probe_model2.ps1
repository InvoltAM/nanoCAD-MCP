# probe_model2.ps1 - dump real property values of existing model nodes
# Run: powershell -ExecutionPolicy Bypass -File scripts\probe_model2.ps1
# Output: model_results2.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "model_results2.txt"
$base = "http://localhost:5080/api/electro/model"
"" | Out-File $out -Encoding utf8

function Dump($title, $url) {
    "==== $title ====" | Out-File $out -Append -Encoding utf8
    try {
        $r = Invoke-RestMethod -Uri $url -TimeoutSec 180
        ($r | ConvertTo-Json -Depth 10) | Out-File $out -Append -Encoding utf8
        return $r
    } catch {
        "ERROR: $($_.Exception.Message)" | Out-File $out -Append -Encoding utf8
        return $null
    }
}

$fiders = Dump "Nodes ElFider" "$base/nodes/ElFider"
if ($fiders -and $fiders.nodes.Count -gt 0) {
    Dump "Dump first ElFider" "$base/node/$($fiders.nodes[0].ac_id)"
}

$automats = Dump "Nodes ElAutomat" "$base/nodes/ElAutomat"
if ($automats -and $automats.nodes.Count -gt 0) {
    Dump "Dump first ElAutomat" "$base/node/$($automats.nodes[0].ac_id)"
}

$boards = Dump "Nodes ElBoard" "$base/nodes/ElBoard"
if ($boards -and $boards.nodes.Count -gt 0) {
    Dump "Dump first ElBoard" "$base/node/$($boards.nodes[0].ac_id)"
}

$sockets = Dump "Nodes ElSocket" "$base/nodes/ElSocket"
if ($sockets -and $sockets.nodes.Count -gt 0) {
    Dump "Dump first ElSocket" "$base/node/$($sockets.nodes[0].ac_id)"
}

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
