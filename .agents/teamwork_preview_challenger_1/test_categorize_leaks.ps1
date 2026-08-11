$targetDir = 'D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents'
$allFiles = Get-ChildItem -Path $targetDir -Recurse -File

$auditList = @()

foreach ($f in $allFiles) {
    # Skip test scripts created by challenger
    if ($f.Name -like "test_*.ps1") { continue }
    
    $relativePath = $f.FullName.Substring($targetDir.Length)
    $lines = Get-Content -Path $f.FullName -ErrorAction SilentlyContinue
    if (-not $lines) { continue }
    
    $lineNum = 0
    foreach ($line in $lines) {
        $lineNum++
        
        # Check ansac
        if ($line -match '(?i)ansac') {
            $auditList += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Pattern = 'ansac'; Content = $line.Trim() }
        }
        # Check C:\Users
        elseif ($line -match '(?i)c:\\users|c:/users') {
            $auditList += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Pattern = 'C_Users'; Content = $line.Trim() }
        }
        # Check D:\Gdrive
        elseif ($line -match '(?i)d:\\gdrive|d:/gdrive') {
            $auditList += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Pattern = 'D_Gdrive'; Content = $line.Trim() }
        }
    }
}

Write-Host "Total matches in non-test files: $($auditList.Count)"
$auditList | Group-Object File | Select-Object Count, Name | Format-Table -AutoSize
