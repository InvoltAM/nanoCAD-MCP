# inspect_electro2.ps1 - recon round 2
# Run: powershell -ExecutionPolicy Bypass -File scripts\inspect_electro2.ps1
# Output: inspect_results2.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "inspect_results2.txt"
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

# 1. Type lists of assemblies that hold the missing pieces
Dump "Types Nanosoft.ObjectLib.ESN.Db" "$base/types/Nanosoft.ObjectLib.ESN.Db"
Dump "Types Nanosoft.Electrica.Core" "$base/types/Nanosoft.Electrica.Core"
Dump "Types Nanosoft.Cad.Model" "$base/types/Nanosoft.Cad.Model"
Dump "Types Nanosoft.ObjectLib.Core" "$base/types/Nanosoft.ObjectLib.Core"
Dump "Types Nanosoft.Kit" "$base/types/Nanosoft.Kit"
Dump "Types Nanosoft.ObjectLib.WireCommon" "$base/types/Nanosoft.ObjectLib.WireCommon"
Dump "Types Nanosoft.Electrica.Calc" "$base/types/Nanosoft.Electrica.Calc"

# 2. DI maps
Dump "Components Nanosoft.Electrica.Core" "$base/components/Nanosoft.Electrica.Core"
Dump "Components Nanosoft.Cad.Model" "$base/components/Nanosoft.Cad.Model"
Dump "Components Nanosoft.ObjectLib.ESN.Db" "$base/components/Nanosoft.ObjectLib.ESN.Db"

# 3. Real type names found in round 1
$types = @(
    "Nanosoft.Electrica.ElBoard",
    "Nanosoft.Electrica.ElFider",
    "Nanosoft.Electrica.ElSocket",
    "Nanosoft.Electrica.ElAutomat",
    "Nanosoft.Electrica.ElSwitch",
    "Nanosoft.Electrica.IElFiderService",
    "Nanosoft.Electrica.ElBoardUtility",
    "Nanosoft.Electrica.ElFiderUtilities",
    "Nanosoft.Electrica.ElFiderGadget",
    "Nanosoft.ObjectLib.ESN.Db.DbElFiderKitItem"
)
foreach ($t in $types) { Dump "Type $t" "$base/type/$t" }

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
