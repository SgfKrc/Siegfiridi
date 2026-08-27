<#
.SYNOPSIS
    Siegfridi 一键环境配置脚本（Windows / PowerShell）

.DESCRIPTION
    检查 Python 版本 -> 创建 .venv -> 升级 pip -> 以可编辑模式安装项目
    及其依赖组，并在末尾做轻量验证（--version 与 pytest）。

    依赖组说明（与 pyproject.toml 对应）：
      dev            开发工具链（pytest / ruff / pyinstaller）——默认安装
      audio          音频解码与预处理（PyAV / librosa / soundfile）
      transcription  自动转录（basic-pitch / onnxruntime）
      synthesis      FluidSynth 合成（pyfluidsynth）

.EXAMPLE
    .\scripts\setup-env.ps1                 # 仅基础 + dev（推荐首先执行）
    .\scripts\setup-env.ps1 -All            # 一键安装全部依赖组
    .\scripts\setup-env.ps1 -Audio -Synthesis
    .\scripts\setup-env.ps1 -SkipChecks     # 跳过环境预检
#>
[CmdletBinding()]
param(
    [switch]$All,           # 安装全部可选依赖组
    [switch]$Audio,         # 安装 audio 组
    [switch]$Transcription, # 安装 transcription 组
    [switch]$Synthesis,     # 安装 synthesis 组
    [switch]$SkipChecks     # 跳过 Python/git 预检
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-OK([string]$Message) {
    Write-Host "    OK: $Message" -ForegroundColor Green
}

function Find-Python {
    # 优先 py launcher 选择 3.11/3.12，回退到 PATH 中的 python。
    # 注意：3.11 必须排在 3.12 之前——basic-pitch 在非 Darwin 且 Python>=3.11
    # 时依赖 tensorflow<2.15.1，而该版本没有支持 Python 3.12 的 Windows wheel。
    $candidates = @()
    foreach ($ver in @('3.11', '3.12')) {
        $py = Get-Command "py" -ErrorAction SilentlyContinue
        if ($py) {
            $candidates += , @("py -$ver", "-$ver")
        }
    }
    $candidates += , @('python', '')
    foreach ($cand in $candidates) {
        $label = $cand[0]
        $arg = $cand[1]
        try {
            $versionLine = if ($arg) {
                (& py $arg --version 2>&1)
            } else {
                (& python --version 2>&1)
            }
            if ($LASTEXITCODE -ne 0) { continue }
            if ($versionLine -match 'Python (\d+\.\d+\.\d+)') {
                $ver = [version]$Matches[1]
                if ($ver -ge [version]'3.11' -and $ver -lt [version]'3.13') {
                    return @{ Label = $label; Version = $ver; Arg = $arg }
                }
            }
        } catch {
            continue
        }
    }
    return $null
}

# ---------- 0. 预检 ----------
if (-not $SkipChecks) {
    Write-Step "预检环境（Python / git）"
    $pyInfo = Find-Python
    if (-not $pyInfo) {
        throw "未找到 Python 3.11 或 3.12，请先安装：https://www.python.org/downloads/windows/（安装时勾选 py launcher）"
    }
    Write-OK ("Python {0}（{1}）" -f $pyInfo.Version, $pyInfo.Label)

    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        Write-OK ("git {0}" -f ((git --version) -replace '^git version ', ''))
    } else {
        Write-Warning "未检测到 git；不会影响本次安装，但提交代码需要它"
    }
} else {
    $pyInfo = @{ Label = 'python'; Arg = ''; Version = '未知' }
}

# ---------- 1. 虚拟环境 ----------
$Root = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $Root '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Step "创建虚拟环境 .venv（Python $($pyInfo.Version)）"
    if ($pyInfo.Arg) {
        & py $pyInfo.Arg -m venv $VenvDir
    } else {
        & python -m venv $VenvDir
    }
    if ($LASTEXITCODE -ne 0) { throw "创建虚拟环境失败" }
} else {
    Write-OK "虚拟环境已存在：.venv"
}

# ---------- 2. 升级 pip ----------
Write-Step "升级 pip / 兼容版 setuptools / wheel"
# Basic Pitch 0.4.0 -> resampy 0.4.2 仍使用 pkg_resources；兼容提示要求 setuptools<81。
& $VenvPython -m pip install --upgrade pip 'setuptools<81' wheel
if ($LASTEXITCODE -ne 0) { throw "pip 升级失败" }

# ---------- 3. 安装项目与依赖组 ----------
$extras = @('dev')
if ($All) {
    $extras = @('dev', 'audio', 'transcription', 'synthesis')
} else {
    if ($Audio) { $extras += 'audio' }
    if ($Transcription) { $extras += 'transcription' }
    if ($Synthesis) { $extras += 'synthesis' }
}
$spec = '".[{0}]"' -f ($extras -join ',')

Write-Step "安装项目（可编辑模式）与依赖组：$($extras -join ' / ')"
Write-Host "    运行: $VenvPython -m pip install -e $spec"
& $VenvPython -m pip install -e $spec
if ($LASTEXITCODE -ne 0) {
    if ($All -or $extras.Count -gt 1) {
        # 可选组失败不阻塞整个环境：回退到仅 dev 再试一次
        Write-Warning "全量安装失败，回退安装基础 + dev 组……"
        & $VenvPython -m pip install -e '".[dev]"'
        if ($LASTEXITCODE -ne 0) { throw "基础与 dev 依赖安装失败" }
        Write-Warning "可选依赖组未安装成功，可按需重跑：-Audio / -Transcription / -Synthesis"
    } else {
        throw "基础与 dev 依赖安装失败"
    }
}

# ---------- 4. 轻量验证 ----------
Write-Step "验证安装"
& $VenvPython -m siegfridi --version
if ($LASTEXITCODE -ne 0) { throw "验证失败：siegfridi --version 无法运行" }

& $VenvPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "验证失败：pytest 未通过" }

# ---------- 5. 完成 ----------
Write-Host ""
Write-Host "环境就绪！" -ForegroundColor Green
Write-Host "  运行应用（开发模式）：" -ForegroundColor Yellow
Write-Host "      $VenvPython -m siegfridi"
Write-Host "  激活虚拟环境（PowerShell）：" -ForegroundColor Yellow
Write-Host "      & '$VenvDir\Scripts\Activate.ps1'"
Write-Host "  按需补充依赖组：" -ForegroundColor Yellow
Write-Host "      .\scripts\setup-env.ps1 -All"
