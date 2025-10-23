# List of Commands

List of commands to quickly process an entire type of content.

To view the current progress run `python scripts/analysis/monitor_progress.py`

## YouTube

`while ($true) { Start-Sleep 100; python scripts\analysis\run_comprehensive_analysis.py --disable medium,reddit,website,whitepaper; Start-Sleep 6600; }`

## Reddit

`while ($true) { python scripts\analysis\run_comprehensive_analysis.py --disable medium,website,whitepaper,youtube; Start-Sleep 600 }`

## Telegram

`while ($true) { python src/analyzers/telegram_analyzer.py batch 3; Start-Sleep 3600 }`

## Medium

`while ($true) { Start-Sleep 14400; python scripts\analysis\run_comprehensive_analysis.py --disable reddit,website,whitepaper,youtube }`

## Website

`while ($true) { python scripts\analysis\run_comprehensive_analysis.py --disable medium,reddit,whitepaper,youtube; Start-Sleep 10 }`

## Whitepaper

`while ($true) { python scripts\analysis\run_comprehensive_analysis.py --disable medium,reddit,website,youtube; Start-Sleep 5 }`

## Twitter

`while ($true) { python src/analyzers/twitter_analyzer.py batch 1; Start-Sleep 900 }`