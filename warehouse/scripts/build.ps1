$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$version = '3.9.11'
$maven = Join-Path (Get-Location) ".tools/apache-maven-$version/bin/mvn.cmd"
if (!(Test-Path $maven)) {
 New-Item -ItemType Directory -Force .tools | Out-Null
 [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
 $url = "https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/$version/apache-maven-$version-bin.zip"
 Invoke-WebRequest -UseBasicParsing $url -OutFile .tools/maven.zip
 $expected = ((Invoke-WebRequest -UseBasicParsing "$url.sha512").Content.Trim() -split '\s+')[0]
 $actual = (Get-FileHash .tools/maven.zip -Algorithm SHA512).Hash
 if ($actual -ne $expected) { throw 'Maven download checksum mismatch' }
 Expand-Archive .tools/maven.zip .tools -Force
}
& $maven '-B' 'package'
if ($LASTEXITCODE -ne 0) { throw 'Build failed. See output above.' }
New-Item -ItemType Directory -Force release | Out-Null
Copy-Item target/warehouse-1.0.0.jar release/warehouse-1.0.0.jar -Force
Write-Host 'BUILD SUCCESS. Run the launch script to use the new version.'
