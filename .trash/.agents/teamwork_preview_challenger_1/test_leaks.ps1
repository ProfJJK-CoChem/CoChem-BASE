$targetDir = 'D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents'

Write-Host "=== 1. AUDITING 15 .agent.md FILES ==="
$agentFiles = Get-ChildItem -Path $targetDir -Filter "*.agent.md"

foreach ($f in $agentFiles) {
    Write-Host "Checking $($f.Name)..."
    $content = Get-Content -Path $f.FullName -Raw
    
    # Check ansac
    if ($content -match '(?i)ansac') {
        Write-Host "  [FAIL] ansac found in $($f.Name)"
    }
    # Check C:\Users or C:/Users
    if ($content -match '(?i)C:\\Users|C:/Users') {
        Write-Host "  [FAIL] C:\Users path found in $($f.Name)"
    }
    # Check D:\Gdrive or D:/Gdrive or __CoChem
    if ($content -match '(?i)D:\\Gdrive|D:/Gdrive|__CoChem') {
        Write-Host "  [FAIL] D:\Gdrive or __CoChem path found in $($f.Name)"
    }
    # Check Drive letters C: or D:
    if ($content -match '(?i)[C-D]:[/\\]') {
        Write-Host "  [FAIL] Drive letter found in $($f.Name)"
    }
    # Check URL encoded variants
    if ($content -match '(?i)C%3A|D%3A|%61%6e%73%61%63|file:///') {
        Write-Host "  [FAIL] URL encoded leak found in $($f.Name)"
    }
}

Write-Host "`n=== 2. AUDITING ALL OTHER FILES IN .AGENTS ==="
$allFiles = Get-ChildItem -Path $targetDir -Recurse -File

$leaks = @()

foreach ($f in $allFiles) {
    $relativePath = $f.FullName.Substring($targetDir.Length)
    $lines = Get-Content -Path $f.FullName -ErrorAction SilentlyContinue
    if (-not $lines) { continue }
    
    $lineNum = 0
    foreach ($line in $lines) {
        $lineNum++
        
        # Test case-insensitive ansac
        if ($line -match '(?i)ansac') {
            # Check if it's just mentioning the instruction / pattern in a reviewer/challenger doc vs actual leak
            $leaks += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Type = 'ansac'; Snippet = $line.Trim() }
        }
        
        # Test C:\Users or C:/Users
        if ($line -match '(?i)C:\\Users|C:/Users') {
            $leaks += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Type = 'C_Users'; Snippet = $line.Trim() }
        }

        # Test D:\Gdrive or d:/gdrive
        if ($line -match '(?i)D:\\Gdrive|D:/Gdrive') {
            $leaks += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Type = 'D_Gdrive'; Snippet = $line.Trim() }
        }

        # Test drive letters C: or D:
        if ($line -match '(?i)[C-D]:[/\\]') {
            $leaks += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Type = 'DriveLetter'; Snippet = $line.Trim() }
        }
        
        # Test URL encoded
        if ($line -match '(?i)[C-D]%3A|%61%6e%73%61%63') {
            $leaks += [PSCustomObject]@{ File = $relativePath; Line = $lineNum; Type = 'UrlEncoded'; Snippet = $line.Trim() }
        }
    }
}

Write-Host "Total findings across all files: $($leaks.Count)"
Write-Host "Findings in *.agent.md files:"
$leaks | Where-Object { $_.File -like "*.agent.md*" } | Format-Table -AutoSize

Write-Host "Findings in non-agent files (DISPATCH / BRIEFING / handoff / analysis):"
$leaks | Where-Object { $_.File -notlike "*.agent.md*" } | Select-Object -First 30 | Format-Table -AutoSize
