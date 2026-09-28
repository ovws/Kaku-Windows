$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$commit = 'b09b56c29c1e367e598b60ca266e2cc9038751e0'
$baseUrl = "https://raw.githubusercontent.com/wez/wezterm/$commit/assets/windows"
$assetRoot = Join-Path $PSScriptRoot '..\assets\windows'

$assets = @(
    @{ Path = 'manifest.manifest'; Sha256 = '09f8b4e89f09cbabf602fa18a075fa0ce1815237e628c5351bbd4ec148ac9a3b' }
    @{ Path = 'console.manifest'; Sha256 = '56a172a82abdcd55034f626cb6da105f8c51e96650d22b8e7c16757e0f26922a' }
    @{ Path = 'terminal.ico'; Sha256 = '80ba901168a64f065ad166fa76688b7843b68b61e4ec6e8e954150c02ef4b105' }
    @{ Path = 'conhost/conpty.dll'; Sha256 = '375bfb0479b6c53836ab307e3f9fd17bedbd733f2e9690943d0f12e72fb80777' }
    @{ Path = 'conhost/OpenConsole.exe'; Sha256 = '55b18996761c88c351820e82508e05ab0ec2194aeead20724fdfaeedec076ef4' }
    @{ Path = 'angle/libEGL.dll'; Sha256 = '21a18f35147c0c1413c94a6354a9b5e4f58cddb54d2adac664a6478e47df054b' }
    @{ Path = 'angle/libGLESv2.dll'; Sha256 = '7360d7e4d2ed34d1b6224fcb00592db3f86827bb75106a89dc457504df188618' }
    @{ Path = 'mesa/opengl32.dll'; Sha256 = 'd109ab0e8f7aa6f00992368b72c9a8aa0cf6d1b1563c3ab1caedbdba9c4476ba' }
)

$ProgressPreference = 'SilentlyContinue'
foreach ($asset in $assets) {
    $destination = Join-Path $assetRoot $asset.Path
    $directory = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $directory | Out-Null

    $temporary = "$destination.download"
    $url = "$baseUrl/$($asset.Path)"
    Write-Host "Downloading $($asset.Path)"
    Invoke-WebRequest -Uri $url -OutFile $temporary

    $actualHash = (Get-FileHash -Path $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $asset.Sha256) {
        Remove-Item -Force $temporary
        throw "SHA-256 mismatch for $($asset.Path): expected $($asset.Sha256), got $actualHash"
    }

    Move-Item -Force $temporary $destination
}
