# LiveCoinWatch Data Collector Runner
# This script loads the environment variables from config/env and runs the collector

param(
    [switch]$All,                    # Collect all available cryptocurrencies
    [int]$Limit = 50,               # Maximum number of coins (default: 50)
    [int]$MaxCoins,                 # Maximum coins when using -All
    [int]$Offset = 0,               # Starting offset
    [switch]$Help                   # Show help
)

if ($Help) {
    Write-Host "LiveCoinWatch Data Collector" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\run_livecoinwatch.ps1                    # Collect top 50 coins (default)"
    Write-Host "  .\run_livecoinwatch.ps1 -Limit 100         # Collect top 100 coins"
    Write-Host "  .\run_livecoinwatch.ps1 -All               # Collect ALL available coins"
    Write-Host "  .\run_livecoinwatch.ps1 -All -MaxCoins 500 # Collect up to 500 coins"
    Write-Host "  .\run_livecoinwatch.ps1 -All -Offset 1000  # Resume from offset 1000"
    Write-Host ""
    Write-Host "Parameters:" -ForegroundColor Yellow
    Write-Host "  -All        Collect all available cryptocurrencies"
    Write-Host "  -Limit      Maximum number of coins to collect (default: 50)"
    Write-Host "  -MaxCoins   Maximum coins when using -All"
    Write-Host "  -Offset     Starting offset for collection"
    Write-Host "  -Help       Show this help message"
    Write-Host ""
    exit 0
}

# Load environment variables from config file
$configFile = Join-Path $PSScriptRoot "config" "env"

if (Test-Path $configFile) {
    Write-Host "Loading environment variables from config/env..." -ForegroundColor Green
    
    Get-Content $configFile | ForEach-Object {
        if ($_ -match "^([^#][^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, [EnvironmentVariableTarget]::Process)
            Write-Host "Set $name" -ForegroundColor Yellow
        }
    }
    
    # Build command arguments
    $args = @()
    
    if ($All) {
        $args += "--all"
        Write-Host "`nRunning LiveCoinWatch collector for ALL cryptocurrencies..." -ForegroundColor Green
        
        if ($MaxCoins) {
            $args += "--max-coins"
            $args += $MaxCoins
            Write-Host "Limited to maximum $MaxCoins coins" -ForegroundColor Yellow
        }
        
        if ($Offset -gt 0) {
            $args += "--offset"
            $args += $Offset
            Write-Host "Starting from offset $Offset" -ForegroundColor Yellow
        }
    } else {
        $args += "--limit"
        $args += $Limit
        Write-Host "`nRunning LiveCoinWatch collector for top $Limit cryptocurrencies..." -ForegroundColor Green
    }
    
    # Show warning for full collection
    if ($All -and -not $MaxCoins) {
        Write-Host ""
        Write-Warning "You're about to collect ALL available cryptocurrencies!"
        Write-Host "This may use a significant portion of your daily API limit." -ForegroundColor Yellow
        Write-Host "Press Ctrl+C to cancel or any key to continue..." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Write-Host ""
    }
    
    # Run the collector
    python src/collectors/livecoinwatch.py @args
    
} else {
    Write-Error "Config file not found at: $configFile"
    Write-Host "Please ensure config/env exists with your API keys." -ForegroundColor Red
    exit 1
}
