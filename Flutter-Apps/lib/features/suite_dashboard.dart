import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../app_controller.dart';
import '../core/api_client.dart';
import '../core/crm_offline_edits.dart';
import '../core/models.dart';
import '../core/suite_read_cache.dart';
import 'notes_page.dart';
import 'crm_lead_page.dart';
import 'sales_order_page.dart';
import 'suite_notifications_page.dart';
import 'account_settings_panel.dart';
import 'workspace_page.dart';

typedef _App = ({
  String grant,
  String title,
  String caption,
  IconData icon,
  Color color,
  String? endpoint,
});

const List<_App> _apps = [
  (
    grant: 'srm',
    title: 'Appointments',
    caption: 'Bookings & schedule',
    icon: LucideIcons.calendarDays,
    color: Color(0xff965831),
    endpoint: '/srm/industry/records',
  ),
  (
    grant: 'power_apps',
    title: 'Power Apps',
    caption: 'Build & automate',
    icon: LucideIcons.zap,
    color: Color(0xff7638c8),
    endpoint: '/power-apps/environments',
  ),
  (
    grant: 'hrms',
    title: 'AI HRMS',
    caption: 'People & payroll',
    icon: LucideIcons.users,
    color: Color(0xff2964c2),
    endpoint: '/employees/',
  ),
  (
    grant: 'crm',
    title: 'VyaparaCRM',
    caption: 'Leads & customers',
    icon: LucideIcons.users,
    color: Color(0xff087c68),
    endpoint: CrmLeadPage.endpoint,
  ),
  (
    grant: 'project_management',
    title: 'KaryaFlow PMS',
    caption: 'Projects & tasks',
    icon: LucideIcons.listChecks,
    color: Color(0xff6145ce),
    endpoint: null,
  ),
  (
    grant: 'srm',
    title: 'Sales & POS',
    caption: 'Sales & inventory',
    icon: LucideIcons.shoppingCart,
    color: Color(0xffc25448),
    endpoint: '/srm/sales-orders',
  ),
  (
    grant: 'fam',
    title: 'Finance & Accounting',
    caption: 'Accounts & ledgers',
    icon: LucideIcons.chartNoAxesColumnIncreasing,
    color: Color(0xff6244c6),
    endpoint: '/fam/parties',
  ),
];

class SuiteDashboard extends StatefulWidget {
  const SuiteDashboard({super.key, required this.controller});
  final AppController controller;

  @override
  State<SuiteDashboard> createState() => _SuiteDashboardState();
}

class _SuiteDashboardState extends State<SuiteDashboard> {
  late Future<Json> _access = _load();
  String _query = '';
  Timer? _syncTimer;
  AppLifecycleListener? _lifecycle;
  bool _syncing = false;
  int _unreadNotifications = 0;
  int _notificationRequest = 0;

  Future<void> _refreshUnread() async {
    final controller = widget.controller;
    if (controller.offline || controller.user == null) return;
    final request = ++_notificationRequest;
    try {
      final result =
          await controller.api.request('GET', '/notifications/unread-count')
              as Json;
      if (mounted &&
          request == _notificationRequest &&
          controller.user != null) {
        setState(() => _unreadNotifications = (result['unread'] as int?) ?? 0);
      }
    } catch (_) {
      // Retain the last known badge while the server is unavailable.
    }
  }

  @override
  void initState() {
    super.initState();
    _refreshUnread();
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      _syncTimer = Timer.periodic(
        const Duration(seconds: 20),
        (_) => _syncEdits(_access),
      );
      _lifecycle = AppLifecycleListener(
        onResume: () {
          _syncEdits(_access);
          _refreshUnread();
        },
      );
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _syncEdits(_access);
      });
    }
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
    _lifecycle?.dispose();
    super.dispose();
  }

  String? _localScope(Json access) {
    final controller = widget.controller;
    final id = controller.user?.id;
    final company = access['companyId'];
    if (id == null ||
        company == null ||
        kIsWeb ||
        defaultTargetPlatform != TargetPlatform.android) {
      return null;
    }
    return jsonEncode([controller.api.dio.options.baseUrl, id, company]);
  }

  Future<void> _syncEdits(Future<Json> accessFuture) async {
    if (_syncing ||
        !mounted ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }
    final controller = widget.controller;
    final revision = controller.api.sessionRevision;
    _syncing = true;
    try {
      final access = await accessFuture;
      if (!mounted ||
          !identical(_access, accessFuture) ||
          revision != controller.api.sessionRevision ||
          !_allowed(access, 'crm')) {
        return;
      }
      final scope = _localScope(access);
      if (scope == null) return;
      final edits = CrmOfflineEdits(scope);
      if (await edits.hasPending &&
          mounted &&
          identical(_access, accessFuture) &&
          revision == controller.api.sessionRevision) {
        await edits.sync(controller.api);
      }
    } catch (_) {
      // Leave the durable queue available when local storage or the API is unavailable.
    } finally {
      _syncing = false;
    }
  }

  Future<Json> _load({bool reconnect = false}) async {
    final controller = widget.controller;
    if (controller.offline && reconnect) {
      await controller.loadAccount(restoreOffline: true);
    }
    if (controller.offline) {
      final cached = controller.api.offlineSuite?['access'];
      if (cached is Json) return cached;
    }
    final user = controller.user;
    final access = await controller.api.request('GET', '/access/me') as Json;
    if (user != null &&
        identical(user, controller.user) &&
        user.id != null &&
        access['companyId'] != null) {
      final grants = access['grants'] as Json? ?? {};
      try {
        await controller.api.rememberSuite(
          {'id': user.id, 'email': user.email},
          {
            'companyId': access['companyId'],
            'companyName': access['companyName'],
            'grants': {
              for (final key in ['crm', 'srm'])
                key: {
                  'enabled': _allowed(access, key) && grants.containsKey(key),
                },
            },
          },
        );
      } catch (_) {
        // The live dashboard remains available if secure storage cannot write.
      }
    }
    return access;
  }

  void _push(Widget screen) => Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => screen));

  bool _allowed(Json access, String key) {
    final disabled = access['companyDisabledModules'] as List? ?? [];
    final grants = access['grants'] as Json? ?? {};
    return !disabled.contains(key) &&
        ((grants[key] as Json?)?['enabled'] == true ||
            access['isGlobalAdmin'] == true);
  }

  void _open(_App app, Json access) {
    final controller = widget.controller;
    if (app.title == 'Appointments') {
      _push(_AppointmentBranches(controller: controller));
      return;
    }
    if (app.grant == 'project_management') {
      _push(
        ListenableBuilder(
          listenable: controller,
          builder: (_, _) => controller.user == null
              ? const SizedBox.shrink()
              : WorkspacePage(controller: controller),
        ),
      );
      final workspace = controller.selected;
      if (workspace != null && controller.overview == null) {
        controller.selectWorkspace(workspace);
      }
      return;
    }
    final cache = app.grant == 'crm' || app.title == 'Sales & POS'
        ? _localScope(access)
        : null;
    _push(
      _SuiteRecords(
        title: app.title,
        controller: controller,
        path: app.endpoint,
        cachePrefix: cache,
        showInventory: app.title == 'Sales & POS',
        offlineOnly: controller.offline,
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xfff8f7ff),
    appBar: AppBar(
      backgroundColor: const Color(0xfff8f7ff),
      title: const Text('Business Suite'),
      actions: [
        IconButton(
          tooltip: 'Notifications',
          icon: Badge(
            isLabelVisible:
                !widget.controller.offline && _unreadNotifications > 0,
            label: Text(
              _unreadNotifications > 99 ? '99+' : '$_unreadNotifications',
            ),
            child: const Icon(LucideIcons.bell),
          ),
          onPressed: () async {
            await Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) =>
                    SuiteNotificationsPage(api: widget.controller.api),
              ),
            );
            if (mounted) await _refreshUnread();
          },
        ),
        IconButton(
          tooltip: 'Settings',
          icon: const Icon(LucideIcons.settings),
          onPressed: () => _push(_SuiteSettings(controller: widget.controller)),
        ),
      ],
    ),
    body: FutureBuilder<Json>(
      future: _access,
      builder: (context, snapshot) {
        final access = snapshot.data;
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Could not load your applications.'),
                TextButton(
                  onPressed: () => setState(() {
                    _access = _load();
                  }),
                  child: const Text('Try again'),
                ),
              ],
            ),
          );
        }
        if (access == null) {
          return const Center(child: CircularProgressIndicator());
        }
        final allowed = _apps
            .where((app) => _allowed(access, app.grant))
            .where(
              (app) =>
                  !widget.controller.offline || app.title != 'Appointments',
            )
            .toList();
        final shown = allowed
            .where(
              (app) => '${app.title} ${app.caption}'.toLowerCase().contains(
                _query.trim().toLowerCase(),
              ),
            )
            .toList();
        return RefreshIndicator(
          onRefresh: () async {
            setState(() {
              _access = _load(reconnect: true);
            });
            try {
              await _access;
            } catch (_) {
              /* Reported by FutureBuilder. */
            }
          },
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
            children: [
              if (widget.controller.offline)
                const ListTile(
                  leading: Icon(LucideIcons.wifiOff),
                  title: Text('Offline · Saved records only'),
                  subtitle: Text('Pull to refresh when you reconnect.'),
                ),
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(22),
                  gradient: const LinearGradient(
                    colors: [Color(0xffeeeaff), Color(0xffe3d8fa)],
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Your work starts here.',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 8),
                    const Text('Open an application to continue.'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (access['companyName'] case final String company)
                ListTile(
                  leading: const Icon(LucideIcons.building2),
                  title: Text(company),
                  subtitle: const Text('Current company'),
                ),
              TextField(
                onChanged: (value) => setState(() => _query = value),
                decoration: const InputDecoration(
                  prefixIcon: Icon(LucideIcons.search),
                  hintText: 'Find an application',
                  filled: true,
                  fillColor: Colors.white,
                ),
              ),
              const SizedBox(height: 18),
              Text(
                'Your applications (${allowed.length})',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 10),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisExtent: 126,
                  mainAxisSpacing: 8,
                  crossAxisSpacing: 8,
                ),
                itemCount: shown.length,
                itemBuilder: (context, index) {
                  final app = shown[index];
                  return Card(
                    margin: EdgeInsets.zero,
                    color: Colors.white,
                    elevation: 0,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(12),
                      onTap: () => _open(app, access),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(app.icon, color: app.color),
                            const SizedBox(height: 8),
                            Text(
                              app.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Text(
                              app.caption,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
              if (shown.isEmpty)
                Text(
                  allowed.isEmpty
                      ? 'No applications assigned.'
                      : 'No matching applications.',
                ),
              if (_allowed(access, 'project_management'))
                ListTile(
                  leading: const Icon(LucideIcons.fileText),
                  title: const Text('Notes'),
                  onTap: () => _push(NotesPage(api: widget.controller.api)),
                ),
              if (access['isAccessAdmin'] == true ||
                  access['isGlobalAdmin'] == true)
                ListTile(
                  leading: const Icon(LucideIcons.shieldCheck),
                  title: const Text('Company Admin'),
                  onTap: () => _push(
                    _SuiteRecords(
                      title: 'Company Admin',
                      controller: widget.controller,
                      path: '/access/me',
                      collection: 'organizations',
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    ),
  );
}

class _SuiteSettings extends StatefulWidget {
  const _SuiteSettings({required this.controller});
  final AppController controller;

  @override
  State<_SuiteSettings> createState() => _SuiteSettingsState();
}

class _SuiteSettingsState extends State<_SuiteSettings> {
  late Future<dynamic> _directory = _load();
  String _query = '';
  AppController get controller => widget.controller;

  Future<dynamic> _load() => controller.api.request('GET', '/access/settings');

  void _openOption(Json option) {
    final id = option['id'];
    if (id is! String || id.isEmpty) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _SettingOption(
          controller: controller,
          id: id,
          title: '${option['title']}',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Settings')),
    body: ListView(
      children: [
        ListTile(
          leading: const Icon(LucideIcons.userRound),
          title: const Text('Account'),
          subtitle: Text(controller.user?.email ?? ''),
          onTap: () => _openOption({'id': 'account', 'title': 'Account'}),
        ),
        ListTile(
          leading: const Icon(LucideIcons.server),
          title: const Text('Server'),
          subtitle: Text(controller.api.dio.options.baseUrl),
        ),
        ListTile(
          leading: const Icon(LucideIcons.logOut),
          title: const Text('Sign out'),
          onTap: controller.signOut,
        ),
        const Divider(),
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            onChanged: (value) =>
                setState(() => _query = value.trim().toLowerCase()),
            decoration: const InputDecoration(
              prefixIcon: Icon(LucideIcons.search),
              labelText: 'Find a setting',
            ),
          ),
        ),
        FutureBuilder(
          future: _directory,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return ListTile(
                title: const Text('Could not load workspace settings'),
                trailing: TextButton(
                  onPressed: () => setState(() {
                    _directory = _load();
                  }),
                  child: const Text('Retry'),
                ),
              );
            }
            final data = snapshot.data;
            if (data is! Json) return const LinearProgressIndicator();
            final options = (data['options'] as List? ?? [])
                .whereType<Json>()
                .where(
                  (item) => '${item['title']} ${item['description']}'
                      .toLowerCase()
                      .contains(_query),
                );
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ListTile(
                  leading: const Icon(LucideIcons.building2),
                  title: Text('${data['companyName'] ?? 'Workspace settings'}'),
                ),
                for (final option in options)
                  ListTile(
                    title: Text('${option['title'] ?? ''}'),
                    subtitle: Text('${option['description'] ?? ''}'),
                    trailing: const Icon(LucideIcons.chevronRight),
                    onTap: () => _openOption(option),
                  ),
              ],
            );
          },
        ),
      ],
    ),
  );
}

class _SettingOption extends StatefulWidget {
  const _SettingOption({
    required this.controller,
    required this.id,
    required this.title,
  });
  final AppController controller;
  final String id, title;

  @override
  State<_SettingOption> createState() => _SettingOptionState();
}

class _SettingOptionState extends State<_SettingOption> {
  late final _access = widget.controller.api.request(
    'GET',
    '/access/settings/options/${Uri.encodeComponent(widget.id)}',
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: FutureBuilder(
      future: _access,
      builder: (_, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final data = snapshot.data;
        if (data is! Json) {
          return const Center(child: CircularProgressIndicator());
        }
        if (widget.id == 'account') {
          return AccountSettingsPanel(
            api: widget.controller.api,
            user: widget.controller.user,
          );
        }
        return ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Text('${data['description'] ?? ''}'),
            const SizedBox(height: 12),
            Text(
              data['editable'] == true
                  ? 'Editing this setting is available on the web.'
                  : 'Read-only access for this setting.',
            ),
          ],
        );
      },
    ),
  );
}

class _AppointmentBranches extends StatefulWidget {
  const _AppointmentBranches({required this.controller});
  final AppController controller;

  @override
  State<_AppointmentBranches> createState() => _AppointmentBranchesState();
}

class _AppointmentBranchesState extends State<_AppointmentBranches> {
  late final _context = widget.controller.api.request(
    'GET',
    '/branches/context',
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Appointments')),
    body: FutureBuilder(
      future: _context,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        final data = snapshot.data;
        if (data is! Json) {
          return const Center(child: CircularProgressIndicator());
        }
        final branches = (data['branches'] as List? ?? [])
            .whereType<Json>()
            .where((branch) => branch['is_active'] == true);
        return ListView(
          children: [
            const ListTile(title: Text('Choose a branch')),
            for (final branch in branches)
              ListTile(
                title: Text('${branch['name']}'),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => _SuiteRecords(
                      title: 'Appointments · ${branch['name']}',
                      controller: widget.controller,
                      path: '/srm/industry/records',
                      query: const {'kind': 'appointment'},
                      scopeHeaders: {'X-Suite-Branch': '${branch['id']}'},
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    ),
  );
}

class _SuiteRecords extends StatefulWidget {
  const _SuiteRecords({
    required this.title,
    required this.controller,
    required this.path,
    this.collection,
    this.query = const {},
    this.scopeHeaders = const {},
    this.cachePrefix,
    this.showInventory = false,
    this.offlineOnly = false,
  });
  final String title;
  final AppController controller;
  final String? path, collection;
  final Map<String, dynamic> query;
  final Map<String, String> scopeHeaders;
  final String? cachePrefix;
  final bool showInventory;
  final bool offlineOnly;

  @override
  State<_SuiteRecords> createState() => _SuiteRecordsState();
}

class _SuiteRecordsState extends State<_SuiteRecords> {
  CrmOfflineEdits? get _crmEdits {
    final scope = widget.cachePrefix;
    return widget.path == CrmLeadPage.endpoint && scope != null
        ? CrmOfflineEdits(scope)
        : null;
  }

  String _term = '';
  late Future<List<Json>> _records = _load();
  List<Json>? _cached;
  String? get _cacheKey => widget.cachePrefix == null
      ? null
      : '${widget.cachePrefix}:${widget.path}';

  Future<List<Json>> _load() async {
    final path = widget.path;
    if (path == null) return [];
    final cacheKey = _cacheKey;
    if (cacheKey != null) {
      try {
        final cached = await SuiteReadCache.read(cacheKey);
        if (mounted && cached != null) setState(() => _cached = cached);
      } catch (_) {
        /* A cache failure does not block online reads. */
      }
    }
    if (widget.offlineOnly) {
      throw ApiFailure(
        'Offline. Open this page online to save records on this device.',
      );
    }
    dynamic data;
    try {
      data = await widget.controller.api.request(
        'GET',
        path,
        query: widget.query,
        scopeHeaders: widget.scopeHeaders,
      );
      final edits = _crmEdits;
      if (edits != null) {
        try {
          if (await edits.hasPending) {
            await edits.sync(widget.controller.api);
            data = await widget.controller.api.request(
              'GET',
              path,
              query: widget.query,
              scopeHeaders: widget.scopeHeaders,
            );
          }
        } catch (_) {
          // The list remains readable if the device edit store is unavailable.
        }
      }
    } on ApiFailure catch (error) {
      if (cacheKey != null && (error.status == 401 || error.status == 403)) {
        if (mounted) setState(() => _cached = null);
        try {
          await SuiteReadCache.clear(cacheKey);
        } catch (_) {}
      }
      rethrow;
    }
    final collection = widget.collection;
    final rows = data is List
        ? data
        : data is Json
        ? (collection == null
              ? data['items'] ?? data['results']
              : data[collection])
        : null;
    if (rows is! List) {
      throw const FormatException(
        'The server returned an unexpected records format.',
      );
    }
    final records = rows.cast<Json>();
    if (cacheKey != null) {
      final projection = [
        for (final record in records)
          {
            for (final field in [
              'id',
              'status',
              'title',
              'name',
              'first_name',
              'last_name',
              'full_name',
              'version',
              'company_name',
              'order_number',
              'currency',
              'subtotal',
              'discount_amount',
              'tax_amount',
              'total_amount',
              'expected_start_date',
              'expected_end_date',
              'sku',
              'item_name',
              'current_quantity',
              'reorder_level',
              'unit_code',
            ])
              if (record[field] is String || record[field] is num)
                field: record[field],
          },
      ];
      try {
        await SuiteReadCache.write(cacheKey, projection);
      } catch (_) {}
    }
    return records;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.title),
      actions: [
        IconButton(
          tooltip: 'Refresh',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: () => setState(() {
            _records = _load();
          }),
        ),
        if (widget.showInventory)
          IconButton(
            tooltip: 'Inventory',
            icon: const Icon(LucideIcons.package),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Inventory',
                  controller: widget.controller,
                  path: '/srm/inventory/items',
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: widget.offlineOnly,
                ),
              ),
            ),
          ),
      ],
    ),
    body: widget.path == null
        ? const Center(
            child: Text(
              'Native appointment scheduling is still in development.',
            ),
          )
        : FutureBuilder<List<Json>>(
            future: _records,
            builder: (context, snapshot) {
              if (snapshot.hasError &&
                  (_cached == null ||
                      snapshot.error is! ApiFailure ||
                      (snapshot.error as ApiFailure).status != null)) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          snapshot.error.toString(),
                          textAlign: TextAlign.center,
                        ),
                        TextButton(
                          onPressed: () => setState(() {
                            _records = _load();
                          }),
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                );
              }
              final rows = snapshot.data ?? _cached;
              if (rows == null) {
                return const Center(child: CircularProgressIndicator());
              }
              if (rows.isEmpty) {
                return const Center(child: Text('No records found'));
              }
              final cached = snapshot.data == null;
              final search = widget.cachePrefix != null;
              final visible = _term.isEmpty
                  ? rows
                  : rows
                        .where(
                          (item) =>
                              [
                                    'title',
                                    'name',
                                    'first_name',
                                    'last_name',
                                    'order_number',
                                    'status',
                                    'sku',
                                    'item_name',
                                    'full_name',
                                    'company_name',
                                  ]
                                  .map((key) => item[key] ?? '')
                                  .join(' ')
                                  .toLowerCase()
                                  .contains(_term),
                        )
                        .toList();
              return Column(
                children: [
                  if (search)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                      child: TextField(
                        onChanged: (value) =>
                            setState(() => _term = value.trim().toLowerCase()),
                        decoration: InputDecoration(
                          prefixIcon: const Icon(LucideIcons.search),
                          labelText: switch (widget.path) {
                            CrmLeadPage.endpoint => 'Search saved leads',
                            '/srm/inventory/items' => 'Search saved products',
                            _ => 'Search saved orders',
                          },
                        ),
                      ),
                    ),
                  if (visible.isEmpty) const Text('No matching records'),
                  Expanded(
                    child: ListView.builder(
                      itemCount: visible.length + (cached ? 1 : 0),
                      itemBuilder: (_, index) {
                        if (cached && index == 0) {
                          return ListTile(
                            title: Text(
                              snapshot.hasError
                                  ? 'Offline · Saved records'
                                  : 'Saved records · Refreshing',
                            ),
                          );
                        }
                        final item = visible[index - (cached ? 1 : 0)];
                        final name = [
                          item['first_name'],
                          item['last_name'],
                        ].whereType<String>().join(' ');
                        final label =
                            item['item_name'] ??
                            item['title'] ??
                            item['name'] ??
                            item['legal_name'] ??
                            item['full_name'] ??
                            item['order_number'] ??
                            (name.isEmpty
                                ? 'Record ${item['id'] ?? index + 1}'
                                : name);
                        final subtitle = [
                          item['sku'],
                          item['status'],
                        ].whereType<String>().join(' · ');
                        return ListTile(
                          title: Text('$label'),
                          subtitle: subtitle.isEmpty ? null : Text(subtitle),
                          onTap:
                              (widget.path == '/srm/inventory/items' ||
                                      widget.path == '/srm/sales-orders' ||
                                      widget.path == CrmLeadPage.endpoint) &&
                                  item['id'] is int
                              ? () => Navigator.of(context).push(
                                  MaterialPageRoute<void>(
                                    builder: (_) =>
                                        widget.path == CrmLeadPage.endpoint
                                        ? CrmLeadPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            offlineEdits: _crmEdits,
                                            onSaved: () {
                                              if (mounted) {
                                                setState(() {
                                                  _records = _load();
                                                });
                                              }
                                            },
                                            offline:
                                                widget.offlineOnly ||
                                                (cached && snapshot.hasError),
                                          )
                                        : widget.path == '/srm/sales-orders'
                                        ? SalesOrderPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            offline:
                                                widget.offlineOnly ||
                                                (cached && snapshot.hasError),
                                          )
                                        : InventoryProductPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            offline:
                                                widget.offlineOnly ||
                                                (cached && snapshot.hasError),
                                          ),
                                  ),
                                )
                              : null,
                        );
                      },
                    ),
                  ),
                ],
              );
            },
          ),
  );
}

class InventoryProductPage extends StatefulWidget {
  const InventoryProductPage({
    super.key,
    required this.api,
    required this.summary,
    required this.offline,
  });
  final ApiClient api;
  final Json summary;
  final bool offline;

  @override
  State<InventoryProductPage> createState() => _InventoryProductPageState();
}

class _InventoryProductPageState extends State<InventoryProductPage> {
  late Future<Json> _product = _load();

  Future<Json> _load() async => widget.offline
      ? widget.summary
      : await widget.api.request(
              'GET',
              '/srm/inventory/items/${widget.summary['id']}',
            )
            as Json;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Product details')),
    body: FutureBuilder<Json>(
      future: _product,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${snapshot.error}'),
                TextButton(
                  onPressed: () => setState(() {
                    _product = _load();
                  }),
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }
        final data = snapshot.data;
        if (data == null) {
          return const Center(child: CircularProgressIndicator());
        }
        final ledger = (data['ledger'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${data['item_name'] ?? data['name'] ?? 'Product'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (widget.offline)
              const ListTile(title: Text('Offline · Saved product summary')),
            for (final field in const {
              'sku': 'SKU',
              'unit_code': 'Unit',
              'current_quantity': 'On hand',
              'reorder_level': 'Reorder level',
            }.entries)
              if (data[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('${data[field.key]}'),
                ),
            if (!widget.offline) ...[
              const Divider(),
              Text(
                'Recent stock movements',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              if (ledger.isEmpty)
                const ListTile(title: Text('No stock movements')),
              for (final row in ledger)
                ListTile(
                  title: Text(
                    '${row['movement_number'] ?? row['movement_type'] ?? 'Movement'}',
                  ),
                  subtitle: Text(
                    '${row['movement_date'] ?? ''} · In ${row['quantity_in'] ?? 0} · Out ${row['quantity_out'] ?? 0}',
                  ),
                ),
            ],
          ],
        );
      },
    ),
  );
}
