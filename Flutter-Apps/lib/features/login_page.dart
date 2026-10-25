import 'package:flutter/material.dart';

import '../app_controller.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.controller});
  final AppController controller;
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
      widget.controller.authenticate(
        _email.text,
        _password.text,
        code: _code.text,
        recovery: _recovery,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final mfa = controller.mfaToken != null;
    return Scaffold(
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
                        'KaryaFlow',
                        style: Theme.of(context).textTheme.headlineLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        mfa
                            ? 'Verify your sign-in'
                            : 'Your projects. Your team. In sync.',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 32),
                      if (!mfa) ...[
                        TextFormField(
                          controller: _email,
                          enabled: !controller.busy,
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
                          enabled: !controller.busy,
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
                          enabled: !controller.busy,
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
                          onChanged: controller.busy
                              ? null
                              : (v) => setState(() => _recovery = v),
                        ),
                        TextButton(
                          onPressed: controller.busy
                              ? null
                              : controller.cancelMfa,
                          child: const Text('Back to sign in'),
                        ),
                      ],
                      if (controller.error != null) ...[
                        const SizedBox(height: 16),
                        Text(
                          controller.error!,
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
                        onPressed: controller.busy ? null : _submit,
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(
                            controller.busy
                                ? 'Connecting…'
                                : mfa
                                ? 'Verify'
                                : 'Sign in',
                          ),
                        ),
                      ),
                      const SizedBox(height: 24),
                      Text(
                        'BusinessSuite · Project Management',
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
