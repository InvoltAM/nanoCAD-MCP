# probe_db2.ps1 - IDataSource shape (how to enumerate equipment DB records)
# Run: powershell -ExecutionPolicy Bypass -File scripts\probe_db2.ps1
# Output: db_results2.txt in repo root - send it back entirely.

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "db_results2.txt"
$insp = "http://localhost:5080/api/electro"
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

Dump "Type Nanosoft.Data.IDataSource" "$insp/type/Nanosoft.Data.IDataSource"
Dump "Type Nanosoft.Studio.DataBase.IDataSource" "$insp/type/Nanosoft.Studio.DataBase.IDataSource"
Dump "Type DatabaseProxyComponent (concrete)" "$insp/type/Nanosoft.CAE.Db.DatabaseProxyComponent.DatabaseProxyComponent"
Dump "Type Nanosoft.Data.DbObject" "$insp/type/Nanosoft.Data.DbObject"
Dump "Types Nanosoft.Studio.DataBase" "$insp/types/Nanosoft.Studio.DataBase"

"DONE" | Out-File $out -Append -Encoding utf8
Write-Host "Done. Results file: $out"
