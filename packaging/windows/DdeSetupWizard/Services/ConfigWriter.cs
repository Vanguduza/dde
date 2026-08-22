using System.Diagnostics;

using System.IO;

using System.Text;



namespace DdeSetupWizard.Services;



public static class ConfigWriter

{

    public static void WriteAll(SetupContext ctx)

    {

        Directory.CreateDirectory(ctx.DataRoot);

        Directory.CreateDirectory(Path.Combine(ctx.DataRoot, "artifacts"));

        Directory.CreateDirectory(Path.Combine(ctx.DataRoot, "logs"));



        WriteConfigToml(ctx);

        WriteEnvFile(ctx);

        StoreAdminCredential(ctx);

    }



    private static void WriteConfigToml(SetupContext ctx)

    {

        var example = Path.Combine(ctx.InstallRoot, "config.example.toml");

        if (!File.Exists(example))

        {

            throw new FileNotFoundException("Missing config.example.toml", example);

        }



        var text = File.ReadAllText(example);

        text = text.Replace("mode = \"local\"", $"mode = \"{ctx.Mode.ToString().ToLowerInvariant()}\"");

        if (ctx.Mode == DeploymentMode.Cloud && !string.IsNullOrWhiteSpace(ctx.CloudApiBaseUrl))

        {

            text = text.Replace("api_base_url = \"\"", $"api_base_url = \"{Escape(ctx.CloudApiBaseUrl)}\"");

        }

        text = text.Replace("admin_username = \"\"", $"admin_username = \"{Escape(ctx.AdminUsername)}\"");

        text = text.Replace("anthropic_api_key = \"\"", $"anthropic_api_key = \"{Escape(ctx.AnthropicApiKey)}\"");

        text = text.Replace("openai_api_key = \"\"", $"openai_api_key = \"{Escape(ctx.OpenAiApiKey)}\"");

        text = text.Replace("deepseek_api_key = \"\"", $"deepseek_api_key = \"{Escape(ctx.DeepSeekApiKey)}\"");

        text = text.Replace("cursor_api_key = \"\"", $"cursor_api_key = \"{Escape(ctx.CursorApiKey)}\"");

        text = text.Replace("github_token = \"\"", $"github_token = \"{Escape(ctx.GitHubToken)}\"");



        text = text.Replace(

            "auth_mode = \"subscription\"",

            $"auth_mode = \"{MapClaudeAuthMode(ctx.ClaudeAuthMode)}\"");

        text = text.Replace("email = \"\"", $"email = \"{Escape(ctx.ClaudeEmail)}\"");

        text = text.Replace(

            "session_status = \"none\"",

            $"session_status = \"{MapSessionStatus(ctx.ClaudeSessionStatus)}\"");

        text = text.Replace(

            "oauth_token_ref = \"\"",

            $"oauth_token_ref = \"{Escape(ctx.ClaudeOAuthTokenRef)}\"");

        text = text.Replace(

            "auth_source = \"\"",

            $"auth_source = \"{Escape(ctx.ClaudeAuthSource)}\"");

        text = text.Replace(

            "auth_method = \"\"",

            $"auth_method = \"{Escape(ctx.ClaudeAuthMethod)}\"");

        text = text.Replace(

            "subscription_type = \"\"",

            $"subscription_type = \"{Escape(ctx.ClaudeSubscriptionType)}\"");

        text = text.Replace(

            "org_name = \"\"",

            $"org_name = \"{Escape(ctx.ClaudeOrgName)}\"");

        text = text.Replace(

            "blocked_reason = \"\"",

            $"blocked_reason = \"{Escape(ctx.ClaudeBlockedReason)}\"");



        text = text.Replace(

            "status = \"unknown\"",

            $"status = \"{MapDockerStatus(ctx.DockerStatus)}\"");



        var target = Path.Combine(ctx.DataRoot, "config.toml");

        File.WriteAllText(target, text, Encoding.UTF8);

    }



    private static void WriteEnvFile(SetupContext ctx)

    {

        var envPath = Path.Combine(ctx.DataRoot, ".env");

        var lines = new[]

        {

            $"DDE_CORE_IMAGE={ctx.CoreImageTag}",

            $"DDE_CURSOR_API_KEY={ctx.CursorApiKey}",

            // Anthropic key only when used as Claude Code backup (or left empty).

            $"DDE_ANTHROPIC_API_KEY={ctx.AnthropicApiKey}",

            $"DDE_OPENAI_API_KEY={ctx.OpenAiApiKey}",

            $"DDE_DEEPSEEK_API_KEY={ctx.DeepSeekApiKey}",

            $"DDE_GITHUB_TOKEN={ctx.GitHubToken}",

            $"DDE_CLAUDE_CODE_AUTH_MODE={MapClaudeAuthMode(ctx.ClaudeAuthMode)}",

            $"DDE_CLAUDE_CODE_EMAIL={ctx.ClaudeEmail}",

            $"DDE_CLAUDE_CODE_SESSION_STATUS={MapSessionStatus(ctx.ClaudeSessionStatus)}",

            $"DDE_CLAUDE_CODE_OAUTH_TOKEN_REF={ctx.ClaudeOAuthTokenRef}",

            $"DDE_CLAUDE_CODE_AUTH_SOURCE={ctx.ClaudeAuthSource}",

        };

        File.WriteAllLines(envPath, lines, Encoding.UTF8);

    }



    private static void StoreAdminCredential(SetupContext ctx)

    {

        if (string.IsNullOrWhiteSpace(ctx.AdminPassword))

        {

            return;

        }



        try

        {

            RunProcess("cmdkey", $"/generic:DDE/AdminPassword /user:{ctx.AdminUsername} /pass:{ctx.AdminPassword}");

        }

        catch

        {

            // Credential Manager is best-effort.

        }

    }



    private static string MapClaudeAuthMode(ClaudeAuthMode mode) => mode switch

    {

        ClaudeAuthMode.ApiKeyBackup => "api_key_backup",

        _ => "subscription",

    };



    private static string MapSessionStatus(ClaudeSessionStatus status) => status switch

    {

        ClaudeSessionStatus.PendingCliLogin => "pending_cli_login",

        ClaudeSessionStatus.VerifiedCliLogin => "verified_cli_login",

        ClaudeSessionStatus.StoredSetupToken => "stored_setup_token",

        ClaudeSessionStatus.Blocked => "blocked",

        _ => "none",

    };



    private static string MapDockerStatus(DockerStatus status) => status switch

    {

        DockerStatus.Healthy => "healthy",

        DockerStatus.Missing => "missing",

        DockerStatus.InstalledNotRunning => "installed_not_running",

        DockerStatus.Skipped => "skipped",

        _ => "unknown",

    };



    private static string Escape(string value) => value.Replace("\\", "\\\\").Replace("\"", "\\\"");



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

}


