using System.Windows;
using System.Windows.Controls;

namespace DdeSetupWizard.Pages;

public sealed class ModePage : WizardPageBase
{
    private readonly SetupContext _context;
    private readonly Action _next;
    private readonly Action _back;
    private readonly RadioButton _local;
    private readonly RadioButton _cloud;
    private readonly TextBox _cloudUrl;

    public ModePage(SetupContext context, Action next, Action back)
        : base("Deployment mode", "Run everything locally on this PC, or use this PC as a client to a remote DDE Core.")
    {
        _context = context;
        _next = next;
        _back = back;
        _local = new RadioButton { Content = "Local appliance (Core + DB + Redis + workers on this PC)", IsChecked = true };
        _cloud = new RadioButton { Content = "Cloud client (connect to remote DDE Core)", Margin = new Thickness(0, 8, 0, 0) };
        _cloudUrl = new TextBox { Margin = new Thickness(24, 8, 0, 0), IsEnabled = false };
    }

    protected override UIElement BuildContent()
    {
        var panel = new StackPanel();
        panel.Children.Add(_local);
        panel.Children.Add(_cloud);
        panel.Children.Add(new TextBlock
        {
            Text = "Remote API base URL",
            Margin = new Thickness(24, 12, 0, 4),
        });
        panel.Children.Add(_cloudUrl);

        _cloud.Checked += (_, _) =>
        {
            _cloudUrl.IsEnabled = true;
            _context.Mode = DeploymentMode.Cloud;
        };
        _local.Checked += (_, _) =>
        {
            _cloudUrl.IsEnabled = false;
            _context.Mode = DeploymentMode.Local;
        };

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
            _context.Mode = _cloud.IsChecked == true ? DeploymentMode.Cloud : DeploymentMode.Local;
            _context.CloudApiBaseUrl = _cloudUrl.Text.Trim();
            if (_context.Mode == DeploymentMode.Cloud && string.IsNullOrWhiteSpace(_context.CloudApiBaseUrl))
            {
                MessageBox.Show("Enter the remote DDE API base URL.", "Cloud mode", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            if (_context.Mode == DeploymentMode.Local && _context.DockerStatus != DockerStatus.Healthy)
            {
                MessageBox.Show(
                    "Local appliance requires healthy Docker Desktop. Install/start Docker or choose cloud mode.",
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
}
