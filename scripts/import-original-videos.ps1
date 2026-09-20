param(
  [Parameter(Mandatory=$true)][string]$SourceDirectory,
  [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$siteRoot = Split-Path -Parent $PSScriptRoot

foreach ($clip in @('7733','8247','8472','7264','9277')) {
  $source = Join-Path $SourceDirectory "IMG_$clip.MOV"
  $target = Join-Path $siteRoot "media/video/original-$clip.mp4"
  if (!(Test-Path -LiteralPath $source)) { throw "Missing original: $source" }
  if (!$VerifyOnly) {
    # Stream copy only: preserve encoded pixels, HDR/Dolby Vision, and rotation.
    # unofficial is required by the MP4 muxer to retain the Dolby Vision record.
    & ffmpeg -hide_banner -loglevel error -i $source -map 0:v:0 -c:v copy -map_metadata -1 -an -strict unofficial -movflags +faststart -y $target
    if ($LASTEXITCODE -ne 0) { throw "Original-video import failed: $clip" }
  }
  $sourceHashes = @(& ffprobe -v error -select_streams v:0 -show_packets -show_entries packet=data_hash -show_data_hash sha256 -of csv=p=0 $source)
  if ($LASTEXITCODE -ne 0) { throw "Cannot inspect original: $clip" }
  $targetHashes = @(& ffprobe -v error -select_streams v:0 -show_packets -show_entries packet=data_hash -show_data_hash sha256 -of csv=p=0 $target)
  if ($LASTEXITCODE -ne 0) { throw "Cannot inspect delivery file: $clip" }
  if (!$sourceHashes.Count -or ($sourceHashes -join "`n") -cne ($targetHashes -join "`n")) {
    throw "Encoded video data changed: $clip"
  }
  $fields = 'stream=codec_name,profile,pix_fmt,width,height,color_range,color_space,color_transfer,color_primaries:stream_side_data=rotation,dv_profile,dv_level,rpu_present_flag,dv_bl_signal_compatibility_id'
  $sourceColor = & ffprobe -v error -select_streams v:0 -show_entries $fields -of compact $source
  if ($LASTEXITCODE -ne 0) { throw "Cannot inspect source color: $clip" }
  $targetColor = & ffprobe -v error -select_streams v:0 -show_entries $fields -of compact $target
  if ($LASTEXITCODE -ne 0 -or $sourceColor -cne $targetColor) { throw "Source color metadata changed: $clip" }
  Write-Output "$clip`: identical encoded video packets and original color metadata preserved."
}
