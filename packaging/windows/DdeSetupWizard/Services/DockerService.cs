using System.Diagnostics;
using System.IO;
using System.Net.Http;

namespace DdeSetupWizard.Services;

public static class DockerService
{
    private const string DesktopInstallerUrl =
        "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe";

    public static DockerStatus Detect()
    {
        if (!HasDockerCli())
        {
            return IsDockerDesktopInstalled() ? DockerStatus.InstalledNotRunning : DockerStatus.Missing;
        }

        return IsEngineHealthy() ? DockerStatus.Healthy : DockerStatus.InstalledNotRunning;
    }

    public static async Task<DockerStatus> WaitForHealthyAsync(TimeSpan timeout, CancellationToken ct)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            ct.ThrowIfCancellationRequested();
            var status = Detect();
            if (status == DockerStatus.Healthy)
            {
                return status;
            }
            await Task.Delay(TimeSpan.FromSeconds(3), ct);
        }
        return Detect();
    }

    public static void StartDockerDesktop()
    {
        var desktop = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            "Docker", "Docker", "Docker Desktop.exe");
        if (File.Exists(desktop))
        {
            Process.Start(new ProcessStartInfo(desktop) { UseShellExecute = true });
        }
    }

    public static async Task<string> DownloadInstallerAsync(string targetDir, IProgress<string>? progress, CancellationToken ct)
    {
        Directory.CreateDirectory(targetDir);
        var target = Path.Combine(targetDir, "DockerDesktopInstaller.exe");
        progress?.Report("Downloading Docker Desktop...");
        using var client = new HttpClient();
        await using var stream = await client.GetStreamAsync(DesktopInstallerUrl, ct);
        await using var file = File.Create(target);
        await stream.CopyToAsync(file, ct);
        return target;
    }

    public static void LaunchInstaller(string installerPath)
    {
        Process.Start(new ProcessStartInfo(installerPath) { UseShellExecute = true, Verb = "runas" });
    }

    public static void OpenInstallDocs()
    {
        Process.Start(new ProcessStartInfo(
            "https://docs.docker.com/desktop/setup/install/windows-install/")
        {
            UseShellExecute = true,
        });
    }

    public static string Describe(DockerStatus status) => status switch
    {
        DockerStatus.Healthy => "Docker is running and ready for DDE workers.",
        DockerStatus.InstalledNotRunning => "Docker Desktop is installed but the engine is not running.",
        DockerStatus.Missing => "Docker Desktop was not detected. Worker execution requires Docker.",
        DockerStatus.Skipped => "Continuing without Docker. Core-only mode; workers remain blocked.",
        _ => "Checking Docker...",
    };

    private static bool HasDockerCli()
    {
        try
        {
            return Run("docker", "--version").ExitCode == 0;
        }
        catch
        {
            return false;
        }
    }

    private static bool IsEngineHealthy()
    {
        try
        {
            return Run("docker", "info --format \"{{.ServerVersion}}\"").ExitCode == 0;
        }
        catch
        {
            return false;
        }
    }

    private static bool IsDockerDesktopInstalled()
    {
        var desktop = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            "Docker", "Docker", "Docker Desktop.exe");
        if (File.Exists(desktop))
        {
            return true;
        }

        return Directory.Exists(Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
            "Docker"));
    }

    private static (int ExitCode, string Output) Run(string file, string args)
    {
        using var proc = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = file,
                Arguments = args,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            },
        };
        proc.Start();
        var output = proc.StandardOutput.ReadToEnd() + proc.StandardError.ReadToEnd();
        proc.WaitForExit();
        return (proc.ExitCode, output.Trim());
    }
}
