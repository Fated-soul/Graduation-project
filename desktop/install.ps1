param(
    [switch]$NoShortcuts
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $PSScriptRoot 'dist\MingChaShuHao'
$sourceExe = Join-Path $source 'MingChaShuHao.exe'
$agentEnv = Join-Path $root 'agent\.env'
$envTemplate = Join-Path $PSScriptRoot '.env.example'
$installRoot = Join-Path $env:LOCALAPPDATA 'Programs\MingChaShuHao'
$installedExe = Join-Path $installRoot 'MingChaShuHao.exe'
$dataRoot = Join-Path $env:LOCALAPPDATA 'MingChaShuHao'
$configDir = Join-Path $dataRoot 'config'
$configPath = Join-Path $configDir '.env'

if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw "Desktop build not found: $sourceExe"
}
if (-not (Test-Path -LiteralPath $agentEnv)) {
    throw "Agent configuration not found: $agentEnv"
}
if (-not (Test-Path -LiteralPath $envTemplate)) {
    throw "Desktop configuration template not found: $envTemplate"
}

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dataRoot 'logs') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $dataRoot 'cache') -Force | Out-Null

# Robocopy keeps hidden runtime directories and updates an existing local install
# without deleting user-created files.
& robocopy $source $installRoot /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Application file deployment failed. Robocopy exit code: $LASTEXITCODE"
}

$templateContent = [IO.File]::ReadAllText($envTemplate, [Text.Encoding]::UTF8).TrimEnd()
$agentContent = [IO.File]::ReadAllText($agentEnv, [Text.Encoding]::UTF8).Trim()
$mergedContent = $templateContent + [Environment]::NewLine + [Environment]::NewLine +
    '# Imported from the project agent/.env during local deployment.' +
    [Environment]::NewLine + $agentContent + [Environment]::NewLine
[IO.File]::WriteAllText(
    $configPath,
    $mergedContent,
    [Text.UTF8Encoding]::new($false)
)

if (-not $NoShortcuts) {
    $shell = New-Object -ComObject WScript.Shell
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    $startMenuPath = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    $shortcutName = (-join @(
        [char]0x660E,
        [char]0x5BDF,
        [char]0x9F20,
        [char]0x6BEB
    )) + '.lnk'
    $shortcutFolders = @($desktopPath, $startMenuPath)

    # Remove shortcuts from earlier deployments only when they point to this
    # exact application. This also repairs names created by a legacy code page.
    foreach ($folder in $shortcutFolders) {
        Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -ErrorAction SilentlyContinue |
            ForEach-Object {
                $existingShortcut = $shell.CreateShortcut($_.FullName)
                if ([string]::Equals(
                    $existingShortcut.TargetPath,
                    $installedExe,
                    [StringComparison]::OrdinalIgnoreCase
                )) {
                    Remove-Item -LiteralPath $_.FullName -Force
                }
            }
    }

    foreach ($shortcutPath in ($shortcutFolders | ForEach-Object {
        Join-Path $_ $shortcutName
    })) {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $installedExe
        $shortcut.WorkingDirectory = $installRoot
        $shortcut.IconLocation = "$installedExe,0"
        $shortcut.Description = 'MingChaShuHao research workstation'
        $shortcut.Save()
    }
}

Write-Host "Application installed: $installedExe"
Write-Host "Runtime configuration: $configPath"
Write-Host 'The current agent/.env configuration has been imported.'
