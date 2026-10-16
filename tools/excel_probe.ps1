param([string]$Path, [string]$ScenarioFile, [string]$Out)
# Drives Excel itself through the input scenarios in excel/probe_scenarios.json and writes what Excel's formulas
# returned, so tools/verify_workbook.py can compare them with an independent Python calculation.
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Path)
  $inp = $wb.Worksheets.Item('Inputs'); $sz = $wb.Worksheets.Item('Sizing')
  $st = $wb.Worksheets.Item('States'); $ck = $wb.Worksheets.Item('Checks')
  # Windows PowerShell 5.1 hands back a JSON array as one object; the pipeline unrolls it.
  $scenarios = @(Get-Content -Raw -Path $ScenarioFile | ConvertFrom-Json | ForEach-Object { $_ })
  $segNames = @('Endocrinology', 'Primary care physician', 'Primary care NP or PA', 'Oncology specialist')
  $result = @()
  foreach ($s in $scenarios) {
    $inp.Range('C4').Value2 = [string]$s.franchise
    $inp.Range('C8').Value2 = [double]$s.capacity.diabetes[0]; $inp.Range('D8').Value2 = [double]$s.capacity.diabetes[1]
    $inp.Range('C9').Value2 = [double]$s.capacity.oncology[0]; $inp.Range('D9').Value2 = [double]$s.capacity.oncology[1]
    for ($i = 0; $i -lt 4; $i++) {
      $plan = $s.plan.($segNames[$i])
      $inp.Cells.Item(14 + $i, 5).Value2 = [double]$plan.calls
      $inp.Cells.Item(14 + $i, 6).Value2 = [double]$plan.share
    }
    $wb.Application.CalculateFull()
    $head = @(); foreach ($r in 4..9) { $head += $sz.Cells.Item($r, 3).Value2 }
    $sv = $sz.Range('B12:G16').Value2
    $segtab = @(); for ($i = 1; $i -le 5; $i++) { $r = @(); for ($c = 1; $c -le 6; $c++) { $r += ,$sv[$i, $c] }; $segtab += ,$r }
    $tv = $st.Range('A6:H57').Value2
    $states = @(); for ($i = 1; $i -le 52; $i++) { $r = @(); for ($c = 1; $c -le 8; $c++) { $r += ,$tv[$i, $c] }; $states += ,$r }
    $checks = @(); foreach ($r in 5..10) { $checks += [string]$ck.Cells.Item($r, 5).Value2 }
    $result += [pscustomobject]@{ id = $s.id; inputs = $s; head = $head; segtab = $segtab; states = $states; checks = $checks;
                                  overall = [string]$ck.Range('E12').Value2 }
  }
  $result | ConvertTo-Json -Depth 7 -Compress | Set-Content -Path $Out -Encoding UTF8
  $wb.Close($false)
  "ok"
} finally { $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
