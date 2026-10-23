# probe_db.ps1 - equipment DB access recon (no plugin rebuild needed)
# Run: powershell -ExecutionPolicy Bypass -File scripts\probe_db.ps1
# Output: db_results.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "db_results.txt"
$insp = "http://localhost:5080/api/electro"
$mdl  = "http://localhost:5080/api/electro/model"
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

Dump "Type IDatabaseProxyComponent" "$insp/type/Nanosoft.CAE.Db.DatabaseProxyComponent.IDatabaseProxyComponent"
Dump "Resolve IDatabaseProxyComponent" "$mdl/resolve/Nanosoft.CAE.Db.DatabaseProxyComponent.IDatabaseProxyComponent"
Dump "Type DbObjectProvider" "$insp/type/Nanosoft.ObjectLib.ESN.Db.DbImpl.DbObjectProvider"
Dump "Type IDbObjectProvider" "$insp/type/Nanosoft.ObjectLib.ESN.Db.Model.FiderGadgets.IDbObjectProvider"
Dump "Type DbElUzo" "$insp/type/Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElUzo"
Dump "Type DbElFider" "$insp/type/Nanosoft.ObjectLib.ESN.Db.DbImpl.DbElFider"
Dump "Type DbKitItem" "$insp/type/Nanosoft.Data.DbKitItem"

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
