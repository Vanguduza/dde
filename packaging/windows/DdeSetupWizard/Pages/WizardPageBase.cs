using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace DdeSetupWizard.Pages;

public abstract class WizardPageBase : Page
{
    protected WizardPageBase(string title, string subtitle)
    {
        var root = new Grid { Margin = new Thickness(28) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var header = new StackPanel { Margin = new Thickness(0, 0, 0, 18) };
        header.Children.Add(new TextBlock
        {
            Text = title,
            FontSize = 24,
            FontWeight = FontWeights.SemiBold,
        });
        header.Children.Add(new TextBlock
        {
            Text = subtitle,
            Margin = new Thickness(0, 6, 0, 0),
            TextWrapping = TextWrapping.Wrap,
            Foreground = Brushes.Gray,
        });
        Grid.SetRow(header, 0);
        root.Children.Add(header);

        var body = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        body.Content = BuildContent();
        Grid.SetRow(body, 1);
        root.Children.Add(body);

        var footer = BuildFooter();
        Grid.SetRow(footer, 2);
        root.Children.Add(footer);

        Content = root;
    }

    protected abstract UIElement BuildContent();
    protected abstract UIElement BuildFooter();
}
