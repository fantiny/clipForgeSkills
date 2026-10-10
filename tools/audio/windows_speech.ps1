param([switch]$ListVoices, [string]$Voice, [string]$TextFile, [string]$OutputWave)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($ListVoices) {
        $voices = @($speaker.GetInstalledVoices() | Where-Object { $_.Enabled } | ForEach-Object {
            @{ name = $_.VoiceInfo.Name; culture = $_.VoiceInfo.Culture.Name }
        })
        @{ voices = $voices } | ConvertTo-Json -Depth 3 -Compress
    } else {
        if (-not $Voice -or -not $TextFile -or -not $OutputWave) { throw 'Voice, TextFile and OutputWave are required' }
        $speaker.SelectVoice($Voice)
        $speaker.SetOutputToWaveFile($OutputWave)
        $speaker.Speak([System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8))
        $speaker.SetOutputToNull()
        @{ voice = $speaker.Voice.Name; output = $OutputWave } | ConvertTo-Json -Compress
    }
} finally {
    $speaker.Dispose()
}
