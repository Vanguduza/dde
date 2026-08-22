using System.Diagnostics;
using System.IO;
using System.Net.Http;

namespace DdeSetupWizard.Services;

public sealed class InstallOrchestrator
{
    public async Task RunAsync(SetupContext ctx, IProgress<string> progress, CancellationToken ct)
    {
        progress.Report("Writing configuration...");
        ConfigWriter.WriteAll(ctx);

        if (ctx.Mode == DeploymentMode.Cloud)
        {
            progress.Report("Cloud mode configured. Local Core stack will not start.");
            ctx.HealthCheckUrl = string.IsNullOrWhiteSpace(ctx.CloudApiBaseUrl)
                ? null
                : ctx.CloudApiBaseUrl.TrimEnd('/') + "/healthz";
            return;
        }

        if (ctx.DockerStatus != DockerStatus.Healthy)
        {
            throw new InvalidOperationException(
                "Docker is not healthy. Install/start Docker Desktop or choose cloud mode.");
        }

        progress.Report("Loading bundled DDE Core image...");
        await LoadCoreImageAsync(ctx, progress, ct);

        progress.Report("Pulling Postgres and Redis images...");
        await ComposeAsync(ctx, progress, ct, "pull", "postgres", "redis");

        progress.Report("Starting database services...");
        await ComposeAsync(ctx, progress, ct, "up", "-d", "postgres", "redis");

        progress.Report("Applying database migrations...");
        await ComposeAsync(ctx, progress, ct, "--profile", "bootstrap", "run", "--rm", "migrate");

        progress.Report("Starting DDE Core...");
        await ComposeAsync(ctx, progress, ct, "up", "-d", "core");

        progress.Report("Waiting for health check...");
        ctx.HealthCheckUrl = "http://127.0.0.1:8000/healthz";
        await WaitForHealthAsync(ctx.HealthCheckUrl, ct);
        progress.Report("DDE Core is healthy.");
    }

    private static async Task LoadCoreImageAsync(SetupContext ctx, IProgress<string> progress, CancellationToken ct)
    {
        if (!File.Exists(ctx.CoreImageTar))
        {
            throw new FileNotFoundException("Bundled core image not found", ctx.CoreImageTar);
        }

        await RunDockerAsync(progress, ct, "load", "-i", ctx.CoreImageTar);
    }

    private static async Task ComposeAsync(
        SetupContext ctx,
        IProgress<string> progress,
        CancellationToken ct,
        params string[] args)
    {
        var compose = Path.Combine(ctx.InstallRoot, "docker-compose.appliance.yml");
        var envFile = Path.Combine(ctx.DataRoot, ".env");
        var composeArgs = new List<string> { "compose", "-f", compose, "--env-file", envFile };
        composeArgs.AddRange(args);
        await RunDockerAsync(progress, ct, composeArgs.ToArray());
    }

    private static async Task WaitForHealthAsync(string url, CancellationToken ct)
    {
        using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(5) };
        var deadline = DateTime.UtcNow.AddMinutes(2);
        while (DateTime.UtcNow < deadline)
        {
            ct.ThrowIfCancellationRequested();
            try
            {
                using var resp = await client.GetAsync(url, ct);
                if (resp.IsSuccessStatusCode)
                {
                    return;
                }
            }
            catch
            {
                // Retry until deadline.
            }
            await Task.Delay(TimeSpan.FromSeconds(2), ct);
        }
        throw new TimeoutException($"Timed out waiting for {url}");
    }

    private static Task RunDockerAsync(IProgress<string> progress, CancellationToken ct, params string[] args)
    {
        return Task.Run(() =>
        {
            ct.ThrowIfCancellationRequested();
            progress.Report($"docker {string.Join(' ', args)}");
            using var proc = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "docker",
                    Arguments = string.Join(' ', args.Select(Quote)),
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                },
            };
            proc.Start();
            var output = proc.StandardOutput.ReadToEnd();
            var error = proc.StandardError.ReadToEnd();
            proc.WaitForExit();
            if (proc.ExitCode != 0)
            {
                throw new InvalidOperationException(
                    $"docker {args[0]} failed ({proc.ExitCode}): {error}\n{output}");
            }
        }, ct);
    }

    private static string Quote(string arg) =>
        arg.Contains(' ') || arg.Contains('"') ? $"\"{arg.Replace("\"", "\\\"")}\"" : arg;
}
