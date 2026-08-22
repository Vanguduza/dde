#Requires -Version 5.1
# Deprecated: launches the GUI wizard.
$wizard = Join-Path (Split-Path $PSScriptRoot -Parent) "DdeSetupWizard.exe"
& $wizard
