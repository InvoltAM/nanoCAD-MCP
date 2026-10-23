# inspect_electro3.ps1 - recon round 3
# Run: powershell -ExecutionPolicy Bypass -File scripts\inspect_electro3.ps1
# Output: inspect_results3.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "inspect_results3.txt"
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

# 1. All loaded assemblies (dot matches any assembly with dot in name; then extras)
Dump "Assemblies ." "$base/assemblies/."
Dump "Assemblies ModuleBase" "$base/assemblies/ModuleBase"

# 2. Candidate homes for IAcadObject / IAcadNet
Dump "Types Nanosoft.CadInterop" "$base/types/Nanosoft.CadInterop"
Dump "Types Nanosoft.Cad.Impl" "$base/types/Nanosoft.Cad.Impl"
Dump "Types Nanosoft.Studio.Model" "$base/types/Nanosoft.Studio.Model"

# 3. Direct type probes (endpoint searches all loaded assemblies by full name)
$types = @(
    "IAcadObject",
    "IAcadNet",
    "Nanosoft.CAE.IAcadObject",
    "Nanosoft.CAE.IAcadNet",
    "Nanosoft.Acad.IAcadObject",
    "Nanosoft.Acad.IAcadNet",
    "Nanosoft.ModuleBase.CwComponent",
    "Nanosoft.ModuleBase.ICwComponent",
    "Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElFiderKitItem",
    "Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElAutomat",
    "Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElBoard",
    "Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElSocket",
    "Nanosoft.CAE.CaeFider",
    "Nanosoft.ObjectLib.WireCommon.CaeFider.Model.ICaeFider",
    "Nanosoft.CAE.IFiderCreator",
    "Nanosoft.CAE.IElGroupBuilder",
    "Nanosoft.Electrica.IElPowerCalculator",
    "Nanosoft.Electrica.IFidersShell",
    "Nanosoft.Electrica.ElFiderUtilities",
    "Nanosoft.Electrica.ElFiderGadget"
)
foreach ($t in $types) { Dump "Type $t" "$base/type/$t" }

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
