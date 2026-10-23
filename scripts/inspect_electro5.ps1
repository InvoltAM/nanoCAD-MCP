# inspect_electro5.ps1 - recon round 5 (final): DI container + net service signatures
# Run: powershell -ExecutionPolicy Bypass -File scripts\inspect_electro5.ps1
# Output: inspect_results5.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "inspect_results5.txt"
$base = "http://localhost:5080/api/electro"
"" | Out-File $out -Encoding utf8

function Dump($title, $url) {
    "==== $title ====" | Out-File $out -Append -Encoding utf8
    try {
        $r = Invoke-RestMethod -Uri $url -TimeoutSec 120
        ($r | ConvertTo-Json -Depth 7) | Out-File $out -Append -Encoding utf8
    } catch {
        "ERROR: $($_.Exception.Message)" | Out-File $out -Append -Encoding utf8
    }
}

$types = @(
    "Nanosoft.Platform.Platform.Container",
    "Nanosoft.Platform.Platform.IContainer",
    "Nanosoft.Platform.Platform.ScopeComponentManager",
    "Nanosoft.Platform.Platform.IScopeComponentManager",
    "Nanosoft.Acad.IAcadNetService",
    "Nanosoft.Acad.NetTools.AcadNetService",
    "Nanosoft.Acad.Net.IAcadNetFactory",
    "Nanosoft.Acad.Net.INetObjectFactory",
    "Nanosoft.Acad.Net.IModelRepository",
    "Nanosoft.Acad.IAcadNetSelector",
    "Nanosoft.Utils.ComponentAttribute",
    "Nanosoft.Platform.Platform.ScopeComponentAttribute"
)
foreach ($t in $types) { Dump "Type $t" "$base/type/$t" }

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
