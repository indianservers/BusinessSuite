import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../core/api_client.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({
    super.key,
    this.controller,
    this.serverUrl = '',
    this.onServerChanged,
    this.onServerTest,
  });
  final AppController? controller;
  final String serverUrl;
  final Future<void> Function(String)? onServerChanged;
  final Future<void> Function(String)? onServerTest;
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();
  bool _showPassword = false, _recovery = false;
  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _code.dispose();
    super.dispose();
  }

  void _submit() {
    if (_form.currentState!.validate()) {
      widget.controller?.authenticate(
        _email.text,
        _password.text,
        code: _code.text,
        recovery: _recovery,
      );
    }
  }

  Future<void> _settings() async {
    var url = widget.serverUrl;
    String? error;
    String? connectionStatus;
    var saving = false;
    var testing = false;
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('Server settings'),
          content: TextFormField(
            initialValue: url,
            enabled: !saving && !testing,
            keyboardType: TextInputType.url,
            decoration: InputDecoration(
              labelText: 'Business Suite server URL',
              hintText: 'https://suite.example.com',
              errorText: error,
              errorMaxLines: 4,
              helperText: connectionStatus,
            ),
            onChanged: (value) {
              url = value;
              if (error != null || connectionStatus != null) {
                update(() {
                  error = null;
                  connectionStatus = null;
                });
              }
            },
          ),
          actions: [
            TextButton(
              onPressed: saving || testing
                  ? null
                  : () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            if (widget.onServerTest case final test?)
              TextButton(
                onPressed: saving || testing
                    ? null
                    : () async {
                        update(() {
                          testing = true;
                          error = null;
                          connectionStatus = null;
                        });
                        try {
                          await test(url);
                          if (context.mounted) {
                            update(
                              () => connectionStatus =
                                  'Business Suite server reached.',
                            );
                          }
                        } catch (failure) {
                          if (context.mounted) {
                            update(
                              () => error = switch (failure) {
                                ArgumentError() => '${failure.message}',
                                ApiFailure() => failure.message,
                                _ => 'Could not reach the server.',
                              },
                            );
                          }
                        } finally {
                          if (context.mounted) update(() => testing = false);
                        }
                      },
                child: Text(testing ? 'Testing…' : 'Test connection'),
              ),
            FilledButton(
              onPressed: saving || testing
                  ? null
                  : () async {
                      update(() => saving = true);
                      try {
                        await widget.onServerChanged!(url);
                        if (context.mounted) Navigator.pop(context);
                      } catch (failure) {
                        if (context.mounted) {
                          update(() {
                            error = failure is ArgumentError
                                ? '${failure.message}'
                                : 'Could not save server settings.';
                            saving = false;
                          });
                        }
                      }
                    },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final mfa = controller?.mfaToken != null;
    final busy = controller?.busy ?? false;
    return Scaffold(
      appBar: AppBar(
        actions: [
          if (widget.onServerChanged != null)
            IconButton(
              tooltip: 'Server settings',
              onPressed: busy || mfa ? null : _settings,
              icon: const Icon(Icons.settings_outlined),
            ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _form,
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Icon(
                        Icons.space_dashboard_rounded,
                        size: 48,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Business Suite',
                        style: Theme.of(context).textTheme.headlineLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        mfa
                            ? 'Verify your sign-in'
                            : 'Sign in to your business workspace',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      if (controller == null &&
                          widget.onServerChanged != null) ...[
                        const SizedBox(height: 16),
                        OutlinedButton.icon(
                          onPressed: _settings,
                          icon: const Icon(Icons.settings_outlined),
                          label: const Text('Set server address'),
                        ),
                      ],
                      const SizedBox(height: 32),
                      if (!mfa) ...[
                        TextFormField(
                          controller: _email,
                          enabled: !busy,
                          decoration: const InputDecoration(
                            labelText: 'Work email',
                            prefixIcon: Icon(Icons.alternate_email),
                          ),
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.next,
                          autofillHints: const [AutofillHints.username],
                          autocorrect: false,
                          validator: (v) =>
                              v == null ||
                                  !RegExp(
                                    r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
                                  ).hasMatch(v.trim())
                              ? 'Enter your work email'
                              : null,
                        ),
                        const SizedBox(height: 16),
                        TextFormField(
                          controller: _password,
                          enabled: !busy,
                          obscureText: !_showPassword,
                          autofillHints: const [AutofillHints.password],
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              tooltip: _showPassword
                                  ? 'Hide password'
                                  : 'Show password',
                              onPressed: () => setState(
                                () => _showPassword = !_showPassword,
                              ),
                              icon: Icon(
                                _showPassword
                                    ? Icons.visibility_off
                                    : Icons.visibility,
                              ),
                            ),
                          ),
                          onFieldSubmitted: (_) => _submit(),
                          validator: (v) => v == null || v.isEmpty
                              ? 'Enter your password'
                              : null,
                        ),
                      ] else ...[
                        TextFormField(
                          controller: _code,
                          enabled: !busy,
                          autofocus: true,
                          decoration: InputDecoration(
                            labelText: _recovery
                                ? 'Recovery code'
                                : 'Authenticator code',
                          ),
                          keyboardType: _recovery
                              ? TextInputType.text
                              : TextInputType.number,
                          onFieldSubmitted: (_) => _submit(),
                          validator: (v) => v == null || v.trim().isEmpty
                              ? 'Enter your code'
                              : null,
                        ),
                        SwitchListTile(
                          contentPadding: EdgeInsets.zero,
                          title: const Text('Use a recovery code'),
                          value: _recovery,
                          onChanged: busy
                              ? null
                              : (v) => setState(() => _recovery = v),
                        ),
                        TextButton(
                          onPressed: busy ? null : controller?.cancelMfa,
                          child: const Text('Back to sign in'),
                        ),
                      ],
                      if (controller?.error != null) ...[
                        const SizedBox(height: 16),
                        Text(
                          controller!.error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                        if (controller.api.hasSession)
                          TextButton(
                            onPressed: controller.busy
                                ? null
                                : controller.loadAccount,
                            child: const Text('Retry loading account'),
                          ),
                      ],
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: busy || controller == null ? null : _submit,
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(
                            busy
                                ? 'Connecting…'
                                : mfa
                                ? 'Verify'
                                : 'Sign in',
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'Business Suite',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
