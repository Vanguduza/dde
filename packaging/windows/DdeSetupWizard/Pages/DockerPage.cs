using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using DdeSetupWizard.Services;

namespace DdeSetupWizard.Pages;

public sealed class DockerPage : WizardPageBase
{
    private readonly SetupContext _context;
    private readonly Action _next;
    private readonly Action _back;
    private readonly TextBlock _statusText;
    private readonly TextBlock _detailText;

    public DockerPage(SetupContext context, Action next, Action back)
        : base("Docker Desktop", "Worker execution requires Docker Desktop with the WSL2 backend.")
    {
        _context = context;
        _next = next;
        _back = back;
        _statusText = new TextBlock { FontWeight = FontWeights.SemiBold, FontSize = 15 };
        _detailText = new TextBlock { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 0) };
        RefreshStatus();
    }

    protected override UIElement BuildContent()
    {
        var panel = new StackPanel();

        var statusBox = new Border
        {
            Background = Brushes.White,
            BorderBrush = Brushes.LightGray,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Padding = new Thickness(14),
            Margin = new Thickness(0, 0, 0, 16),
        };
        var statusPanel = new StackPanel();
        statusPanel.Children.Add(_statusText);
        statusPanel.Children.Add(_detailText);
        statusBox.Child = statusPanel;
        panel.Children.Add(statusBox);

        var download = new Button { Content = "Download & install Docker Desktop" };
        download.Click += async (_, _) => await DownloadDockerAsync();
        panel.Children.Add(download);

        var start = new Button { Content = "Start Docker Desktop", Margin = new Thickness(0, 8, 0, 0) };
        start.Click += async (_, _) =>
        {
            DockerService.StartDockerDesktop();
            await WaitAndRefreshAsync();
        };
        panel.Children.Add(start);

        var recheck = new Button { Content = "Re-check Docker", Margin = new Thickness(0, 8, 0, 0) };
        recheck.Click += async (_, _) => await WaitAndRefreshAsync();
        panel.Children.Add(recheck);

        var docs = new Button { Content = "Open Docker install docs", Margin = new Thickness(0, 8, 0, 0) };
        docs.Click += (_, _) => DockerService.OpenInstallDocs();
        panel.Children.Add(docs);

        var skip = new CheckBox
        {
            Content = "Continue without Docker (Core-only; workers blocked)",
            Margin = new Thickness(0, 16, 0, 0),
        };
        skip.Checked += (_, _) =>
        {
            _context.SkipWorkers = true;
            _context.DockerStatus = DockerStatus.Skipped;
            RefreshStatus();
        };
        skip.Unchecked += (_, _) =>
        {
            _context.SkipWorkers = false;
            RefreshStatus();
        };
        panel.Children.Add(skip);

        return panel;
    }

    protected override UIElement BuildFooter()
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var back = new Button { Content = "Back" };
        back.Click += (_, _) => _back();
        var next = new Button { Content = "Next", IsDefault = true };
        next.Click += (_, _) =>
        {
            if (!_context.SkipWorkers && _context.DockerStatus != DockerStatus.Healthy)
            {
                MessageBox.Show(
                    "Docker is not healthy yet. Install/start Docker Desktop, re-check, or enable Core-only mode.",
                    "Docker required",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return;
            }
            _next();
        };
        row.Children.Add(back);
        row.Children.Add(next);
        return row;
    }

    private async Task DownloadDockerAsync()
    {
        try
        {
            var dir = Path.Combine(Path.GetTempPath(), "DDE-Docker");
            var installer = await DockerService.DownloadInstallerAsync(
                dir,
                new Progress<string>(msg => _detailText.Text = msg),
                CancellationToken.None);
            DockerService.LaunchInstaller(installer);
            _detailText.Text = "Complete the Docker Desktop installer, then click Re-check Docker.";
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "Download failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private async Task WaitAndRefreshAsync()
    {
        _detailText.Text = "Waiting for Docker engine...";
        _context.DockerStatus = await DockerService.WaitForHealthyAsync(TimeSpan.FromMinutes(3), CancellationToken.None);
        RefreshStatus();
    }

    private void RefreshStatus()
    {
        if (_context.SkipWorkers)
        {
            _context.DockerStatus = DockerStatus.Skipped;
        }
        else
        {
            _context.DockerStatus = DockerService.Detect();
        }
        _statusText.Text = _context.DockerStatus.ToString();
        _detailText.Text = DockerService.Describe(_context.DockerStatus);
    }
}
