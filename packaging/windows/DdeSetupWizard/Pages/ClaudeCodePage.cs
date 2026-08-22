using System.Windows;
using System.Windows.Controls;
using DdeSetupWizard.Services;

namespace DdeSetupWizard.Pages;

/// <summary>
/// Claude Code auth: ensure official CLI on PATH, then subscription via CLI OAuth.
/// Anthropic API key is backup only. Never fakes signed-in without
/// <c>claude auth status</c> or a stored setup-token.
/// </summary>
public sealed class ClaudeCodePage : WizardPageBase
{
    private readonly SetupContext _context;
    private readonly Action _next;
    private readonly Action _back;
    private readonly TextBox _email;
    private readonly PasswordBox _setupTokenPaste;
    private readonly PasswordBox _apiKeyBackup;
    private readonly CheckBox _useApiKeyBackup;
    private readonly TextBlock _cliStatus;
    private readonly TextBlock _status;
    private Expander? _backupExpander;

    public ClaudeCodePage(SetupContext context, Action next, Action back)
        : base(
            "Claude Code",
            "Install the official Claude Code CLI if needed, then sign in with your subscription. API key is backup only.")
    {
        _context = context;
        _next = next;
        _back = back;
        _email = new TextBox();
        _setupTokenPaste = new PasswordBox();
        _apiKeyBackup = new PasswordBox();
        _useApiKeyBackup = new CheckBox
        {
            Content = "Use API key backup (if subscription login unavailable)",
            Margin = new Thickness(0, 8, 0, 8),
        };
        _cliStatus = new TextBlock
        {
            FontWeight = FontWeights.SemiBold,
            FontSize = 14,
            TextWrapping = TextWrapping.Wrap,
        };
        _status = new TextBlock
        {
            Margin = new Thickness(0, 12, 0, 0),
            TextWrapping = TextWrapping.Wrap,
            Foreground = System.Windows.Media.Brushes.DimGray,
        };
    }

    protected override UIElement BuildContent()
    {
        var panel = new StackPanel();

        panel.Children.Add(new TextBlock
        {
            Text = "Claude Code CLI (required for subscription auth)",
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 0, 0, 8),
        });

        var cliBox = new Border
        {
            Background = System.Windows.Media.Brushes.White,
            BorderBrush = System.Windows.Media.Brushes.LightGray,
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(6),
            Padding = new Thickness(14),
            Margin = new Thickness(0, 0, 0, 16),
        };
        var cliPanel = new StackPanel();
        cliPanel.Children.Add(_cliStatus);
        cliPanel.Children.Add(new TextBlock
        {
            Text =
                "Official install: native PowerShell installer (auto-updates). "
                + "Binary: %USERPROFILE%\\.local\\bin\\claude.exe. "
                + "Docs: " + ClaudeCodeCliService.DocsInstallUrl,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 6, 0, 0),
            Foreground = System.Windows.Media.Brushes.Gray,
        });
        cliBox.Child = cliPanel;
        panel.Children.Add(cliBox);

        var cliRow = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Margin = new Thickness(0, 0, 0, 16),
        };
        var installCli = new Button
        {
            Content = "Install Claude Code CLI",
            Margin = new Thickness(0, 0, 8, 0),
            Padding = new Thickness(12, 6, 12, 6),
        };
        var recheckCli = new Button
        {
            Content = "Re-check CLI",
            Margin = new Thickness(0, 0, 8, 0),
            Padding = new Thickness(12, 6, 12, 6),
        };
        var openDocs = new Button
        {
            Content = "Open install docs",
            Padding = new Thickness(12, 6, 12, 6),
        };
        installCli.Click += async (_, _) => await InstallCliAsync();
        recheckCli.Click += (_, _) => RefreshCliStatus();
        openDocs.Click += (_, _) => ClaudeCodeCliService.OpenInstallDocs();
        cliRow.Children.Add(installCli);
        cliRow.Children.Add(recheckCli);
        cliRow.Children.Add(openDocs);
        panel.Children.Add(cliRow);

        panel.Children.Add(new TextBlock
        {
            Text = "Subscription login (primary)",
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 0, 0, 8),
        });

        panel.Children.Add(new TextBlock
        {
            Text =
                "Anthropic does not publish a third-party OAuth client for Claude Code. "
                + "Email / GitHub / Google sign-in happens in the browser opened by the official CLI "
                + "(claude auth login / claude setup-token). "
                + "Docs: " + ClaudeCodeAuthService.DocsAuthenticationUrl,
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 8),
            Foreground = System.Windows.Media.Brushes.Gray,
        });

        AddLabeled(panel, "Email (optional prefill for CLI login)", _email);

        var primaryRow = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Margin = new Thickness(0, 12, 0, 0),
        };
        var signIn = new Button
        {
            Content = "Sign in with Claude Code CLI",
            Margin = new Thickness(0, 0, 8, 0),
            Padding = new Thickness(12, 6, 12, 6),
        };
        var verify = new Button
        {
            Content = "Verify login",
            Margin = new Thickness(0, 0, 8, 0),
            Padding = new Thickness(12, 6, 12, 6),
        };
        var setupToken = new Button
        {
            Content = "Generate setup-token…",
            Padding = new Thickness(12, 6, 12, 6),
        };
        signIn.Click += (_, _) => StartCliLogin();
        verify.Click += (_, _) => VerifyCliStatus();
        setupToken.Click += (_, _) => StartSetupTokenFlow();
        primaryRow.Children.Add(signIn);
        primaryRow.Children.Add(verify);
        primaryRow.Children.Add(setupToken);
        panel.Children.Add(primaryRow);

        panel.Children.Add(new TextBlock
        {
            Text = "Optional: paste long-lived token from `claude setup-token` (stored in Windows Credential Manager)",
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 16, 0, 4),
            Foreground = System.Windows.Media.Brushes.Gray,
        });
        AddLabeled(panel, "CLAUDE_CODE_OAUTH_TOKEN / setup-token", _setupTokenPaste);
        var storeToken = new Button
        {
            Content = "Store setup-token securely",
            Margin = new Thickness(0, 8, 0, 0),
            Padding = new Thickness(12, 6, 12, 6),
            HorizontalAlignment = HorizontalAlignment.Left,
        };
        storeToken.Click += (_, _) => StorePastedToken();
        panel.Children.Add(storeToken);

        panel.Children.Add(_status);
        RefreshCliStatus();
        RefreshStatusLabel();

        _backupExpander = new Expander
        {
            Header = "Backup / advanced — Anthropic API key",
            Margin = new Thickness(0, 20, 0, 0),
            IsExpanded = false,
        };
        var backupPanel = new StackPanel { Margin = new Thickness(0, 8, 0, 0) };
        backupPanel.Children.Add(new TextBlock
        {
            Text = "Backup if subscription login is unavailable. Not the primary Claude Code path.",
            TextWrapping = TextWrapping.Wrap,
            Margin = new Thickness(0, 0, 0, 8),
            Foreground = System.Windows.Media.Brushes.Gray,
        });
        backupPanel.Children.Add(_useApiKeyBackup);
        AddLabeled(backupPanel, "Anthropic API key", _apiKeyBackup);
        _backupExpander.Content = backupPanel;
        panel.Children.Add(_backupExpander);

        // Auto-probe once when the page is shown (does not invent signed-in).
        VerifyCliStatus(silentIfNotFound: true);

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
            PersistToContext();
            if (_context.ClaudeAuthMode == ClaudeAuthMode.ApiKeyBackup
                && string.IsNullOrWhiteSpace(_context.AnthropicApiKey))
            {
                MessageBox.Show(
                    "API key backup is selected but no key was entered.",
                    "Claude Code",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return;
            }

            if (_context.ClaudeAuthMode == ClaudeAuthMode.Subscription
                && _context.ClaudeSessionStatus is not ClaudeSessionStatus.VerifiedCliLogin
                and not ClaudeSessionStatus.StoredSetupToken)
            {
                var proceed = MessageBox.Show(
                    "No verified Claude subscription session yet.\n\n"
                    + "Install CLI if needed, then Sign in + Verify, or store a setup-token, "
                    + "or switch to API key backup.\n\nContinue anyway?",
                    "Claude Code",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Warning);
                if (proceed != MessageBoxResult.Yes)
                {
                    return;
                }
            }

            _next();
        };
        row.Children.Add(back);
        row.Children.Add(next);
        return row;
    }

    private async Task InstallCliAsync()
    {
        var consent = MessageBox.Show(
            "Install the official Claude Code CLI now?\n\n"
            + "Method: Anthropic native installer (irm https://claude.ai/install.ps1), "
            + "with winget fallback if needed.\n"
            + "DDE will also add %USERPROFILE%\\.local\\bin to your User PATH.\n\n"
            + "This does not sign you in — you still run Sign in after install.",
            "Install Claude Code CLI",
            MessageBoxButton.YesNo,
            MessageBoxImage.Question);
        if (consent != MessageBoxResult.Yes)
        {
            return;
        }

        _cliStatus.Text = "Installing Claude Code CLI…";
        try
        {
            var (ok, message, status) = await ClaudeCodeCliService.EnsureInstalledAsync(
                _context.InstallRoot,
                new Progress<string>(msg => _cliStatus.Text = msg),
                CancellationToken.None);
            RefreshCliStatus();
            if (ok && status == ClaudeCodeCliService.CliStatus.Present)
            {
                MessageBox.Show(
                    "Claude Code CLI is on PATH.\n\n"
                    + message + "\n\n"
                    + "Next: Sign in with Claude Code CLI, then Verify login.",
                    "Claude Code CLI",
                    MessageBoxButton.OK,
                    MessageBoxImage.Information);
                VerifyCliStatus(silentIfNotFound: true);
            }
            else
            {
                MessageBox.Show(
                    message + "\n\nYou can open install docs or retry.",
                    "Claude Code CLI",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
            }
        }
        catch (Exception ex)
        {
            RefreshCliStatus();
            MessageBox.Show(ex.Message, "Install failed", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void RefreshCliStatus()
    {
        var status = ClaudeCodeCliService.Detect();
        _cliStatus.Text = status == ClaudeCodeCliService.CliStatus.Present
            ? "CLI: present on PATH (Get-Command / known install path succeeded)."
            : "CLI: missing — click Install Claude Code CLI (required for subscription auth).";
        if (status == ClaudeCodeCliService.CliStatus.Present
            && _context.ClaudeSessionStatus == ClaudeSessionStatus.Blocked
            && (_context.ClaudeBlockedReason?.Contains("CLI not found", StringComparison.OrdinalIgnoreCase) == true
                || _context.ClaudeBlockedReason?.Contains("not found on PATH", StringComparison.OrdinalIgnoreCase) == true))
        {
            _context.ClaudeSessionStatus = ClaudeSessionStatus.None;
            _context.ClaudeBlockedReason = string.Empty;
            RefreshStatusLabel();
        }
    }

    private void StartCliLogin()
    {
        PersistToContext();
        _context.ClaudeAuthMode = ClaudeAuthMode.Subscription;
        _useApiKeyBackup.IsChecked = false;

        if (ClaudeCodeCliService.Detect() != ClaudeCodeCliService.CliStatus.Present)
        {
            var install = MessageBox.Show(
                "Claude Code CLI is not on PATH.\n\nInstall it now?",
                "Claude Code",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);
            if (install == MessageBoxResult.Yes)
            {
                _ = InstallCliAsync();
            }

            return;
        }

        var (ok, error, blocked) = ClaudeCodeAuthService.StartAuthLogin(_email.Text);
        if (!ok)
        {
            _context.ClaudeSessionStatus = ClaudeSessionStatus.Blocked;
            _context.ClaudeBlockedReason = blocked ?? error ?? "CLI login failed to start.";
            RefreshStatusLabel();
            MessageBox.Show(
                _context.ClaudeBlockedReason,
                "Claude Code",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        _context.ClaudeSessionStatus = ClaudeSessionStatus.PendingCliLogin;
        _context.ClaudeAuthSource = "claude_auth_login";
        _context.ClaudeBlockedReason = string.Empty;
        RefreshStatusLabel();
        MessageBox.Show(
            "A Claude Code login window was opened.\n\n"
            + "Complete email / GitHub / Google sign-in in the browser, "
            + "then click Verify login on this page.\n\n"
            + ClaudeCodeAuthService.DocsAuthenticationUrl,
            "Claude Code",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }

    private void StartSetupTokenFlow()
    {
        PersistToContext();
        if (ClaudeCodeCliService.Detect() != ClaudeCodeCliService.CliStatus.Present)
        {
            var install = MessageBox.Show(
                "Claude Code CLI is not on PATH.\n\nInstall it now?",
                "Claude Code",
                MessageBoxButton.YesNo,
                MessageBoxImage.Warning);
            if (install == MessageBoxResult.Yes)
            {
                _ = InstallCliAsync();
            }

            return;
        }

        var (ok, error, blocked) = ClaudeCodeAuthService.StartSetupToken();
        if (!ok)
        {
            _context.ClaudeSessionStatus = ClaudeSessionStatus.Blocked;
            _context.ClaudeBlockedReason = blocked ?? error ?? "setup-token failed to start.";
            RefreshStatusLabel();
            MessageBox.Show(
                _context.ClaudeBlockedReason,
                "Claude Code",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        _context.ClaudeSessionStatus = ClaudeSessionStatus.PendingCliLogin;
        _context.ClaudeAuthSource = "claude_setup_token";
        MessageBox.Show(
            "A Claude Code setup-token window was opened.\n\n"
            + "Approve access in the browser, copy the printed token (sk-ant-oat01-…), "
            + "paste it below, then click Store setup-token securely.",
            "Claude Code",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
        RefreshStatusLabel();
    }

    private void StorePastedToken()
    {
        PersistToContext();
        var raw = _setupTokenPaste.Password.Trim();
        var token = ClaudeCodeAuthService.ExtractOAuthToken(raw) ?? raw;
        if (!ClaudeCodeAuthService.IsValidOAuthToken(token))
        {
            MessageBox.Show(
                "Paste a valid Claude Code OAuth token from `claude setup-token` "
                + "(prefix sk-ant-oat01-). API keys (sk-ant-api03-) belong under Backup.",
                "Claude Code",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        var account = string.IsNullOrWhiteSpace(_context.ClaudeEmail)
            ? _email.Text.Trim()
            : _context.ClaudeEmail;
        if (!ClaudeCodeAuthService.StoreOAuthToken(token, account))
        {
            MessageBox.Show(
                "Could not store token in Windows Credential Manager.",
                "Claude Code",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        _context.ClaudeAuthMode = ClaudeAuthMode.Subscription;
        _context.ClaudeSessionStatus = ClaudeSessionStatus.StoredSetupToken;
        _context.ClaudeOAuthTokenRef = ClaudeCodeAuthService.OAuthTokenRef;
        _context.ClaudeAuthSource = "claude_setup_token";
        _context.ClaudeBlockedReason = string.Empty;
        _useApiKeyBackup.IsChecked = false;
        _setupTokenPaste.Password = string.Empty;
        RefreshStatusLabel();
        MessageBox.Show(
            "Setup-token stored in Windows Credential Manager.\n"
            + "Config will reference " + ClaudeCodeAuthService.OAuthTokenRef + " (not the raw secret).",
            "Claude Code",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }

    private void VerifyCliStatus(bool silentIfNotFound = false)
    {
        PersistToContext();
        RefreshCliStatus();
        var status = ClaudeCodeAuthService.QueryAuthStatus();
        ApplyStatus(status, silentIfNotFound);
        RefreshStatusLabel();
    }

    private void ApplyStatus(ClaudeCodeAuthService.AuthStatusResult status, bool silentIfNotFound)
    {
        if (!status.CliFound)
        {
            if (_context.ClaudeSessionStatus == ClaudeSessionStatus.StoredSetupToken
                && !string.IsNullOrWhiteSpace(_context.ClaudeOAuthTokenRef))
            {
                _context.ClaudeBlockedReason = status.BlockedReason ?? status.Error ?? string.Empty;
                return;
            }

            _context.ClaudeSessionStatus = ClaudeSessionStatus.Blocked;
            _context.ClaudeBlockedReason = status.BlockedReason ?? status.Error ?? "CLI not found.";
            if (!silentIfNotFound)
            {
                var install = MessageBox.Show(
                    _context.ClaudeBlockedReason + "\n\nInstall Claude Code CLI now?",
                    "Claude Code",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Warning);
                if (install == MessageBoxResult.Yes)
                {
                    _ = InstallCliAsync();
                }
            }

            return;
        }

        if (status.LoggedIn)
        {
            _context.ClaudeAuthMode = ClaudeAuthMode.Subscription;
            _context.ClaudeSessionStatus = ClaudeSessionStatus.VerifiedCliLogin;
            _context.ClaudeAuthSource = "claude_auth_status";
            _context.ClaudeBlockedReason = string.Empty;
            if (!string.IsNullOrWhiteSpace(status.Email))
            {
                _context.ClaudeEmail = status.Email!;
                _email.Text = status.Email!;
            }

            _context.ClaudeSubscriptionType = status.SubscriptionType ?? string.Empty;
            _context.ClaudeAuthMethod = status.AuthMethod ?? string.Empty;
            _context.ClaudeOrgName = status.OrgName ?? string.Empty;
            _useApiKeyBackup.IsChecked = false;
            return;
        }

        if (_context.ClaudeSessionStatus == ClaudeSessionStatus.StoredSetupToken)
        {
            return;
        }

        if (_context.ClaudeSessionStatus == ClaudeSessionStatus.PendingCliLogin)
        {
            return;
        }

        _context.ClaudeSessionStatus = ClaudeSessionStatus.None;
        _context.ClaudeSubscriptionType = string.Empty;
        _context.ClaudeAuthMethod = string.Empty;
        _context.ClaudeOrgName = string.Empty;
    }

    private void PersistToContext()
    {
        if (!string.IsNullOrWhiteSpace(_email.Text))
        {
            _context.ClaudeEmail = _email.Text.Trim();
        }

        var useBackup = _useApiKeyBackup.IsChecked == true;
        _context.AnthropicApiKey = _apiKeyBackup.Password;
        if (useBackup)
        {
            _context.ClaudeAuthMode = ClaudeAuthMode.ApiKeyBackup;
            if (_context.ClaudeSessionStatus is ClaudeSessionStatus.PendingCliLogin
                or ClaudeSessionStatus.Blocked)
            {
                _context.ClaudeSessionStatus = ClaudeSessionStatus.None;
                _context.ClaudeBlockedReason = string.Empty;
            }
        }
        else
        {
            _context.ClaudeAuthMode = ClaudeAuthMode.Subscription;
        }
    }

    private void RefreshStatusLabel()
    {
        _status.Text = _context.ClaudeSessionStatus switch
        {
            ClaudeSessionStatus.VerifiedCliLogin =>
                $"Signed in — verified via `claude auth status`"
                + (string.IsNullOrWhiteSpace(_context.ClaudeEmail) ? "" : $": {_context.ClaudeEmail}")
                + (string.IsNullOrWhiteSpace(_context.ClaudeSubscriptionType)
                    ? ""
                    : $" ({_context.ClaudeSubscriptionType})")
                + (string.IsNullOrWhiteSpace(_context.ClaudeAuthMethod)
                    ? ""
                    : $", method={_context.ClaudeAuthMethod}")
                + ".",
            ClaudeSessionStatus.StoredSetupToken =>
                $"Setup-token stored — ref {_context.ClaudeOAuthTokenRef}"
                + (string.IsNullOrWhiteSpace(_context.ClaudeEmail) ? "" : $" ({_context.ClaudeEmail})")
                + ". Worker Path A still uses the local `claude` CLI session; this token is for headless/CI custody.",
            ClaudeSessionStatus.PendingCliLogin =>
                "Pending — complete browser login in the Claude Code window, then click Verify login "
                + "(or paste/store a setup-token).",
            ClaudeSessionStatus.Blocked =>
                "CLI / auth blocked — " + (string.IsNullOrWhiteSpace(_context.ClaudeBlockedReason)
                    ? "use Install Claude Code CLI, then Sign in."
                    : _context.ClaudeBlockedReason),
            _ => "Not signed in — install CLI if needed, Sign in with Claude Code CLI, then Verify. "
                + "Do not mark complete without a verified session or stored setup-token.",
        };
    }

    private static void AddLabeled(Panel panel, string label, Control input)
    {
        panel.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 8, 0, 4) });
        panel.Children.Add(input);
    }
}
