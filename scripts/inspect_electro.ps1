# inspect_electro.ps1
# Разведка API nanoCAD BIM Электро 26 через ElectroInspectService.
# Запуск: powershell -ExecutionPolicy Bypass -File scripts\inspect_electro.ps1
# Результат: inspect_results.txt в корне репозитория — прислать целиком.

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

# 1. Какие сборки Nanosoft реально загружены в процесс
Dump "Assemblies Nanosoft" "$base/assemblies/Nanosoft"

# 2. Полный список типов ключевых сборок (ищем IAcadObject, создатели, сервисы)
Dump "Types Nanosoft.ObjectLib.ESN" "$base/types/Nanosoft.ObjectLib.ESN"
Dump "Types Nanosoft.CAE.Model"   "$base/types/Nanosoft.CAE.Model"
Dump "Types Nanosoft.CAE.Project" "$base/types/Nanosoft.CAE.Project"
Dump "Types Nanosoft.CAE.Db"      "$base/types/Nanosoft.CAE.Db"

# 3. DI-карта проектного слоя
Dump "Components Nanosoft.CAE.Project" "$base/components/Nanosoft.CAE.Project"
Dump "Components Nanosoft.CAE.Model"   "$base/components/Nanosoft.CAE.Model"

# 4. Сигнатуры конкретных типов
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
Write-Host "Готово. Файл с результатами: $out"
