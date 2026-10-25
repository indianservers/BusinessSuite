import 'package:flutter/material.dart';

import 'app_controller.dart';
import 'core/api_client.dart';
import 'features/login_page.dart';
import 'features/workspace_page.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  const baseUrl = String.fromEnvironment('API_BASE_URL');
  if (baseUrl.isEmpty) {
    runApp(
      const MaterialApp(
        home: Scaffold(
          body: SafeArea(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Text(
                'Backend URL required. Start this app with --dart-define=API_BASE_URL=https://your-server/api/v1. See README.md for local development.',
              ),
            ),
          ),
        ),
      ),
    );
    return;
  }
  try {
    final controller = AppController(
      ApiClient(
        baseUrl: baseUrl,
        store: SecureSessionStore(server: baseUrl),
      ),
    );
    runApp(BusinessSuiteApp(controller: controller));
    controller.start();
  } on ArgumentError catch (error) {
    runApp(
      MaterialApp(
        home: Scaffold(
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text('${error.message}'),
            ),
          ),
        ),
      ),
    );
  }
}

class BusinessSuiteApp extends StatefulWidget {
  const BusinessSuiteApp({super.key, required this.controller});
  final AppController controller;
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
    title: 'KaryaFlow · BusinessSuite',
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
            ? LoginPage(controller: controller)
            : WorkspacePage(controller: controller);
      },
    ),
  );
}
