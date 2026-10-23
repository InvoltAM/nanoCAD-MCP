# inspect_electro4.ps1 - recon round 4: how to get IAcadNet and the DI container
# Run: powershell -ExecutionPolicy Bypass -File scripts\inspect_electro4.ps1
# Output: inspect_results4.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "inspect_results4.txt"
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

# 1. Type lists: Cad.Toolware (home of IAcadNet), Platform (DI container), Cad.Impl
Dump "Types Nanosoft.Cad.Toolware" "$base/types/Nanosoft.Cad.Toolware"
Dump "Types Nanosoft.Platform" "$base/types/Nanosoft.Platform"

# 2. Direct probes
$types = @(
    "Nanosoft.Acad.IAcadNetSystemLoaderService",
    "Nanosoft.Acad.INetObjectFactory",
    "Nanosoft.Acad.IModelRepository",
    "Nanosoft.Acad.GlobalId",
    "Nanosoft.Acad.AcaoNetService",
    "Nanosoft.Acad.AcadNetService"
)
foreach ($t in $types) { Dump "Type $t" "$base/type/$t" }

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
