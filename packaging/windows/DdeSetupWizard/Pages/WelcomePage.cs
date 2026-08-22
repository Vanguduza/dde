using System.Windows;
using System.Windows.Controls;

namespace DdeSetupWizard.Pages;

public sealed class WelcomePage : WizardPageBase
{
    private readonly Action _next;

    public WelcomePage(SetupContext context, Action next)
        : base("Welcome to DDE", "Local appliance installer — Core, database, Redis, migrations, and Docker-backed workers.")
    {
        _next = next;
        _ = context;
    }

    protected override UIElement BuildContent()
    {
        var panel = new StackPanel();
        panel.Children.Add(new TextBlock
        {
            TextWrapping = TextWrapping.Wrap,
            Text =
                "This wizard will:\n" +
                "• Verify or install Docker Desktop\n" +
                "• Configure local or cloud deployment\n" +
                "• Collect admin login and provider API keys\n" +
                "• Ensure Claude Code CLI on PATH, then subscription sign-in (API key backup only)\n" +
                "• Load the bundled DDE Core image\n" +
                "• Apply database migrations\n" +
                "• Start DDE Core and verify /healthz",
            FontSize = 14,
            LineHeight = 24,
        });
        return panel;
    }

    protected override UIElement BuildFooter()
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var next = new Button { Content = "Next", IsDefault = true };
        next.Click += (_, _) => _next();
        row.Children.Add(next);
        return row;
    }
}
