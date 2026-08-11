$targetDir = 'D:\Gdrive\__CoChem\GitHub-Repo\CoChem-BASE\.agents'
$agentFiles = Get-ChildItem -Path $targetDir -Filter "*.agent.md"

Write-Host "Found $($agentFiles.Count) agent configuration files:"
foreach ($f in $agentFiles) {
    Write-Host " - $($f.Name)"
}

Write-Host "`n=== DETAILED ANALYSIS OF 15 .agent.md FILES ==="

$agentAudit = @()

foreach ($f in $agentFiles) {
    $lines = Get-Content -Path $f.FullName
    $lineNum = 0
    foreach ($line in $lines) {
        $lineNum++
        
        # Check ansac
        if ($line -match '(?i)ansac') {
            $agentAudit += [PSCustomObject]@{ File = $f.Name; Line = $lineNum; Check = 'LEAK: ansac'; Snippet = $line }
        }
        
        # Check C: or D: drive letters
        if ($line -match '(?i)[a-z]:[/\\]') {
            $agentAudit += [PSCustomObject]@{ File = $f.Name; Line = $lineNum; Check = 'LEAK: Drive Letter Path'; Snippet = $line }
        }
        
        # Check Users directory
        if ($line -match '(?i)users[/\\]') {
            $agentAudit += [PSCustomObject]@{ File = $f.Name; Line = $lineNum; Check = 'LEAK: Users directory'; Snippet = $line }
        }

        # Check Gdrive / CoChem
        if ($line -match '(?i)gdrive|__cochem') {
            $agentAudit += [PSCustomObject]@{ File = $f.Name; Line = $lineNum; Check = 'LEAK: Gdrive or __CoChem'; Snippet = $line }
        }

        # Check URL encoded or hex strings
        if ($line -match '(?i)%3a|%5c|%2f|%61%6e%73%61%63') {
            $agentAudit += [PSCustomObject]@{ File = $f.Name; Line = $lineNum; Check = 'LEAK: URL Encoded Path'; Snippet = $line }
        }

        # Count proper sanitization placeholders
        if ($line -match '<USER_HOME>') {
            # Verified placeholder
        }
        if ($line -match '<COCHEM_WORKSPACE>') {
            # Verified placeholder
        }
    }
}

if ($agentAudit.Count -eq 0) {
    Write-Host "`n[RESULT] 0 leaks found in all 15 .agent.md files!"
} else {
    Write-Host "`n[RESULT] Leaks found in .agent.md files:"
    $agentAudit | Format-Table -AutoSize
}

Write-Host "`n=== PLACEHOLDER USAGE STATS IN .agent.md FILES ==="
foreach ($f in $agentFiles) {
    $content = Get-Content -Path $f.FullName -Raw
    $userHomeMatches = ([regex]::Matches($content, '<USER_HOME>')).Count
    $cochemWorkspaceMatches = ([regex]::Matches($content, '<COCHEM_WORKSPACE>')).Count
    Write-Host "$($f.Name): <USER_HOME> x$userHomeMatches | <COCHEM_WORKSPACE> x$cochemWorkspaceMatches"
}
