using System.Diagnostics;
using System.IO;
using System.Text;

namespace DdeSetupWizard.Services;

/// <summary>
/// Detect / install official Claude Code CLI so <c>claude</c> is on PATH.
/// Install method: Anthropic native Windows installer (<c>https://claude.ai/install.ps1</c>),
/// with optional winget fallback via <c>Ensure-ClaudeCli.ps1</c>.
/// Docs: https://code.claude.com/docs/en/installation
/// </summary>
public static class ClaudeCodeCliService
{
    public const string DocsInstallUrl = "https://code.claude.com/docs/en/installation";
    public const string NativeInstallUrl = "https://claude.ai/install.ps1";

    public enum CliStatus
    {
        Unknown,
        Missing,
        Present,
    }

    public static string NativeBinPath() =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            ".local",
            "bin",
            "claude.exe");

    public static string NativeBinDir() =>
        Path.GetDirectoryName(NativeBinPath())!;

    /// <summary>
    /// Refresh process PATH from Machine + User registry (post-install).
    /// </summary>
    public static void RefreshProcessPathFromRegistry()
    {
        var machine = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.Machine) ?? "";
        var user = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.User) ?? "";
        var combined = string.Join(";", new[] { machine, user }.Where(s => !string.IsNullOrWhiteSpace(s)));
        Environment.SetEnvironmentVariable("Path", combined, EnvironmentVariableTarget.Process);
    }

    /// <summary>
    /// Ensure %USERPROFILE%\.local\bin is on User PATH (native installer often skips this).
    /// </summary>
    public static void EnsureNativeBinOnUserPath()
    {
        var binDir = NativeBinDir();
        if (!Directory.Exists(binDir))
        {
            return;
        }

        var userPath = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.User) ?? "";
        var entries = userPath.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (!entries.Any(e => string.Equals(
                e.TrimEnd('\\'),
                binDir.TrimEnd('\\'),
                StringComparison.OrdinalIgnoreCase)))
        {
            var next = string.IsNullOrWhiteSpace(userPath) ? binDir : userPath + ";" + binDir;
            Environment.SetEnvironmentVariable("Path", next, EnvironmentVariableTarget.User);
        }

        RefreshProcessPathFromRegistry();
        var processPath = Environment.GetEnvironmentVariable("Path", EnvironmentVariableTarget.Process) ?? "";
        if (!processPath.Split(';', StringSplitOptions.RemoveEmptyEntries)
                .Any(e => string.Equals(e.TrimEnd('\\'), binDir.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)))
        {
            Environment.SetEnvironmentVariable(
                "Path",
                binDir + ";" + processPath,
                EnvironmentVariableTarget.Process);
        }
    }

    public static CliStatus Detect()
    {
        RefreshProcessPathFromRegistry();
        if (File.Exists(NativeBinPath()))
        {
            EnsureNativeBinOnUserPath();
        }

        return ClaudeCodeAuthService.FindClaudeExecutable() is not null
            ? CliStatus.Present
            : CliStatus.Missing;
    }

    public static string Describe(CliStatus status) => status switch
    {
        CliStatus.Present =>
            "Claude Code CLI (`claude`) is on PATH. Sign-in is separate — use Sign in / Verify.",
        CliStatus.Missing =>
            "Claude Code CLI not found. Install it to use subscription auth (`claude auth login`).",
        _ => "Checking Claude Code CLI...",
    };

    public static string? ResolveEnsureScript(string installRoot)
    {
        var candidate = Path.Combine(installRoot, "scripts", "Ensure-ClaudeCli.ps1");
        if (File.Exists(candidate))
        {
            return candidate;
        }

        // Dev / running from publish folder next to repo packaging.
        var beside = Path.Combine(
            AppContext.BaseDirectory,
            "..", "..", "..", "..", "scripts", "Ensure-ClaudeCli.ps1");
        beside = Path.GetFullPath(beside);
        return File.Exists(beside) ? beside : null;
    }

    /// <summary>
    /// Run Ensure-ClaudeCli.ps1 -NonInteractive (user already consented in UI).
    /// </summary>
    public static async Task<(bool Ok, string Message, CliStatus Status)> EnsureInstalledAsync(
        string installRoot,
        IProgress<string>? progress,
        CancellationToken ct)
    {
        var script = ResolveEnsureScript(installRoot);
        if (script is null)
        {
            return (
                false,
                "Ensure-ClaudeCli.ps1 not found under install scripts. Reinstall DDE or run the official installer manually: "
                + DocsInstallUrl,
                Detect());
        }

        progress?.Report("Installing Claude Code CLI (official native installer)...");
        var (exitCode, stdout, stderr) = await RunPowerShellFileAsync(
            script,
            "-NonInteractive -Method Auto",
            TimeSpan.FromMinutes(10),
            ct);

        RefreshProcessPathFromRegistry();
        if (File.Exists(NativeBinPath()))
        {
            EnsureNativeBinOnUserPath();
        }

        var status = Detect();
        var detail = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
        if (exitCode == 0 && status == CliStatus.Present)
        {
            return (true, TrimMessage(detail) ?? "Claude Code CLI is on PATH.", status);
        }

        return (
            false,
            TrimMessage(detail)
            ?? $"Ensure-ClaudeCli exited {exitCode}. Install manually: {DocsInstallUrl}",
            status);
    }

    public static void OpenInstallDocs()
    {
        Process.Start(new ProcessStartInfo(DocsInstallUrl) { UseShellExecute = true });
    }

    private static string? TrimMessage(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var lines = text.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (lines.Length <= 6)
        {
            return string.Join(Environment.NewLine, lines);
        }

        return string.Join(Environment.NewLine, lines.TakeLast(6));
    }

    private static Task<(int ExitCode, string Stdout, string Stderr)> RunPowerShellFileAsync(
        string scriptPath,
        string extraArgs,
        TimeSpan timeout,
        CancellationToken ct)
    {
        return Task.Run(() =>
        {
            using var proc = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments =
                        $"-NoProfile -ExecutionPolicy Bypass -File \"{scriptPath}\" {extraArgs}",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    StandardOutputEncoding = Encoding.UTF8,
                    StandardErrorEncoding = Encoding.UTF8,
                },
            };
            var stdout = new StringBuilder();
            var stderr = new StringBuilder();
            proc.OutputDataReceived += (_, e) =>
            {
                if (e.Data is not null)
                {
                    stdout.AppendLine(e.Data);
                }
            };
            proc.ErrorDataReceived += (_, e) =>
            {
                if (e.Data is not null)
                {
                    stderr.AppendLine(e.Data);
                }
            };
            proc.Start();
            proc.BeginOutputReadLine();
            proc.BeginErrorReadLine();
            if (!proc.WaitForExit((int)timeout.TotalMilliseconds))
            {
                try
                {
                    proc.Kill(entireProcessTree: true);
                }
                catch
                {
                    // ignore
                }

                throw new TimeoutException($"Timed out running {scriptPath}");
            }

            ct.ThrowIfCancellationRequested();
            return (proc.ExitCode, stdout.ToString(), stderr.ToString());
        }, ct);
    }
}
