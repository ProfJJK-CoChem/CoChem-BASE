$sourceDir = 'C:\Users\ansac\.gemini\config\agents'
$targetDir = 'D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents'

$sourceFiles = Get-ChildItem -Path $sourceDir -Filter "*.agent.md"

Write-Host "Comparing $($sourceFiles.Count) files between $sourceDir and $targetDir..."

$diffsFound = 0

foreach ($sf in $sourceFiles) {
    $targetFile = Join-Path $targetDir $sf.Name
    if (-not (Test-Path $targetFile)) {
        Write-Host "[MISSING] $targetFile does not exist!"
        $diffsFound++
        continue
    }
    
    $srcContent = Get-Content -Path $sf.FullName -Raw
    $tgtContent = Get-Content -Path $targetFile -Raw
    
    # Sanitize srcContent the same way worker_m1 was supposed to do
    $sanitizedSrc = $srcContent -replace '(?i)c:[\/\\]+users[\/\\]+ansac[\/\\]+\.gemini[\/\\]+config[\/\\]+agents', '<USER_HOME>\.gemini\config\agents'
    $sanitizedSrc = $sanitizedSrc -replace '(?i)c:[\/\\]+users[\/\\]+ansac', '<USER_HOME>'
    $sanitizedSrc = $sanitizedSrc -replace '(?i)d:[\/\\]+gdrive[\/\\]+__cochem', '<COCHEM_WORKSPACE>'
    $sanitizedSrc = $sanitizedSrc -replace '(?i)d:[\/\\]+gdrive', '<GDRIVE_ROOT>'
    
    # Normalize line endings
    $sanitizedSrcNorm = $sanitizedSrc -replace "`r`n", "`n"
    $tgtContentNorm = $tgtContent -replace "`r`n", "`n"
    
    if ($sanitizedSrcNorm.Trim() -eq $tgtContentNorm.Trim()) {
        Write-Host "  [MATCH] $($sf.Name) matches perfectly!"
    } else {
        Write-Host "  [MISMATCH] $($sf.Name) does NOT match!"
        $diffsFound++
    }
}

Write-Host "Total diffs found: $diffsFound"
