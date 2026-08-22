using System.IO;



namespace DdeSetupWizard;



public enum DeploymentMode

{

    Local,

    Cloud,

}



public enum DockerStatus

{

    Unknown,

    Missing,

    InstalledNotRunning,

    Healthy,

    Skipped,

}



/// <summary>Claude Code primary auth vs optional API-key backup.</summary>

public enum ClaudeAuthMode

{

    Subscription,

    ApiKeyBackup,

}



/// <summary>

/// Honest Claude Code session state — never invent a completed OAuth session.

/// Verified via <c>claude auth status</c> or a stored <c>setup-token</c> in Credential Manager.

/// </summary>

public enum ClaudeSessionStatus

{

    None,

    PendingCliLogin,

    VerifiedCliLogin,

    StoredSetupToken,

    Blocked,

}



public sealed class SetupContext

{

    public string InstallRoot { get; set; } = @"C:\Program Files\DDE";

    public string DataRoot { get; set; } = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData) + @"\DDE";

    public string Version { get; set; } = "0.1.0";

    public string CoreImageTag { get; set; } = "dde-core:local";

    public string CoreImageTar { get; set; } = @"C:\Program Files\DDE\payload\dde-core.tar";



    public DeploymentMode Mode { get; set; } = DeploymentMode.Local;

    public string CloudApiBaseUrl { get; set; } = string.Empty;



    public DockerStatus DockerStatus { get; set; } = DockerStatus.Unknown;

    public bool SkipWorkers { get; set; }



    public string AdminUsername { get; set; } = "admin";

    public string AdminPassword { get; set; } = string.Empty;



    /// <summary>Primary: Claude subscription. Backup: Anthropic API key only when selected.</summary>

    public ClaudeAuthMode ClaudeAuthMode { get; set; } = ClaudeAuthMode.Subscription;

    public string ClaudeEmail { get; set; } = string.Empty;

    public ClaudeSessionStatus ClaudeSessionStatus { get; set; } = ClaudeSessionStatus.None;

    /// <summary>wincred:DDE/ClaudeCodeOAuthToken when a setup-token was stored — never the raw secret.</summary>

    public string ClaudeOAuthTokenRef { get; set; } = string.Empty;

    public string ClaudeAuthSource { get; set; } = string.Empty;

    public string ClaudeAuthMethod { get; set; } = string.Empty;

    public string ClaudeSubscriptionType { get; set; } = string.Empty;

    public string ClaudeOrgName { get; set; } = string.Empty;

    public string ClaudeBlockedReason { get; set; } = string.Empty;



    public string AnthropicApiKey { get; set; } = string.Empty;

    public string OpenAiApiKey { get; set; } = string.Empty;

    public string DeepSeekApiKey { get; set; } = string.Empty;

    public string CursorApiKey { get; set; } = string.Empty;

    public string GitHubToken { get; set; } = string.Empty;



    public string? LastError { get; set; }

    public string? HealthCheckUrl { get; set; }



    public static SetupContext LoadDefaults()

    {

        var ctx = new SetupContext();

        var installMeta = Path.Combine(ctx.DataRoot, "install.json");

        if (File.Exists(installMeta))

        {

            try

            {

                var json = File.ReadAllText(installMeta);

                using var doc = System.Text.Json.JsonDocument.Parse(json);

                if (doc.RootElement.TryGetProperty("install_root", out var root))

                {

                    ctx.InstallRoot = root.GetString() ?? ctx.InstallRoot;

                }

                if (doc.RootElement.TryGetProperty("data_root", out var data))

                {

                    ctx.DataRoot = data.GetString() ?? ctx.DataRoot;

                }

                if (doc.RootElement.TryGetProperty("version", out var ver))

                {

                    ctx.Version = ver.GetString() ?? ctx.Version;

                }

                if (doc.RootElement.TryGetProperty("core_image_tag", out var tag))

                {

                    ctx.CoreImageTag = tag.GetString() ?? $"dde-core:{ctx.Version}";

                }

                else

                {

                    ctx.CoreImageTag = $"dde-core:{ctx.Version}";

                }

            }

            catch

            {

                // Non-fatal during wizard startup.

            }

        }



        ctx.CoreImageTar = Path.Combine(ctx.InstallRoot, "payload", "dde-core.tar");

        return ctx;

    }

}


