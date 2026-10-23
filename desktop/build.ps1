param(
    [switch]$SkipInstall,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$desktop = Join-Path $root 'desktop'
$dist = Join-Path $desktop 'dist'
$build = Join-Path $desktop 'build'
$venv = Join-Path $desktop '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
$env:PIP_CACHE_DIR = Join-Path $desktop '.pip-cache'

Push-Location $root
try {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if ($SkipInstall) {
            throw 'The desktop build environment does not exist. Run build.ps1 without -SkipInstall first.'
        }
        python -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create the desktop build environment.' }
    }

    if (-not $SkipInstall) {
        & $venvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw 'Pip upgrade failed.' }
        & $venvPython -m pip install -r backend/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
        & $venvPython -m pip install -r agent/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Agent dependency installation failed.' }
        & $venvPython -m pip install -r frontend/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        & $venvPython -m pip install -r desktop/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Desktop dependency installation failed.' }
    }

    & $venvPython desktop/create_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed.' }
    & $venvPython -m PyInstaller --noconfirm --clean `
        --distpath $dist `
        --workpath $build `
        desktop/MingChaShuHao.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    Copy-Item -LiteralPath (Join-Path $desktop 'README.md') `
        -Destination (Join-Path $dist 'MingChaShuHao\Desktop-README.md') -Force
    $runGuideName = (-join @(
        [char]0x8FD0,
        [char]0x884C,
        [char]0x8BF4,
        [char]0x660E
    )) + '.txt'
    Copy-Item -LiteralPath (Join-Path $desktop $runGuideName) `
        -Destination (Join-Path $dist "MingChaShuHao\$runGuideName") -Force

    $portableArchive = Join-Path $dist 'MingChaShuHao-Portable-3.0.0.zip'
    Compress-Archive -LiteralPath (Join-Path $dist 'MingChaShuHao') `
        -DestinationPath $portableArchive -CompressionLevel Optimal -Force

    if (-not $SkipInstaller) {
        $isccCandidates = @(
            (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
            (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
        )
        $iscc = $isccCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
        if ($iscc) {
            & $iscc (Join-Path $desktop 'installer.iss')
        } else {
            Write-Host 'Inno Setup was not found. The portable application is ready.'
        }
    }

    Write-Host ''
    Write-Host 'Desktop build completed:'
    Write-Host (Join-Path $dist 'MingChaShuHao\MingChaShuHao.exe')
    Write-Host 'Portable archive:'
    Write-Host $portableArchive
}
finally {
    Pop-Location
}
