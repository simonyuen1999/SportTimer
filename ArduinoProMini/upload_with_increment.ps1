<#
PowerShell helper: increment build version in build_version.h, then compile and upload
Usage:
  .\upload_with_increment.ps1 -Port COM4
  .\upload_with_increment.ps1 -Port COM4 -Fqbn "arduino:avr:pro:cpu=16MHzatmega328"

Notes:
- This script updates BUILD_VERSION in build_version.h (mod 0x10000 / 16-bit) but does NOT commit changes to git.
- Requires arduino-cli on PATH.
#>
param(
    [string] $Port = "COM4",
    [string] $Fqbn = "arduino:avr:pro:cpu=16MHzatmega328",
    [string] $SketchPath = "c:\github\SportTimer\ArduinoProMini",
    [string] $BuildPath = "c:\github\SportTimer\ArduinoProMini\build"
)

$headerPath = Join-Path $SketchPath "build_version.h"
if (-not (Test-Path -LiteralPath $headerPath)) {
    Write-Error "build_version.h not found at $headerPath"
    exit 2
}

# Read and parse current hex value
$content = Get-Content -LiteralPath $headerPath -Raw
# Accept 1..4 hex digits to support 16-bit BUILD_VERSION (0x0000..0xFFFF)
$regex = '#define\s+BUILD_VERSION\s+0x([0-9A-Fa-f]{1,4})'
$m = [System.Text.RegularExpressions.Regex]::Match($content, $regex)
if (-not $m.Success) {
    Write-Error "Could not find BUILD_VERSION macro in $headerPath"
    exit 3
}
$oldHex = $m.Groups[1].Value
$oldVal = [Convert]::ToInt32($oldHex,16)
# If the old value is 0xFFFF, wrap back to 0x0000 per rollover policy.
if ($oldVal -ge 0xFFFF) {
    $newVal = 0x0000
} else {
    $newVal = $oldVal + 1
}
# Format as 4-digit uppercase hex
$newHex = $newVal.ToString('X4')

# Replace in file
$newContent = [System.Text.RegularExpressions.Regex]::Replace($content, $regex, "#define BUILD_VERSION 0x$newHex")
Set-Content -LiteralPath $headerPath -Value $newContent -Encoding ASCII

Write-Host "Updated BUILD_VERSION: 0x$oldHex -> 0x$newHex (file: $headerPath)"

# Compile
Write-Host "Compiling sketch $SketchPath for $Fqbn..."
$compileCmd = "arduino-cli compile --fqbn `"$Fqbn`" `"$SketchPath`" --build-path `"$BuildPath`""
$compileRes = & cmd /c $compileCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Compile failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Compile completed."

# Upload (use build folder as input-dir)
Write-Host "Uploading to port $Port..."
$uploadCmd = "arduino-cli upload -p $Port --fqbn `"$Fqbn`" --input-dir `"$BuildPath`" `"$SketchPath`""
$uploadRes = & cmd /c $uploadCmd
if ($LASTEXITCODE -ne 0) {
    Write-Error "Upload failed (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
Write-Host "Upload completed."

# Print which version is now embedded (the new value)
Write-Host "Embedded BUILD_VERSION is now 0x$newHex"

exit 0
