using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using DdeSetupWizard.Services;

namespace DdeSetupWizard.Pages;

public sealed class ProgressPage : WizardPageBase
{
    private readonly SetupContext _context;
    private readonly Action _next;
    private readonly TextBlock _log;
    private readonly Button _nextButton;
    private readonly InstallOrchestrator _orchestrator = new();
    private bool _installStarted;

    public ProgressPage(SetupContext context, Action next, Action back)
        : base("Installing DDE", "Loading Core image, starting services, applying migrations, and verifying health.")
    {
        _context = context;
        _next = next;
        _ = back;
        _log = new TextBlock
        {
            TextWrapping = TextWrapping.Wrap,
            FontFamily = new FontFamily("Consolas"),
            FontSize = 12,
        };
        _nextButton = new Button { Content = "Finish", IsDefault = true, IsEnabled = false };
        _nextButton.Click += (_, _) => _next();
        Loaded += async (_, _) => await RunInstallAsync();
    }

    protected override UIElement BuildContent()
    {
        return new Border
        {
            Background = Brushes.White,
            BorderBrush = Brushes.LightGray,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Padding = new Thickness(12),
            Child = _log,
        };
    }

    protected override UIElement BuildFooter()
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        row.Children.Add(_nextButton);
        return row;
    }

    private async Task RunInstallAsync()
    {
        if (_installStarted)
        {
            return;
        }
        _installStarted = true;

        try
        {
            var progress = new Progress<string>(line => _log.Text += line + Environment.NewLine);
            await _orchestrator.RunAsync(_context, progress, CancellationToken.None);
            _log.Text += Environment.NewLine + "Installation succeeded.";
            _nextButton.IsEnabled = true;
        }
        catch (Exception ex)
        {
            _context.LastError = ex.Message;
            _log.Text += Environment.NewLine + "ERROR: " + ex.Message;
            MessageBox.Show(ex.Message, "Installation failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }
}
