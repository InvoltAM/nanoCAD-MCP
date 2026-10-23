# probe_model.ps1 - M2 probe: DI container, component resolve, model net
# Run: powershell -ExecutionPolicy Bypass -File scripts\probe_model.ps1
# Output: model_results.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "model_results.txt"
$base = "http://localhost:5080/api/electro/model"
"" | Out-File $out -Encoding utf8

function Dump($title, $url) {
    "==== $title ====" | Out-File $out -Append -Encoding utf8
    try {
        $r = Invoke-RestMethod -Uri $url -TimeoutSec 180
        ($r | ConvertTo-Json -Depth 7) | Out-File $out -Append -Encoding utf8
    } catch {
        "ERROR: $($_.Exception.Message)" | Out-File $out -Append -Encoding utf8
    }
}

Dump "Discover accessors" "$base/discover"
Dump "Resolve IDbElFiderCraetor" "$base/resolve/Nanosoft.Electrica.IDbElFiderCraetor"
Dump "Resolve IFiderCreator" "$base/resolve/Nanosoft.CAE.IFiderCreator"
Dump "Resolve IElPowerCalculator" "$base/resolve/Nanosoft.Electrica.IElPowerCalculator"
Dump "Resolve IAcadNet" "$base/resolve/Nanosoft.Acad.IAcadNet"
Dump "Net info" "$base/net"
Dump "Boards" "$base/boards"

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
