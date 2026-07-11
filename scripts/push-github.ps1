Set-Location $PSScriptRoot\..

$credLines = @("protocol=https", "host=github.com", "") | git credential fill
$token = ($credLines | Where-Object { $_ -match '^password=' }) -replace '^password=', ''

$headers = @{
    Authorization              = "Bearer $token"
    Accept                     = "application/vnd.github+json"
    "X-GitHub-Api-Version"     = "2022-11-28"
}
$body = @{
    name        = "kampff-skills"
    description = "Kampff agent skill — human analysis from text. spectrograph + prebuilt collectors."
    private     = $false
} | ConvertTo-Json

try {
    $repo = Invoke-RestMethod -Method POST -Uri "https://api.github.com/user/repos" -Headers $headers -Body $body -ContentType "application/json"
    Write-Host "Created: $($repo.html_url)"
} catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 422) {
        Write-Host "Repository already exists, pushing..."
    } else {
        throw
    }
}

git remote remove origin 2>$null
git remote add origin https://github.com/YangKangSung/kampff-skills.git
git push -u origin main
Write-Host "Done: https://github.com/YangKangSung/kampff-skills"