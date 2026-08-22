using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;

namespace DdeSetupWizard.Pages;

public sealed class CompletePage : WizardPageBase
{
    private readonly SetupContext _context;

    public CompletePage(SetupContext context)
        : base("Setup complete", "DDE is configured on this machine.")
    {
        _context = context;
    }

    protected override UIElement BuildContent()
    {
        var panel = new StackPanel();
        if (!string.IsNullOrWhiteSpace(_context.LastError))
        {
            panel.Children.Add(new TextBlock
            {
                Text = "Setup finished with errors:\n" + _context.LastError,
                TextWrapping = TextWrapping.Wrap,
                Foreground = System.Windows.Media.Brushes.DarkRed,
            });
            return panel;
        }

        panel.Children.Add(new TextBlock
        {
            TextWrapping = TextWrapping.Wrap,
            Text = _context.Mode == DeploymentMode.Cloud
                ? $"Cloud client configured.\nRemote API: {_context.CloudApiBaseUrl}"
                : "Local appliance is running.\nAPI: http://127.0.0.1:8000",
            FontSize = 14,
            LineHeight = 22,
        });

        if (!string.IsNullOrWhiteSpace(_context.HealthCheckUrl))
        {
            var open = new Button { Content = "Open health check", Margin = new Thickness(0, 16, 0, 0) };
            open.Click += (_, _) =>
            {
                Process.Start(new ProcessStartInfo(_context.HealthCheckUrl!) { UseShellExecute = true });
            };
            panel.Children.Add(open);
        }

        return panel;
    }

    protected override UIElement BuildFooter()
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var close = new Button { Content = "Close", IsDefault = true };
        close.Click += (_, _) => Application.Current.Shutdown();
        row.Children.Add(close);
        return row;
    }
}
