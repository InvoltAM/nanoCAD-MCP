# inspect_electro.ps1
# Reconnaissance of nanoCAD BIM Electro 26 API via ElectroInspectService.
# Run: powershell -ExecutionPolicy Bypass -File scripts\inspect_electro.ps1
# Output: inspect_results.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "inspect_results.txt"
$base = "http://localhost:5080/api/electro"
"" | Out-File $out -Encoding utf8

function Dump($title, $url) {
    "==== $title ====" | Out-File $out -Append -Encoding utf8
    try {
        $r = Invoke-RestMethod -Uri $url -TimeoutSec 60
        ($r | ConvertTo-Json -Depth 7) | Out-File $out -Append -Encoding utf8
    } catch {
        "ERROR: $($_.Exception.Message)" | Out-File $out -Append -Encoding utf8
    }
}

# 1. Which Nanosoft assemblies are actually loaded in the process
Dump "Assemblies Nanosoft" "$base/assemblies/Nanosoft"

# 2. Full type lists of key assemblies (looking for IAcadObject, creators, services)
Dump "Types Nanosoft.ObjectLib.ESN" "$base/types/Nanosoft.ObjectLib.ESN"
Dump "Types Nanosoft.CAE.Model"   "$base/types/Nanosoft.CAE.Model"
Dump "Types Nanosoft.CAE.Project" "$base/types/Nanosoft.CAE.Project"
Dump "Types Nanosoft.CAE.Db"      "$base/types/Nanosoft.CAE.Db"

# 3. DI map of the project layer
Dump "Components Nanosoft.CAE.Project" "$base/components/Nanosoft.CAE.Project"
Dump "Components Nanosoft.CAE.Model"   "$base/components/Nanosoft.CAE.Model"

# 4. Signatures of specific types
$types = @(
    "Nanosoft.Electrica.DbElFiderCraetor",
    "Nanosoft.Electrica.SwitchCreator",
    "Nanosoft.Electrica.Creators.BoardCreator",
    "Nanosoft.Electrica.Creators.IDeviceCreator",
    "Nanosoft.Electrica.ElLayerService",
    "Nanosoft.Electrica.EsnDeviceConnectingResolver",
    "Nanosoft.ObjectLib.ESN.Modul.Creator.ElDeviceCreator",
    "Nanosoft.ObjectLib.ESN.Modul.Creator.ElLoadingEqsCreator",
    "Nanosoft.ObjectLib.ESN.SchemaNetBuilder",
    "Nanosoft.ObjectLib.ESN.Modul.FiderFillingService",
    "Nanosoft.ObjectLib.ESN.Equipment.Boards.AutoPhaseBalance.AutoPhaseBoardBalancer",
    "Nanosoft.ObjectLib.ESN.ElBoard",
    "Nanosoft.ObjectLib.ESN.ElFider",
    "Nanosoft.ObjectLib.ESN.ElSocket",
    "Nanosoft.ObjectLib.ESN.ElAutomat"
)
foreach ($t in $types) { Dump "Type $t" "$base/type/$t" }

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
