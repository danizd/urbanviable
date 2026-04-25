$ErrorActionPreference = 'Stop'

$inputPath = 'etl/data/processed/galicia_scouting.geojson'
$outputPath = 'etl/data/processed/galicia_scouting.mbtiles'
$layerName = 'secciones'
$repoRoot = (Resolve-Path '.').Path

if (-not (Test-Path $inputPath)) {
    throw "No existe $inputPath. Ejecuta antes process_data.py"
}

if (Get-Command tippecanoe -ErrorAction SilentlyContinue) {
    if (Test-Path $outputPath) {
        Remove-Item $outputPath -Force
    }

    $args = @(
        "--output=$outputPath",
        "--layer=$layerName",
        "--minimum-zoom=6",
        "--maximum-zoom=14",
        "--coalesce-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--simplification=2",
        "--include=cusec",
        "--include=renta_norm",
        "--include=renta_abs",
        "--include=densidad_norm",
        "--include=jovenes_norm",
        "--include=mayores_norm",
        "--include=poblacion_abs",
        "--include=actividad_norm",
        "--include=actividad_abs",
        "--include=uso_comercial_norm",
        "--include=antiguedad_norm",
        $inputPath
    )
    & tippecanoe @args
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo tippecanoe con codigo $LASTEXITCODE"
    }
}
else {
    $hasWsl = Get-Command wsl -ErrorAction SilentlyContinue
    if (-not $hasWsl) {
        throw 'No se encontro tippecanoe en PATH ni WSL disponible.'
    }

    wsl -d Ubuntu -- bash -lc "echo wsl_ok" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'No se encontro la distro Ubuntu en WSL. Instalala y reintenta.'
    }

    $linuxRoot = $repoRoot -replace '\\', '/'
    $linuxRoot = "/mnt/$($linuxRoot.Substring(0,1).ToLower())/$($linuxRoot.Substring(3))"

    wsl -d Ubuntu -- bash -lc "cd '$linuxRoot' && bash etl/generate_tiles.sh"
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo generate_tiles.sh via WSL con codigo $LASTEXITCODE"
    }
}

if (-not (Test-Path $outputPath)) {
    throw "No se genero el archivo MBTiles en $outputPath"
}

Write-Host "Teselas generadas: $outputPath"
