# Sintesis de voz con las voces de Microsoft instaladas en Windows (Raul y Sabina, espanol de Mexico).
# Lee un JSON con [{ "texto": "...", "archivo": "C:\\...\\x.wav", "voz": "Raul" | "Sabina" }] y escribe cada WAV.
# Usa la API de Windows (Windows.Media.SpeechSynthesis), que tiene las voces "OneCore" (Raul) ademas de las de escritorio.
#   powershell -ExecutionPolicy Bypass -File tools\manual\voz.ps1 -Lista lista.json
param([Parameter(Mandatory = $true)][string]$Lista, [string]$Velocidad = "-4%")

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Esperar($op, [Type]$tipo) {
    $t = $asTask.MakeGenericMethod($tipo).Invoke($null, @($op))
    $null = $t.Wait(-1)
    return $t.Result
}

$sint = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voces = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
$items = Get-Content -Raw -Encoding UTF8 $Lista | ConvertFrom-Json
foreach ($it in $items) {
    $v = $voces | Where-Object { $_.DisplayName -like "*$($it.voz)*" } | Select-Object -First 1
    if ($v) { $sint.Voice = $v }
    $texto = [System.Security.SecurityElement]::Escape($it.texto)
    $ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='es-MX'><prosody rate='$Velocidad'>$texto</prosody></speak>"
    $flujo = Esperar ($sint.SynthesizeSsmlToStreamAsync($ssml)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $lector = New-Object Windows.Storage.Streams.DataReader($flujo.GetInputStreamAt(0))
    $n = [uint32]$flujo.Size
    $null = Esperar ($lector.LoadAsync($n)) ([uint32])
    $bytes = New-Object byte[] $n
    $lector.ReadBytes($bytes)
    [System.IO.File]::WriteAllBytes($it.archivo, $bytes)
    $lector.Dispose(); $flujo.Dispose()
}
Write-Output "voces listas: $($items.Count)"
