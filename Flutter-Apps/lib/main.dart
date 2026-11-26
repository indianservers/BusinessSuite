import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'app_controller.dart';
import 'core/api_client.dart';
import 'features/login_page.dart';
import 'features/suite_dashboard.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const storage = FlutterSecureStorage();
  String? saved;
  try {
    saved = await storage.read(key: 'business-suite-server');
  } on Exception {
    // Server settings remain available if secure storage cannot be read.
  }
  runApp(
    _ServerApp(
      initialUrl: saved ?? const String.fromEnvironment('API_BASE_URL'),
    ),
  );
}

class _ServerApp extends StatefulWidget {
  const _ServerApp({required this.initialUrl});
  final String initialUrl;

  @override
  State<_ServerApp> createState() => _ServerAppState();
}

class _ServerAppState extends State<_ServerApp> {
  AppController? _controller;
  String _url = '';

  AppController _connect(String url) => AppController(
    ApiClient(
      baseUrl: url,
      store: SecureSessionStore(server: url),
    ),
    suiteLogin: true,
  );

  @override
  void initState() {
    super.initState();
    _url = widget.initialUrl;
    if (_url.isEmpty) return;
    try {
      _controller = _connect(_url)..start();
    } on ArgumentError {
      // An invalid URL can be corrected from sign-in settings.
    }
  }

  Future<void> _save(String value) async {
    final uri = Uri.tryParse(value.trim());
    final raw = value.trim().replaceFirst(RegExp(r'/+$'), '');
    final url =
        uri != null &&
            (uri.path.isEmpty || uri.path == '/') &&
            !uri.hasQuery &&
            !uri.hasFragment
        ? '$raw/api/v1'
        : raw;
    if (uri == null || uri.host.isEmpty) {
      throw ArgumentError('Enter a full server URL, including https://.');
    }
    if (url == _url && _controller != null) return;
    final next = _connect(url);
    try {
      await const FlutterSecureStorage().write(
        key: 'business-suite-server',
        value: url,
      );
    } catch (_) {
      next.dispose();
      rethrow;
    }
    if (!mounted) {
      next.dispose();
      return;
    }
    final previous = _controller;
    setState(() {
      _url = url;
      _controller = next;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => previous?.dispose());
    await next.start();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (controller == null) {
      return MaterialApp(
        home: LoginPage(serverUrl: _url, onServerChanged: _save),
      );
    }
    return BusinessSuiteApp(
      key: ObjectKey(controller),
      controller: controller,
      serverUrl: _url,
      onServerChanged: _save,
    );
  }
}

class BusinessSuiteApp extends StatefulWidget {
  const BusinessSuiteApp({
    super.key,
    required this.controller,
    this.serverUrl = '',
    this.onServerChanged,
  });
  final AppController controller;
  final String serverUrl;
  final Future<void> Function(String)? onServerChanged;
  @override
  State<BusinessSuiteApp> createState() => _BusinessSuiteAppState();
}

class _BusinessSuiteAppState extends State<BusinessSuiteApp> {
  final _navigator = GlobalKey<NavigatorState>();
  AppController get controller => widget.controller;
  bool _signedIn = false;
  @override
  void initState() {
    super.initState();
    _signedIn = controller.user != null;
    controller.addListener(_sessionChanged);
  }

  void _sessionChanged() {
    if (_signedIn && controller.user == null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _navigator.currentState?.popUntil((route) => route.isFirst);
        }
      });
    }
    _signedIn = controller.user != null;
  }

  @override
  void dispose() {
    controller.removeListener(_sessionChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    navigatorKey: _navigator,
    title: 'Business Suite',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6554C0)),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
      appBarTheme: const AppBarTheme(centerTitle: false),
    ),
    home: ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        if (controller.loading && controller.user == null) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return controller.user == null
            ? LoginPage(
                controller: controller,
                serverUrl: widget.serverUrl,
                onServerChanged: widget.onServerChanged,
              )
            : SuiteDashboard(controller: controller);
      },
    ),
  );
}
