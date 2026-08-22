using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace DdeSetupWizard.Services;

/// <summary>
/// Official Claude Code auth paths only:
/// <c>claude auth login</c>, <c>claude auth status</c>, <c>claude setup-token</c>.
/// Docs: https://code.claude.com/docs/en/authentication
/// </summary>
public static class ClaudeCodeAuthService
{
    public const string DocsAuthenticationUrl = "https://code.claude.com/docs/en/authentication";
    public const string DocsCliReferenceUrl = "https://code.claude.com/docs/en/cli-reference";
    public const string WinCredOAuthTarget = "DDE/ClaudeCodeOAuthToken";
    public const string OAuthTokenRef = "wincred:DDE/ClaudeCodeOAuthToken";

    private static readonly Regex OAuthTokenPattern = new(
        @"sk-ant-oat01-[A-Za-z0-9\-_]+",
        RegexOptions.Compiled);

    private static readonly Regex ApiKeyPattern = new(
        @"sk-ant-api03-[A-Za-z0-9\-_]+",
        RegexOptions.Compiled);

    public sealed record AuthStatusResult(
        bool CliFound,
        bool LoggedIn,
        string? Email,
        string? AuthMethod,
        string? SubscriptionType,
        string? OrgName,
        string? RawJson,
        string? Error,
        string? BlockedReason);

    public sealed record TokenCaptureResult(
        bool Ok,
        string? Token,
        string? Error);

    public static string? FindClaudeExecutable()
    {
        // Prefer a refreshed PATH so post-install User PATH edits are visible.
        ClaudeCodeCliService.RefreshProcessPathFromRegistry();

        var pathEnv = Environment.GetEnvironmentVariable("PATH")
            ?? Environment.GetEnvironmentVariable("Path")
            ?? "";
        foreach (var dir in pathEnv.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            try
            {
                var candidate = Path.Combine(dir.Trim('"'), "claude.exe");
                if (File.Exists(candidate))
                {
                    return candidate;
                }

                candidate = Path.Combine(dir.Trim('"'), "claude.cmd");
                if (File.Exists(candidate))
                {
                    return candidate;
                }

                candidate = Path.Combine(dir.Trim('"'), "claude");
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
            catch
            {
                // skip bad PATH entries
            }
        }

        // Native installer layout (often not yet on PATH — see Ensure-ClaudeCli.ps1).
        var native = ClaudeCodeCliService.NativeBinPath();
        if (File.Exists(native))
        {
            ClaudeCodeCliService.EnsureNativeBinOnUserPath();
            return native;
        }

        var localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var npmClaude = Path.Combine(localApp, "npm", "claude.cmd");
        if (File.Exists(npmClaude))
        {
            return npmClaude;
        }

        var roamingNpm = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "npm",
            "claude.exe");
        if (File.Exists(roamingNpm))
        {
            return roamingNpm;
        }

        return null;
    }

    public static bool IsValidOAuthToken(string? token)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            return false;
        }

        var t = token.Trim();
        return OAuthTokenPattern.IsMatch(t) && !ApiKeyPattern.IsMatch(t);
    }

    public static string? ExtractOAuthToken(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var m = OAuthTokenPattern.Match(text);
        return m.Success ? m.Value : null;
    }

    /// <summary>
    /// Opens an interactive console running <c>claude auth login</c> (browser OAuth).
    /// Anthropic does not publish a third-party OAuth client for Claude Code subscriptions.
    /// </summary>
    public static (bool Ok, string? Error, string? BlockedReason) StartAuthLogin(string? emailPrefill = null)
    {
        var claude = FindClaudeExecutable();
        if (claude is null)
        {
            return (
                false,
                "Claude Code CLI not found on PATH.",
                "Install Claude Code, then re-run Sign in. Docs: " + DocsAuthenticationUrl);
        }

        var args = new StringBuilder("auth login");
        if (!string.IsNullOrWhiteSpace(emailPrefill))
        {
            args.Append(" --email ");
            args.Append(QuoteArg(emailPrefill.Trim()));
        }

        try
        {
            // New console so the user can complete browser OAuth and paste a login code if needed.
            Process.Start(new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = $"/c start \"Claude Code login\" \"{claude}\" {args}",
                UseShellExecute = false,
                CreateNoWindow = true,
            });
            return (true, null, null);
        }
        catch (Exception ex)
        {
            return (false, ex.Message, null);
        }
    }

    /// <summary>
    /// Starts <c>claude setup-token</c> in a new console. User copies the printed token
    /// and pastes it back into the wizard (token is not scraped from Claude's private store).
    /// </summary>
    public static (bool Ok, string? Error, string? BlockedReason) StartSetupToken()
    {
        var claude = FindClaudeExecutable();
        if (claude is null)
        {
            return (
                false,
                "Claude Code CLI not found on PATH.",
                "Install Claude Code first. Docs: " + DocsAuthenticationUrl);
        }

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = $"/c start \"Claude Code setup-token\" \"{claude}\" setup-token",
                UseShellExecute = false,
                CreateNoWindow = true,
            });
            return (true, null, null);
        }
        catch (Exception ex)
        {
            return (false, ex.Message, null);
        }
    }

    public static AuthStatusResult QueryAuthStatus()
    {
        var claude = FindClaudeExecutable();
        if (claude is null)
        {
            return new AuthStatusResult(
                CliFound: false,
                LoggedIn: false,
                Email: null,
                AuthMethod: null,
                SubscriptionType: null,
                OrgName: null,
                RawJson: null,
                Error: "Claude Code CLI not found on PATH.",
                BlockedReason:
                "Cannot verify subscription login without the official CLI. Install Claude Code and ensure `claude` is on PATH. Docs: "
                + DocsAuthenticationUrl);
        }

        try
        {
            var (exitCode, stdout, stderr) = RunCapture(claude, "auth status", TimeSpan.FromSeconds(45));
            var combined = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
            var parsed = TryParseStatusJson(combined);
            if (parsed is not null)
            {
                return parsed with { CliFound = true, RawJson = combined.Trim() };
            }

            // Older CLIs: exit 0 = logged in, no JSON.
            if (exitCode == 0)
            {
                return new AuthStatusResult(
                    true,
                    true,
                    null,
                    null,
                    null,
                    null,
                    combined.Trim(),
                    null,
                    null);
            }

            return new AuthStatusResult(
                true,
                false,
                null,
                null,
                null,
                null,
                combined.Trim(),
                string.IsNullOrWhiteSpace(stderr) ? "Not logged in." : stderr.Trim(),
                null);
        }
        catch (Exception ex)
        {
            return new AuthStatusResult(
                true,
                false,
                null,
                null,
                null,
                null,
                null,
                ex.Message,
                null);
        }
    }

    public static bool StoreOAuthToken(string token, string? accountHint)
    {
        if (!IsValidOAuthToken(token))
        {
            return false;
        }

        var user = string.IsNullOrWhiteSpace(accountHint) ? "claude-oauth" : accountHint.Trim();
        try
        {
            RunProcess("cmdkey", $"/generic:{WinCredOAuthTarget} /user:{QuoteArg(user)} /pass:{QuoteArg(token.Trim())}");
            return true;
        }
        catch
        {
            return false;
        }
    }

    public static void DeleteOAuthToken()
    {
        try
        {
            RunProcess("cmdkey", $"/delete:{WinCredOAuthTarget}");
        }
        catch
        {
            // best-effort
        }
    }

    private static AuthStatusResult? TryParseStatusJson(string text)
    {
        var json = ExtractJsonObject(text);
        if (json is null)
        {
            return null;
        }

        try
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            var loggedIn = root.TryGetProperty("loggedIn", out var li) && li.ValueKind == JsonValueKind.True;
            string? email = GetStringOrNull(root, "email");
            string? authMethod = GetStringOrNull(root, "authMethod");
            string? subscription = GetStringOrNull(root, "subscriptionType");
            string? orgName = GetStringOrNull(root, "orgName");
            return new AuthStatusResult(
                CliFound: true,
                LoggedIn: loggedIn,
                Email: email,
                AuthMethod: authMethod,
                SubscriptionType: subscription,
                OrgName: orgName,
                RawJson: json,
                Error: loggedIn ? null : "Not logged in.",
                BlockedReason: null);
        }
        catch
        {
            return null;
        }
    }

    private static string? ExtractJsonObject(string text)
    {
        var start = text.IndexOf('{');
        var end = text.LastIndexOf('}');
        if (start < 0 || end <= start)
        {
            return null;
        }

        return text[start..(end + 1)];
    }

    private static string? GetStringOrNull(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out var el) || el.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        return el.ValueKind == JsonValueKind.String ? el.GetString() : el.ToString();
    }

    private static (int ExitCode, string Stdout, string Stderr) RunCapture(
        string fileName,
        string arguments,
        TimeSpan timeout)
    {
        using var proc = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = fileName,
                Arguments = arguments,
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

            throw new TimeoutException($"Timed out running: {fileName} {arguments}");
        }

        return (proc.ExitCode, stdout.ToString(), stderr.ToString());
    }

    private static void RunProcess(string file, string args)
    {
        using var proc = Process.Start(new ProcessStartInfo
        {
            FileName = file,
            Arguments = args,
            UseShellExecute = false,
            CreateNoWindow = true,
        }) ?? throw new InvalidOperationException($"Failed to start {file}");
        proc.WaitForExit();
        if (proc.ExitCode != 0)
        {
            throw new InvalidOperationException($"{file} exited with {proc.ExitCode}");
        }
    }

    private static string QuoteArg(string value)
    {
        if (value.Contains('"') || value.Contains(' ') || value.Contains('\t'))
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        return value;
    }
}
