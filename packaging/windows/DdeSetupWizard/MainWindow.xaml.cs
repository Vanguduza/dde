using System.Windows;
using System.Windows.Controls;
using DdeSetupWizard.Pages;

namespace DdeSetupWizard;

public partial class MainWindow : Window
{
    private readonly SetupContext _context;
    private readonly WelcomePage _welcome;
    private readonly DockerPage _docker;
    private readonly ModePage _mode;
    private readonly CredentialsPage _credentials;
    private readonly ClaudeCodePage _claudeCode;
    private readonly ProgressPage _progress;
    private readonly CompletePage _complete;

    public MainWindow()
    {
        InitializeComponent();
        Background = (System.Windows.Media.Brush)FindResource("SurfaceBrush");

        _context = SetupContext.LoadDefaults();
        _welcome = new WelcomePage(_context, ShowDocker);
        _docker = new DockerPage(_context, ShowMode, ShowWelcome);
        _mode = new ModePage(_context, ShowCredentials, ShowDocker);
        _credentials = new CredentialsPage(_context, ShowClaudeCode, ShowMode);
        _claudeCode = new ClaudeCodePage(_context, ShowProgress, ShowCredentials);
        _progress = new ProgressPage(_context, ShowComplete, ShowClaudeCode);
        _complete = new CompletePage(_context);

        HostFrame.Navigate(_welcome);
    }

    private void ShowWelcome() => HostFrame.Navigate(_welcome);
    private void ShowDocker() => HostFrame.Navigate(_docker);
    private void ShowMode() => HostFrame.Navigate(_mode);
    private void ShowCredentials() => HostFrame.Navigate(_credentials);
    private void ShowClaudeCode() => HostFrame.Navigate(_claudeCode);
    private void ShowProgress() => HostFrame.Navigate(_progress);
    private void ShowComplete() => HostFrame.Navigate(_complete);
}
