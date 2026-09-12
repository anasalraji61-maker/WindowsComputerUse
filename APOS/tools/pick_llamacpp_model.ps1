# Select a complete GGUF model (skip incomplete/corrupt downloads).
param(
    [Parameter(Mandatory = $true)]
    [string]$ModelDir
)

# Default: prefer 3B (stable). Set COS_LLAMA_PREFER=7b to try 7B.
$prefer = ($env:COS_LLAMA_PREFER, '3b' | Select-Object -First 1).ToLower()

$bySize = @{
    '14b' = @(
        @{ Filter = '*14B*Q4_K_M*.gguf'; Min = 8GB },
        @{ Filter = '*14B*.gguf'; Min = 8GB }
    )
    '7b' = @(
        @{ Filter = '*7B*Q4_K_M*.gguf'; Min = 4GB },
        @{ Filter = '*7B*.gguf'; Min = 4GB }
    )
    '3b' = @(
        @{ Filter = '*3B*Q4_K_M*.gguf'; Min = 1.8GB },
        @{ Filter = '*3B*.gguf'; Min = 1.8GB }
    )
}

$order = switch ($prefer) {
    '14b' { @('14b', '7b', '3b') }
    '7b'  { @('7b', '3b', '14b') }
    default { @('3b', '7b', '14b') }
}

$candidates = @()
foreach ($k in $order) { $candidates += $bySize[$k] }
$candidates += @{ Filter = '*.gguf'; Min = 100MB }

foreach ($c in $candidates) {
    $hit = Get-ChildItem -Path $ModelDir -Filter $c.Filter -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -ge $c.Min -and $_.Name -notmatch '\.corrupt|\.part' } |
        Sort-Object Length -Descending |
        Select-Object -First 1
    if ($hit) {
        Write-Output $hit.FullName
        exit 0
    }
}
exit 1
