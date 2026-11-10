$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8080/api'
function Post($path,$body) { Invoke-RestMethod "$base$path" -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json))) }
$code = 'DEMO-' + (Get-Date -Format 'yyyyMMddHHmmssfff')
# Unicode escapes expressed as chars so this script also works in Windows PowerShell 5.1.
$name = [string][char]0x952e + [char]0x76d8
$unit = [string][char]0x4e2a
$p = Post '/products' @{code=$code;name=$name;unit=$unit}
Post '/inbounds' @{productId=$p.id;locationId=1;quantity=100} | Out-Null
$o = Post '/orders' @{productId=$p.id;locationId=1;quantity=20}
$allStocks = Invoke-RestMethod "$base/stocks?productId=$($p.id)"
$stock = $allStocks | Where-Object LOCATION -eq 'A01'
if ($stock.QUANTITY -ne 100) { throw 'Expected 100 before shipment' }
Post "/orders/$($o.id)/ship" @{} | Out-Null
$allStocks = Invoke-RestMethod "$base/stocks?productId=$($p.id)"
$stock = $allStocks | Where-Object LOCATION -eq 'A01'
if ($stock.QUANTITY -ne 80) { throw 'Expected 80 after shipment' }
$allShipments = Invoke-RestMethod "$base/shipments"
$shipment = $allShipments | Where-Object ORDER_ID -eq $o.id
Post "/shipments/$($shipment.ID)/advance" @{status='TRANSIT'} | Out-Null
Post "/shipments/$($shipment.ID)/advance" @{status='DELIVERED'} | Out-Null
$tracks = Invoke-RestMethod "$base/shipments/$($shipment.ID)/tracking"
if ($tracks.Count -ne 3) { throw 'Expected three tracking records' }
Write-Host "PASS: $code stock 100 -> 80, order $($o.id), shipment $($shipment.ID) delivered."
$tracks | Format-Table
