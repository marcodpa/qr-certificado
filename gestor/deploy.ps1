# Publica gestor/out/site a Netlify de forma INCREMENTAL:
# solo sube los archivos que cambiaron (Netlify ya tiene el resto por su hash).
$ErrorActionPreference = 'Stop'
$AQUI = Split-Path -Parent $MyInvocation.MyCommand.Path
$cfg = Get-Content (Join-Path $AQUI 'config.json') -Raw | ConvertFrom-Json
$site = Join-Path $AQUI 'out\site'
$token = (Get-Content (Join-Path $AQUI $cfg.token_file) -Raw).Trim()
$hdr = @{ Authorization = "Bearer $token" }

# 1) sha1 de cada archivo del sitio
$raiz = (Resolve-Path $site).Path.TrimEnd('\')
$sha = [System.Security.Cryptography.SHA1]::Create()
$files = @{}       # "/ruta" -> sha1
$rutaPorRel = @{}  # "/ruta" -> ruta absoluta
Get-ChildItem $raiz -Recurse -File | ForEach-Object {
  $rel = '/' + ($_.FullName.Substring($raiz.Length + 1).Replace('\', '/'))
  $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
  $h = ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLower()
  $files[$rel] = $h
  $rutaPorRel[$rel] = $_.FullName
}
Write-Output ("Sitio: {0} archivos. Consultando a Netlify cuales faltan..." -f $files.Count)

# 2) crear deploy con el manifiesto de hashes -> Netlify responde cuales necesita
$body = @{ files = $files } | ConvertTo-Json -Depth 5 -Compress
$dep = Invoke-RestMethod -Uri "https://api.netlify.com/api/v1/sites/$($cfg.site_id)/deploys" -Headers $hdr -Method Post -ContentType 'application/json' -Body $body
$reqSet = @{}
foreach ($h in $dep.required) { $reqSet[$h] = $true }
$aSubir = @($files.Keys | Where-Object { $reqSet[$files[$_]] })
Write-Output ("Solo hay que subir {0} de {1} archivos." -f $aSubir.Count, $files.Count)

# 3) subir unicamente los archivos requeridos, por su ruta
$i = 0
foreach ($rel in $aSubir) {
  $i++
  $bytes = [System.IO.File]::ReadAllBytes($rutaPorRel[$rel])
  $uri = "https://api.netlify.com/api/v1/deploys/$($dep.id)/files$rel"
  Invoke-RestMethod -Uri $uri -Headers $hdr -Method Put -ContentType 'application/octet-stream' -Body $bytes -TimeoutSec 300 | Out-Null
  if ($i % 10 -eq 0 -or $i -eq $aSubir.Count) { Write-Output ("  subidos {0}/{1}" -f $i, $aSubir.Count) }
}

# 4) esperar a que quede publicado
for ($k = 0; $k -lt 60; $k++) {
  $s = Invoke-RestMethod -Uri "https://api.netlify.com/api/v1/deploys/$($dep.id)" -Headers $hdr
  if ($s.state -eq 'ready') { Write-Output "PUBLICADO OK  $($cfg.base_url)"; exit 0 }
  if ($s.state -eq 'error') { Write-Output "ERROR en el despliegue"; exit 1 }
  Start-Sleep -Seconds 3
}
Write-Output "TIMEOUT esperando el despliegue"; exit 1
