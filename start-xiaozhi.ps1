$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot 'main\xiaozhi-server\.venv\Scripts\python.exe'
$pythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
$opusDirectory = Join-Path $projectRoot 'main\xiaozhi-server\.venv\Lib\site-packages\pyogg'

if (Test-Path -LiteralPath (Join-Path $opusDirectory 'opus.dll') -PathType Leaf) {
    $env:PATH = "$opusDirectory;$env:PATH"
}

$services = @(
    @{
        Name = 'Xiaozhi HTTP Server'
        Directory = Join-Path $projectRoot 'main\xiaozhi-http-server'
        EntryPoint = 'app.py'
    }
    @{
        Name = 'Digital Human'
        Directory = Join-Path $projectRoot 'main\digital-human'
        EntryPoint = 'start.py'
    }
    @{
        Name = 'Xiaozhi Server'
        Directory = Join-Path $projectRoot 'main\xiaozhi-server'
        EntryPoint = 'app.py'
    }
)

foreach ($service in $services) {
    if (-not (Test-Path -LiteralPath $service.Directory -PathType Container)) {
        throw "Service directory not found: $($service.Directory)"
    }

    $command = "title $($service.Name) && `"$pythonExe`" $($service.EntryPoint)"
    Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/k', $command `
        -WorkingDirectory $service.Directory
}

Write-Host 'Three Xiaozhi service windows have been opened.'
