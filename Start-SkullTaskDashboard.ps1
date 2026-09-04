param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Get-Command python -ErrorAction Stop
$arguments = @((Join-Path $root 'task_dashboard.py'))
if (-not $NoBrowser) { $arguments += '--open' }
& $python.Source @arguments
