using System.Windows;
using System.Windows.Controls;

namespace DdeSetupWizard.Pages;

public sealed class CredentialsPage : WizardPageBase
{
    private readonly SetupContext _context;
    private readonly Action _next;
    private readonly Action _back;
    private readonly TextBox _adminUser;
    private readonly PasswordBox _adminPass;
    private readonly PasswordBox _openai;
    private readonly PasswordBox _deepseek;
    private readonly PasswordBox _cursor;
    private readonly PasswordBox _github;

    public CredentialsPage(SetupContext context, Action next, Action back)
        : base(
            "Admin and provider keys",
            "Admin credentials are stored locally. OpenAI / DeepSeek / Cursor / GitHub keys are optional. Claude Code uses subscription login on the next step.")
    {
        _context = context;
        _next = next;
        _back = back;
        _adminUser = new TextBox { Text = "admin" };
        _adminPass = new PasswordBox();
        _openai = new PasswordBox();
        _deepseek = new PasswordBox();
        _cursor = new PasswordBox();
        _github = new PasswordBox();
    }

    protected override UIElement BuildContent()
    {
        var panel = new StackPanel();
        AddField(panel, "Admin username", _adminUser);
        AddField(panel, "Admin password", _adminPass, isPassword: true);
        panel.Children.Add(new TextBlock
        {
            Text = "Other provider keys (optional). Claude Code is not configured here — use the Claude Code step (subscription first).",
            Margin = new Thickness(0, 8, 0, 8),
            TextWrapping = TextWrapping.Wrap,
        });
        AddField(panel, "OpenAI API key", _openai, isPassword: true);
        AddField(panel, "DeepSeek API key", _deepseek, isPassword: true);
        AddField(panel, "Cursor API key", _cursor, isPassword: true);
        AddField(panel, "GitHub token", _github, isPassword: true);
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
            if (string.IsNullOrWhiteSpace(_adminPass.Password))
            {
                MessageBox.Show("Set an admin password.", "Credentials", MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            _context.AdminUsername = _adminUser.Text.Trim();
            _context.AdminPassword = _adminPass.Password;
            _context.OpenAiApiKey = _openai.Password;
            _context.DeepSeekApiKey = _deepseek.Password;
            _context.CursorApiKey = _cursor.Password;
            _context.GitHubToken = _github.Password;
            _next();
        };
        row.Children.Add(back);
        row.Children.Add(next);
        return row;
    }

    private static void AddField(Panel panel, string label, Control input, bool isPassword = false)
    {
        panel.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 0, 0, 4) });
        panel.Children.Add(input);
        _ = isPassword;
    }
}
