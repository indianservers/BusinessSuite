import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../app_controller.dart';
import '../core/api_client.dart';
import '../core/crm_detail_snapshot.dart';
import '../core/crm_offline_edits.dart';
import '../core/inventory_offline_creates.dart';
import '../core/inventory_stock_receipts.dart';
import '../core/models.dart';
import '../core/sales_order_drafts.dart';
import '../core/suite_read_cache.dart';
import 'notes_page.dart';
import 'crm_lead_page.dart';
import 'crm_contact_page.dart';
import 'crm_cpq_evaluator.dart';
import 'crm_guided_selling_form.dart';
import 'crm_pipeline_page.dart';
import 'inventory_batch_page.dart';
import 'inventory_finance_report_page.dart';
import 'inventory_procurement_page.dart';
import 'inventory_purchase_order_form.dart';
import 'inventory_tracking_form.dart';
import 'crm_customer_page.dart';
import 'crm_quotation_page.dart';
import 'crm_task_page.dart';
import 'crm_deal_page.dart';
import 'crm_follow_ups_page.dart';
import 'crm_new_lead_page.dart';
import 'sales_order_page.dart';
import 'sales_contract_page.dart';
import 'sales_engagement_page.dart';
import 'payment_requests_page.dart';
import 'sales_billing_plan_page.dart';
import 'sales_order_drafts_page.dart';
import 'inventory_drafts_page.dart';
import 'suite_notifications_page.dart';
import 'account_settings_panel.dart';
import 'company_profile_panel.dart';
import 'business_defaults_panel.dart';
import 'branch_settings_panel.dart';
import 'lead_sources_panel.dart';
import 'starter_values_panel.dart';
import 'gst_invoice_page.dart';
import 'gst_collections_page.dart';
import 'appointment_booking_page.dart';
import 'my_attendance_page.dart';
import 'my_leave_page.dart';
import 'my_payslips_page.dart';
import 'my_roster_page.dart';
import 'my_timesheets_page.dart';
import 'finance_party_page.dart';
import 'finance_chart_page.dart';
import 'finance_vouchers_page.dart';
import 'power_environment_page.dart';
import '../core/notes_offline_cache.dart';
import 'workspace_page.dart';
import 'inventory_stock_movement_page.dart';
import 'inventory_warehouse_form.dart';

typedef _App = ({
  String key,
  String grant,
  String title,
  String caption,
  IconData icon,
  Color color,
  String? endpoint,
});

const List<_App> _apps = [
  (
    key: 'appointments',
    grant: 'srm',
    title: 'Appointments',
    caption: 'Bookings & schedule',
    icon: LucideIcons.calendarDays,
    color: Color(0xff965831),
    endpoint: '/srm/industry/records',
  ),
  (
    key: 'power_apps',
    grant: 'power_apps',
    title: 'Power Apps',
    caption: 'Build & automate',
    icon: LucideIcons.zap,
    color: Color(0xff7638c8),
    endpoint: PowerEnvironmentPage.endpoint,
  ),
  (
    key: 'hrms',
    grant: 'hrms',
    title: 'AI HRMS',
    caption: 'People & payroll',
    icon: LucideIcons.users,
    color: Color(0xff2964c2),
    endpoint: '/employees/',
  ),
  (
    key: 'crm',
    grant: 'crm',
    title: 'VyaparaCRM',
    caption: 'Leads & customers',
    icon: LucideIcons.users,
    color: Color(0xff087c68),
    endpoint: CrmLeadPage.endpoint,
  ),
  (
    key: 'pms',
    grant: 'project_management',
    title: 'KaryaFlow PMS',
    caption: 'Projects & tasks',
    icon: LucideIcons.listChecks,
    color: Color(0xff6145ce),
    endpoint: null,
  ),
  (
    key: 'srm',
    grant: 'srm',
    title: 'Sales & POS',
    caption: 'Sales & inventory',
    icon: LucideIcons.shoppingCart,
    color: Color(0xffc25448),
    endpoint: '/srm/sales-orders',
  ),
  (
    key: 'fam',
    grant: 'fam',
    title: 'Finance & Accounting',
    caption: 'Accounts & ledgers',
    icon: LucideIcons.chartNoAxesColumnIncreasing,
    color: Color(0xff6244c6),
    endpoint: FinancePartyPage.endpoint,
  ),
];

class SuiteDashboard extends StatefulWidget {
  const SuiteDashboard({super.key, required this.controller});
  final AppController controller;

  @override
  State<SuiteDashboard> createState() => _SuiteDashboardState();
}

class _SuiteDashboardState extends State<SuiteDashboard> {
  static const _preferencesPath = '/access/launcher-preferences';
  late Future<Json> _access = _load();
  List<String>? _favorites;
  bool _favoritesOnly = false;
  bool _savingFavorites = false;
  int _favoritesRequest = 0;
  String _query = '';
  Timer? _syncTimer;
  AppLifecycleListener? _lifecycle;
  bool _syncing = false;
  int _unreadNotifications = 0;
  int _notificationRequest = 0;

  String? _favoritesCacheKey(Json access) {
    final scope = _localScope(access);
    return scope == null ? null : '$scope:$_preferencesPath';
  }

  Future<void> _cacheFavorites(String? key, List<String> favorites) async {
    if (key == null) return;
    try {
      await SuiteReadCache.write(key, [
        {'favorites': favorites},
      ]);
    } catch (_) {
      // The server preferences remain available if the cache cannot write.
    }
  }

  Future<void> _refreshFavorites() async {
    final controller = widget.controller;
    if (_savingFavorites) return;
    final api = controller.api;
    final session = api.sessionRevision;
    final request = ++_favoritesRequest;
    bool current() =>
        mounted &&
        request == _favoritesRequest &&
        session == api.sessionRevision;
    String? key;
    try {
      final access = await _access;
      if (!current()) return;
      key = _favoritesCacheKey(access);
      if (key != null && _favorites == null) {
        try {
          final saved = await SuiteReadCache.read(key);
          final favorites = saved?.firstOrNull?['favorites'];
          if (current() && favorites is List) {
            setState(() => _favorites = favorites.whereType<String>().toList());
          }
        } catch (_) {
          // Continue to the server when the cache is unavailable.
        }
      }
      if (!current() || controller.offline) return;
      final data = await api.request('GET', _preferencesPath) as Json;
      if (!current()) return;
      final favorites =
          (data['favorites'] as List?)?.whereType<String>().toList() ?? [];
      setState(() => _favorites = favorites);
      await _cacheFavorites(key, favorites);
    } on ApiFailure catch (error) {
      if (current() && (error.status == 401 || error.status == 403)) {
        setState(() {
          _favorites = null;
          _favoritesOnly = false;
        });
        if (key != null) await _cacheFavorites(key, []);
      }
    } catch (_) {
      // Favorites remain optional when the shared preferences API is unavailable.
    }
  }

  Future<void> _toggleFavorite(String key) async {
    final favorites = _favorites;
    if (favorites == null || _savingFavorites || widget.controller.offline) {
      return;
    }
    final api = widget.controller.api;
    final session = api.sessionRevision;
    final next = [...favorites];
    if (!next.remove(key)) next.add(key);
    _favoritesRequest++;
    setState(() => _savingFavorites = true);
    try {
      final result =
          await api.request('PUT', _preferencesPath, data: {'favorites': next})
              as Json;
      if (!mounted || session != api.sessionRevision) return;
      final saved = (result['favorites'] as List).whereType<String>().toList();
      setState(() => _favorites = saved);
      final access = await _access;
      if (mounted && session == api.sessionRevision) {
        await _cacheFavorites(_favoritesCacheKey(access), saved);
      }
    } catch (_) {
      if (mounted && session == api.sessionRevision) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not save your favorites.')),
        );
      }
    } finally {
      if (mounted) setState(() => _savingFavorites = false);
    }
  }

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
    _refreshFavorites();
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      _syncTimer = Timer.periodic(
        const Duration(seconds: 20),
        (_) => _syncEdits(_access),
      );
      _lifecycle = AppLifecycleListener(
        onResume: () {
          _syncEdits(_access);
          _refreshUnread();
          _refreshFavorites();
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
          revision != controller.api.sessionRevision) {
        return;
      }
      final scope = _localScope(access);
      if (scope == null) return;
      final edits = CrmOfflineEdits.withTaskSnapshots(scope);
      if (_allowed(access, 'crm') &&
          await edits.hasPending &&
          mounted &&
          identical(_access, accessFuture) &&
          revision == controller.api.sessionRevision) {
        await edits.sync(controller.api);
      }
      if (_allowed(access, 'srm') &&
          mounted &&
          identical(_access, accessFuture) &&
          revision == controller.api.sessionRevision) {
        await InventoryOfflineCreates(
          scope,
          invalidate: SuiteReadCache.invalidate,
        ).sync(controller.api);
        if (mounted &&
            identical(_access, accessFuture) &&
            revision == controller.api.sessionRevision) {
          await InventoryStockReceipts(scope).sync(controller.api);
        }
        if (mounted &&
            identical(_access, accessFuture) &&
            revision == controller.api.sessionRevision &&
            _canCreateInvoice(access)) {
          await SalesOrderDrafts.gstInvoices(
            scope,
            invalidate: SuiteReadCache.invalidate,
          ).sync(controller.api);
        }
        if (mounted &&
            identical(_access, accessFuture) &&
            revision == controller.api.sessionRevision &&
            _canCreateOrder(access)) {
          await SalesOrderDrafts(
            scope,
            invalidate: SuiteReadCache.invalidate,
          ).sync(controller.api);
          if (mounted &&
              identical(_access, accessFuture) &&
              revision == controller.api.sessionRevision) {
            await SalesOrderDrafts.purchaseOrders(
              scope,
              invalidate: SuiteReadCache.invalidate,
            ).sync(controller.api);
          }
        }
      }
      if (_allowed(access, 'project_management') &&
          mounted &&
          identical(_access, accessFuture) &&
          revision == controller.api.sessionRevision) {
        await NotesOfflineCache(scope).sync(controller.api);
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
          {'id': user.id, 'email': user.email, 'employee_id': user.employeeId},
          {
            'companyId': access['companyId'],
            'companyName': access['companyName'],
            'canCreateLead': _canCreateLead(access),
            'canCreateOrder': _canCreateOrder(access),
            'canEditInventoryProducts': _canWriteSales(access, 'edit'),
            'canCreateInvoice': _canCreateInvoice(access),
            'grants': {
              for (final key in [
                'crm',
                'srm',
                'fam',
                'hrms',
                'project_management',
              ])
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

  bool _canCreateLead(Json access) {
    if (!_allowed(access, 'crm')) return false;
    final controller = widget.controller;
    if (controller.offline) return access['canCreateLead'] == true;
    final crm = (access['grants'] as Json?)?['crm'] as Json?;
    const permissions = {'crm_manage', 'crm_admin', 'crm_leads_manage'};
    return controller.user?.isSuperuser == true ||
        (access['managed'] == true
            ? (crm?['actions'] as List?)?.contains('create') == true &&
                  (crm?['permissions'] as List?)?.any(permissions.contains) ==
                      true
            : controller.user?.permissions.any(permissions.contains) == true);
  }

  bool _canWriteCrm(Json access, String action, Set<String> permissions) {
    if (!_allowed(access, 'crm') || widget.controller.offline) return false;
    final user = widget.controller.user;
    if (user?.isSuperuser == true) return true;
    if (access['managed'] != true) {
      return user?.permissions.any(permissions.contains) == true;
    }
    final grant = (access['grants'] as Json?)?['crm'] as Json?;
    return (grant?['actions'] as List?)?.contains(action) == true &&
        (grant?['permissions'] as List?)?.any(permissions.contains) == true;
  }

  bool _canCreateOrder(Json access) => _canWriteSales(access, 'create');

  bool _canCreateInvoice(Json access) {
    if (!_allowed(access, 'srm')) return false;
    if (widget.controller.offline) return access['canCreateInvoice'] == true;
    final user = widget.controller.user;
    if (user?.isSuperuser == true) return true;
    const permissions = {'srm_invoice_create', 'srm_admin'};
    final grant = (access['grants'] as Json?)?['srm'] as Json?;
    return access['managed'] == true
        ? (grant?['actions'] as List?)?.contains('create') == true &&
              (grant?['permissions'] as List?)?.any(permissions.contains) ==
                  true
        : user?.permissions.any(permissions.contains) == true ||
              (grant?['permissions'] as List?)?.any(permissions.contains) ==
                  true;
  }

  bool _canWriteSales(Json access, String action) {
    if (!_allowed(access, 'srm')) return false;
    final controller = widget.controller;
    if (controller.offline) {
      return switch (action) {
        'create' => access['canCreateOrder'] == true,
        'edit' => access['canEditInventoryProducts'] == true,
        _ => false,
      };
    }
    final grant = (access['grants'] as Json?)?['srm'] as Json?;
    const permissions = {'srm_manage', 'srm_admin'};
    return controller.user?.isSuperuser == true ||
        (access['managed'] == true
            ? (grant?['actions'] as List?)?.contains(action) == true &&
                  (grant?['permissions'] as List?)?.any(permissions.contains) ==
                      true
            : controller.user?.permissions.any(permissions.contains) == true);
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
              : WorkspacePage(
                  controller: controller,
                  notesCacheScope: _localScope(access),
                ),
        ),
      );
      final workspace = controller.selected;
      if (workspace != null && controller.overview == null) {
        controller.selectWorkspace(workspace);
      }
      return;
    }
    final cache =
        app.grant == 'crm' ||
            app.title == 'Sales & POS' ||
            app.endpoint == FinancePartyPage.endpoint
        ? _localScope(access)
        : null;
    final grant = (access['grants'] as Json?)?['srm'] as Json?;
    bool allowsSalesAction(String action) =>
        app.title == 'Sales & POS' &&
        (controller.user?.isSuperuser == true ||
            access['managed'] != true ||
            (grant?['actions'] as List?)?.contains(action) == true);
    final finance = (access['grants'] as Json?)?['fam'] as Json?;
    bool allowsVoucherAction(String permission, String action) {
      final permissions = {'fam_admin', permission};
      return app.grant == 'fam' &&
          !controller.offline &&
          (controller.user?.isSuperuser == true ||
              (access['managed'] == true
                  ? (finance?['actions'] as List?)?.contains(action) == true &&
                        (finance?['permissions'] as List?)?.any(
                              permissions.contains,
                            ) ==
                            true
                  : controller.user?.permissions.any(permissions.contains) ==
                        true));
    }

    final hr = (access['grants'] as Json?)?['hrms'] as Json?;
    final canCreateTimesheets =
        controller.user?.isSuperuser == true ||
        access['managed'] != true ||
        ((hr?['permissions'] as List?)?.contains('timesheet_view') == true &&
            (hr?['actions'] as List?)?.contains('create') == true);
    _push(
      _SuiteRecords(
        title: app.title,
        controller: controller,
        path: app.endpoint,
        canViewFinanceInventory: _allowed(access, 'fam'),
        canPostVoucher: allowsVoucherAction('fam_vouchers_post', 'approve'),
        canCreateVoucher: allowsVoucherAction('fam_vouchers_create', 'create'),
        canEditVoucher: allowsVoucherAction('fam_vouchers_create', 'edit'),
        canCancelVoucher: allowsVoucherAction('fam_vouchers_cancel', 'create'),
        canReverseVoucher: allowsVoucherAction(
          'fam_vouchers_reverse',
          'create',
        ),
        query:
            app.title == 'Sales & POS' ||
                app.grant == 'crm' ||
                app.endpoint == FinancePartyPage.endpoint
            ? const {'summary_only': true}
            : const {},
        cachePrefix: cache,
        employeeCacheScope: app.grant == 'hrms' ? _localScope(access) : null,
        canCreateTimesheets: canCreateTimesheets,
        canCreateLead: app.grant == 'crm' && _canCreateLead(access),
        canCreateFollowUps:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'create', const {
              'crm_manage',
              'crm_admin',
              'crm_activities_manage',
            }),
        canEditFollowUps:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'edit', const {
              'crm_manage',
              'crm_admin',
              'crm_activities_manage',
            }),
        canAssignFollowUps:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'assign', const {
              'crm_manage',
              'crm_admin',
              'crm_activities_manage',
            }),
        canCreateContacts:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'create', const {
              'crm_contacts_manage',
              'crm_manage',
              'crm_admin',
            }),
        canEditContacts:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'edit', const {
              'crm_contacts_manage',
              'crm_manage',
              'crm_admin',
            }),
        canCreateDeals:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'create', const {
              'crm_deals_manage',
              'crm_manage',
              'crm_admin',
            }),
        canManageQuotes:
            app.grant == 'crm' &&
            ['manage', 'edit', 'create'].any(
              (action) => _canWriteCrm(access, action, const {
                'crm_quotes_manage',
                'crm_manage',
                'crm_admin',
              }),
            ),
        canViewQuoteSalesOrders: app.grant == 'crm' && _allowed(access, 'srm'),
        canCreateGuidedFlow:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'create', const {
              'crm_cpq_manage',
              'crm_manage',
              'crm_admin',
            }),
        canEditGuidedFlow:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'edit', const {
              'crm_cpq_manage',
              'crm_manage',
              'crm_admin',
            }),
        canCancelQuotes:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'edit', const {
              'crm_quotes_manage',
              'crm_manage',
              'crm_admin',
            }),
        canCreateQuotes:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'create', const {
              'crm_quotes_manage',
              'crm_manage',
              'crm_admin',
            }),
        canApproveQuotes:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'approve', const {
              'crm_quotes_approve',
              'crm_manage',
              'crm_admin',
            }),
        canSendQuotes:
            app.grant == 'crm' &&
            ['send', 'manage', 'edit'].any(
              (action) => _canWriteCrm(access, action, const {
                'crm_quotes_send',
                'crm_manage',
                'crm_admin',
              }),
            ),
        canMoveDeals:
            app.grant == 'crm' &&
            _canWriteCrm(access, 'edit', const {
              'crm_deals_manage',
              'crm_manage',
              'crm_admin',
            }),
        canCreateOrder: app.title == 'Sales & POS' && _canCreateOrder(access),
        canEditWarehouses:
            app.title == 'Sales & POS' && _canWriteSales(access, 'edit'),
        showInventory: app.title == 'Sales & POS',
        canEditOrders: allowsSalesAction('edit'),
        canEditInventoryProducts:
            app.title == 'Sales & POS' && _canWriteSales(access, 'edit'),
        canArchiveOrders:
            app.title == 'Sales & POS' && _canWriteSales(access, 'delete'),
        canCreateOrderInvoices:
            app.title == 'Sales & POS' && _canCreateInvoice(access),
        canExportSalesDocuments: allowsSalesAction('export'),
        canViewCollections:
            app.title == 'Sales & POS' &&
            (controller.user?.isSuperuser == true ||
                (grant?['permissions'] as List?)?.any(
                      const {
                        'srm_collection_view',
                        'srm_collection_create',
                        'srm_admin',
                      }.contains,
                    ) ==
                    true ||
                (access['managed'] != true &&
                    controller.user?.permissions.any(
                          const {
                            'srm_collection_view',
                            'srm_collection_create',
                            'srm_admin',
                          }.contains,
                        ) ==
                        true)),
        canIssueInvoices:
            allowsSalesAction('approve') &&
            (controller.user?.isSuperuser == true ||
                (grant?['permissions'] as List?)?.any(
                      const {'srm_invoice_approve', 'srm_admin'}.contains,
                    ) ==
                    true ||
                (access['managed'] != true &&
                    controller.user?.permissions.any(
                          const {'srm_invoice_approve', 'srm_admin'}.contains,
                        ) ==
                        true)),
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
                  onPressed: () {
                    setState(() {
                      _access = _load();
                    });
                    _refreshFavorites();
                  },
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
                  !widget.controller.offline ||
                  (app.title != 'Appointments' &&
                      app.grant != 'project_management'),
            )
            .toList();
        final favoriteKeys = _favorites ?? const <String>[];
        final byKey = {for (final app in allowed) app.key: app};
        final ordered = [
          for (final key in favoriteKeys) ?byKey[key],
          if (!_favoritesOnly)
            ...allowed.where((app) => !favoriteKeys.contains(app.key)),
        ];
        final shown = ordered
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
              await _refreshFavorites();
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
              if (_favorites != null) ...[
                SegmentedButton<bool>(
                  segments: [
                    const ButtonSegment(
                      value: false,
                      label: Text('All applications'),
                    ),
                    ButtonSegment(
                      value: true,
                      label: Text(
                        'Favorites (${allowed.where((app) => _favorites!.contains(app.key)).length})',
                      ),
                      icon: const Icon(LucideIcons.star),
                    ),
                  ],
                  selected: {_favoritesOnly},
                  onSelectionChanged: (value) => setState(() {
                    _favoritesOnly = value.single;
                  }),
                ),
                const SizedBox(height: 10),
              ],
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisExtent: _favorites == null ? 126 : 144,
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
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Icon(app.icon, color: app.color),
                                if (_favorites != null)
                                  IconButton(
                                    visualDensity: VisualDensity.compact,
                                    padding: EdgeInsets.zero,
                                    constraints: const BoxConstraints.tightFor(
                                      width: 42,
                                      height: 32,
                                    ),
                                    tooltip: _favorites!.contains(app.key)
                                        ? 'Remove ${app.title} from favorites'
                                        : 'Add ${app.title} to favorites',
                                    onPressed:
                                        _savingFavorites ||
                                            widget.controller.offline
                                        ? null
                                        : () => _toggleFavorite(app.key),
                                    icon: Icon(
                                      _favorites!.contains(app.key)
                                          ? Icons.star
                                          : LucideIcons.star,
                                      size: 18,
                                    ),
                                  ),
                              ],
                            ),
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
                  onTap: () {
                    final scope = _localScope(access);
                    _push(
                      NotesPage(
                        api: widget.controller.api,
                        cache: scope == null ? null : NotesOfflineCache(scope),
                        offline: widget.controller.offline,
                      ),
                    );
                  },
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
        if (widget.id == 'company-profile') {
          return CompanyProfilePanel(api: widget.controller.api);
        }
        if (widget.id == 'business-defaults') {
          return BusinessDefaultsPanel(
            api: widget.controller.api,
            editable: data['editable'] == true,
          );
        }
        if (widget.id == 'branches') {
          return BranchSettingsPanel(
            api: widget.controller.api,
            editable: data['editable'] == true,
            actorId: widget.controller.user?.id,
          );
        }
        if (widget.id == 'crm-lead-sources') {
          return LeadSourcesPanel(
            api: widget.controller.api,
            editable: data['editable'] == true,
          );
        }
        if (widget.id == 'starter-values') {
          return StarterValuesPanel(
            api: widget.controller.api,
            editable: data['editable'] == true,
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
                      canCreateAppointment: branch['can_write'] == true,
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

class _AppointmentDetails extends StatefulWidget {
  const _AppointmentDetails({
    required this.controller,
    required this.id,
    required this.scopeHeaders,
    required this.onChanged,
  });

  final AppController controller;
  final int id;
  final Map<String, String> scopeHeaders;
  final VoidCallback onChanged;

  @override
  State<_AppointmentDetails> createState() => _AppointmentDetailsState();
}

class _AppointmentDetailsState extends State<_AppointmentDetails> {
  static const _actions = {
    'checked_in': ('check_in', 'Check in'),
    'in_service': ('start', 'Start service'),
    'completed': ('complete', 'Complete'),
    'cancelled': ('cancel', 'Cancel appointment'),
    'no_show': ('no_show', 'Record no-show'),
  };

  late Future<dynamic> _details = _load();
  late final Future<Json?> _capabilities = _loadCapabilities();
  bool _saving = false;
  String? _error;

  Future<Json?> _loadCapabilities() async {
    try {
      final result = await widget.controller.api.request(
        'GET',
        '/srm/industry/capabilities',
        scopeHeaders: widget.scopeHeaders,
      );
      return result is Json ? result : null;
    } on ApiFailure {
      return null;
    }
  }

  Future<void> _transition(int revision, String status, String label) async {
    if (_saving) return;
    String? reason = '';
    if (status == 'cancelled' || status == 'no_show') {
      var input = '';
      reason = await showDialog<String>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(label),
          content: TextField(
            autofocus: true,
            decoration: const InputDecoration(labelText: 'Reason'),
            onChanged: (text) => input = text.trim(),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Back'),
            ),
            FilledButton(
              onPressed: () {
                if (input.isNotEmpty) Navigator.pop(context, input);
              },
              child: const Text('Confirm'),
            ),
          ],
        ),
      );
    }
    if (!mounted || reason == null || _saving) return;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final updated = await widget.controller.api.request(
        'POST',
        '/srm/industry/records/${widget.id}/transition',
        data: {
          'expected_revision': revision,
          'status': status,
          'reason': reason,
        },
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted) return;
      widget.onChanged();
      setState(() {
        _details = Future.value(updated);
      });
    } on ApiFailure catch (error) {
      if (mounted) {
        setState(() {
          _error = error.toString();
          if (error.status == 409) _details = _load();
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<dynamic> _load() => widget.controller.api.request(
    'GET',
    '/srm/industry/appointments/${widget.id}',
    scopeHeaders: widget.scopeHeaders,
  );

  Future<void> _reschedule(int revision, Json data) async {
    final api = widget.controller.api;
    final session = api.sessionRevision;
    final current = DateTime.tryParse('${data['starts_at']}')?.toLocal();
    if (_saving || current == null) return;
    final now = DateTime.now();
    final today = DateUtils.dateOnly(now);
    final lastDay = today.add(const Duration(days: 3650));
    final day = await showDatePicker(
      context: context,
      initialDate: current.isBefore(now)
          ? today
          : current.isAfter(lastDay)
          ? lastDay
          : current,
      firstDate: today,
      lastDate: lastDay,
    );
    if (!mounted || day == null) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(current),
      helpText: 'New start time · device time zone',
    );
    if (!mounted || time == null || api.sessionRevision != session) return;
    final start = DateTime(
      day.year,
      day.month,
      day.day,
      time.hour,
      time.minute,
    );
    if (!start.isAfter(DateTime.now())) {
      setState(() => _error = 'Choose a future start time.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await api.request(
        'PUT',
        '/srm/industry/appointments/${widget.id}/schedule',
        data: {
          'expected_revision': revision,
          'starts_at': start.toUtc().toIso8601String(),
          'duration_minutes': data['duration_minutes'],
          'resource_ids': data['resource_ids'],
        },
        scopeHeaders: widget.scopeHeaders,
      );
      if (!mounted || api.sessionRevision != session) return;
      widget.onChanged();
      setState(() {
        _details = _load();
      });
    } on ApiFailure catch (error) {
      if (mounted) {
        setState(() {
          _error = error.toString();
          if (error.status == 409 || error.connectionFailure) {
            _details = _load();
          }
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _time(BuildContext context, Object value) {
    final date = DateTime.tryParse('$value')?.toLocal();
    if (date == null) return '$value';
    final labels = MaterialLocalizations.of(context);
    return '${labels.formatMediumDate(date)} · '
        '${labels.formatTimeOfDay(TimeOfDay.fromDateTime(date))}';
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Appointment')),
    body: FutureBuilder(
      future: _details,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        final appointment = snapshot.data;
        if (appointment is! Json) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Could not load this appointment.'),
                TextButton(
                  onPressed: () => setState(() {
                    _details = _load();
                  }),
                  child: const Text('Retry'),
                ),
              ],
            ),
          );
        }
        final rawData = appointment['data'];
        final data = rawData is Json ? rawData : <String, dynamic>{};
        final start = DateTime.tryParse('${data['starts_at']}');
        final duration = data['duration_minutes'];
        final revision = appointment['revision'];
        final next = switch (appointment['status']) {
          'booked' => ['checked_in', 'cancelled', 'no_show'],
          'checked_in' => ['in_service', 'cancelled'],
          'in_service' => ['completed'],
          _ => <String>[],
        };
        final fields = <String, Object?>{
          'Status': appointment['status']?.toString().replaceAll('_', ' '),
          'Customer': data['customer_name'],
          'Service': data['service_name'],
          'Starts': data['starts_at'],
          'Ends':
              data['ends_at'] ??
              (start != null && duration is int
                  ? start.add(Duration(minutes: duration)).toIso8601String()
                  : null),
        };
        return ListView(
          children: [
            ListTile(
              title: Text(
                appointment['title']?.toString() ?? 'Appointment',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            for (final field in fields.entries)
              if (field.value case final Object value)
                ListTile(
                  title: Text(field.key),
                  subtitle: Text(
                    field.key == 'Starts' || field.key == 'Ends'
                        ? _time(context, value)
                        : '$value',
                  ),
                ),
            if (_error case final String message)
              ListTile(title: Text(message)),
            if (revision is int && next.isNotEmpty)
              FutureBuilder<Json?>(
                future: _capabilities,
                builder: (context, snapshot) {
                  final caps = snapshot.data;
                  final allowed = caps?['appointment_actions'];
                  return Padding(
                    padding: const EdgeInsets.all(16),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        if (appointment['status'] == 'booked' &&
                            data['duration_minutes'] is int &&
                            data['resource_ids'] is List &&
                            (allowed is List
                                ? allowed.contains('schedule')
                                : caps?['manage'] == true))
                          OutlinedButton(
                            onPressed: _saving
                                ? null
                                : () async {
                                    if (data['pos_checkout_id'] == null) {
                                      await _reschedule(revision, data);
                                      return;
                                    }
                                    final moved = await Navigator.of(context)
                                        .push<Json>(
                                          MaterialPageRoute(
                                            builder: (_) =>
                                                AppointmentBookingPage(
                                                  api: widget.controller.api,
                                                  headers: widget.scopeHeaders,
                                                  linkedAppointmentId:
                                                      widget.id,
                                                ),
                                          ),
                                        );
                                    if (!mounted || moved == null) return;
                                    widget.onChanged();
                                    setState(() {
                                      _details = Future.value(moved);
                                    });
                                  },
                            child: const Text('Reschedule'),
                          ),
                        for (final status in next)
                          if (_actions[status] case (
                            final permission,
                            final label,
                          ))
                            if (allowed is List
                                ? allowed.contains(permission)
                                : caps?['manage'] == true)
                              OutlinedButton(
                                onPressed:
                                    _saving ||
                                        (status == 'no_show' &&
                                            (start == null ||
                                                start.isAfter(DateTime.now())))
                                    ? null
                                    : () =>
                                          _transition(revision, status, label),
                                child: Text(label),
                              ),
                      ],
                    ),
                  );
                },
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
    this.canCreateAppointment = false,
    this.cachePrefix,
    this.employeeCacheScope,
    this.canCreateTimesheets = false,
    this.showInventory = false,
    this.canViewFinanceInventory = false,
    this.canPostVoucher = false,
    this.canCreateVoucher = false,
    this.canEditVoucher = false,
    this.canCancelVoucher = false,
    this.canReverseVoucher = false,
    this.canExportSalesDocuments = false,
    this.canIssueInvoices = false,
    this.canViewCollections = false,
    this.canEditOrders = false,
    this.canEditInventoryProducts = false,
    this.canArchiveOrders = false,
    this.canEditWarehouses = false,
    this.canCreateLead = false,
    this.canEditFollowUps = false,
    this.canAssignFollowUps = false,
    this.canCreateFollowUps = false,
    this.canCreateContacts = false,
    this.canEditContacts = false,
    this.canMoveDeals = false,
    this.canCreateDeals = false,
    this.canManageQuotes = false,
    this.canCreateGuidedFlow = false,
    this.canEditGuidedFlow = false,
    this.canCancelQuotes = false,
    this.canCreateQuotes = false,
    this.canViewQuoteSalesOrders = false,
    this.canApproveQuotes = false,
    this.canSendQuotes = false,
    this.canCreateOrder = false,
    this.canCreateOrderInvoices = false,
    this.offlineOnly = false,
  });
  final String title;
  final AppController controller;
  final String? path, collection;
  final Map<String, dynamic> query;
  final Map<String, String> scopeHeaders;
  final bool canCreateAppointment;
  final String? cachePrefix;
  final String? employeeCacheScope;
  final bool canCreateTimesheets;
  final bool showInventory;
  final bool canViewFinanceInventory;
  final bool canPostVoucher;
  final bool canCreateVoucher;
  final bool canEditVoucher;
  final bool canCancelVoucher, canReverseVoucher;
  final bool canExportSalesDocuments;
  final bool canIssueInvoices;
  final bool canViewCollections;
  final bool canEditOrders;
  final bool canEditInventoryProducts;
  final bool canArchiveOrders;
  final bool canEditWarehouses;
  final bool canCreateLead;
  final bool canEditFollowUps, canAssignFollowUps, canCreateFollowUps;
  final bool canCreateContacts;
  final bool canEditContacts;
  final bool canMoveDeals;
  final bool canCreateDeals;
  final bool canManageQuotes;
  final bool canCreateGuidedFlow;
  final bool canEditGuidedFlow;
  final bool canCancelQuotes;
  final bool canCreateQuotes;
  final bool canViewQuoteSalesOrders;
  final bool canApproveQuotes;
  final bool canSendQuotes;
  final bool canCreateOrder;
  final bool canCreateOrderInvoices;
  final bool offlineOnly;

  @override
  State<_SuiteRecords> createState() => _SuiteRecordsState();
}

class _SuiteRecordsState extends State<_SuiteRecords> {
  bool get _appointments => widget.query['kind'] == 'appointment';
  late final _appointmentCapabilities = widget.controller.api.request(
    'GET',
    '/srm/industry/capabilities',
    scopeHeaders: widget.scopeHeaders,
  );
  String _appointmentStatus = '';
  DateTime? _appointmentDay;
  bool _appointmentWeek = false;

  void _moveAppointmentDay(int days) {
    final day = _appointmentDay ?? DateTime.now();
    final step = _appointmentWeek ? days * 7 : days;
    _setAppointmentDay(DateTime(day.year, day.month, day.day + step));
  }

  Future<void> _pickAppointmentDay() async {
    final day = await showDatePicker(
      context: context,
      initialDate: _appointmentDay ?? DateTime.now(),
      firstDate: DateTime(1900),
      lastDate: DateTime(2200),
      helpText: 'Schedule date · device time zone',
    );
    if (!mounted || day == null) return;
    _setAppointmentDay(day);
  }

  void _setAppointmentDay(DateTime? day, {bool? week}) {
    setState(() {
      _appointmentDay = day;
      _appointmentWeek = day != null && (week ?? _appointmentWeek);
      _records = _startLoad();
    });
  }

  static const _reorderPath = InventoryStockReceipts.reorderEndpoint;
  static const _stockSummaryPath = InventoryStockReceipts.stockSummaryEndpoint;
  bool get _stockSummary => widget.path == _stockSummaryPath;
  static const _warehousesPath = InventoryWarehouseForm.endpoint;
  static const _warehouseStockPath =
      InventoryStockReceipts.warehouseStockEndpoint;
  bool get _warehouses => widget.path == _warehousesPath;
  bool get _warehouseStock => widget.path == _warehouseStockPath;
  static const _valuationPath = InventoryStockReceipts.valuationEndpoint;
  bool get _valuation => widget.path == _valuationPath;
  bool get _activityReport =>
      InventoryStockReceipts.activityReports.containsKey(widget.path);
  bool get _stockAlerts => widget.path == _reorderPath;
  bool get _inventory => widget.path == InventoryOfflineCreates.itemsEndpoint;

  num? _stockNumber(Object? value) =>
      value is num ? value : num.tryParse('${value ?? ''}');

  bool _lowStock(Json row) {
    final threshold = _stockNumber(row['reorder_threshold']);
    final quantity = _stockNumber(row['current_quantity']);
    return threshold != null &&
        threshold > 0 &&
        quantity != null &&
        quantity <= threshold;
  }

  CrmOfflineEdits? get _crmEdits {
    final scope = widget.cachePrefix;
    return widget.path == CrmLeadPage.endpoint && scope != null
        ? CrmOfflineEdits(scope)
        : null;
  }

  String _term = '';
  String _serverSearch = '';
  int _page = 1;
  bool _hasNextPage = false;
  bool _customerCreateAllowed = false;
  Set<int> _editableTaskProjects = {};
  int _loadRevision = 0;
  Timer? _searchDebounce;
  bool get _isCrm => widget.path == CrmLeadPage.endpoint;
  bool get _crmContacts => widget.path == CrmContactPage.endpoint;
  bool get _crmDeals => widget.path == CrmDealPage.endpoint;
  bool get _crmCustomers => widget.path == CrmCustomerPage.endpoint;
  bool get _crmTasks => widget.path == CrmTaskPage.endpoint;
  bool get _crmQuotations => widget.path == CrmQuotationPage.endpoint;
  static const _quoteApprovalsPath = '/crm/quote-approvals';
  static const _cpqPath = '/crm/cpq-rules';
  bool get _crmCpq => widget.path == _cpqPath;
  bool get _crmGuidedSelling => widget.path == CrmGuidedSellingForm.endpoint;
  bool get _crmQuoteApprovals => widget.path == _quoteApprovalsPath;
  static const _approvalFields = [
    'quote_id',
    'reason',
    'comments',
    'approver_user_id',
    'approved_by',
    'submitted_at',
    'decided_at',
  ];
  bool get _batchTracking => widget.path == InventoryBatchPage.batches;
  bool get _serialTracking => widget.path == InventoryBatchPage.serials;
  ProcurementRecord? get _procurement => switch (widget.path) {
    '/srm/procurement/purchase-orders' ||
    _archivedOrdersPath => ProcurementRecord.order,
    '/srm/procurement/grn' => ProcurementRecord.receipt,
    _ => null,
  };
  static const _archivedOrdersPath = '/srm/documents/purchase-orders';
  bool get _archivedOrders => widget.path == _archivedOrdersPath;
  bool get _cachePagedRecords =>
      _isCrm ||
      _crmContacts ||
      _crmDeals ||
      _crmCustomers ||
      _crmTasks ||
      _crmQuotations ||
      _crmQuoteApprovals ||
      _crmCpq ||
      _crmGuidedSelling ||
      _batchTracking ||
      _procurement == ProcurementRecord.order;
  bool get _isEmployees => widget.path == '/employees/';
  bool get _hasPages => _cachePagedRecords || _isEmployees;
  bool get _searchOnServer =>
      _hasPages ||
      _inventory ||
      widget.path == '/srm/sales-orders' ||
      widget.path == GstInvoicePage.listEndpoint;
  late bool _offlineOnly = widget.offlineOnly;
  late Future<List<Json>> _records = _startLoad();
  List<Json>? _cached;
  ApiFailure? _accessDenied;
  bool _usedSavedFallback = false;
  late final SalesOrderDrafts? _saleDrafts =
      widget.showInventory && widget.cachePrefix != null
      ? SalesOrderDrafts(
          widget.cachePrefix!,
          invalidate: SuiteReadCache.invalidate,
        )
      : null;
  late final InventoryOfflineCreates? _inventoryDrafts =
      _inventory && widget.cachePrefix != null
      ? InventoryOfflineCreates(
          widget.cachePrefix!,
          invalidate: SuiteReadCache.invalidate,
        )
      : null;
  bool _branchesPrepared = false;

  Future<void> _prepareInventoryDrafts() async {
    final drafts = _inventoryDrafts;
    if (drafts == null || _branchesPrepared) return;
    _branchesPrepared = true;
    try {
      await drafts.writableBranches(widget.controller.api);
    } catch (_) {
      _branchesPrepared = false;
    }
  }

  String? get _cacheKey => widget.path == SalesContractPage.endpoint
      ? switch (widget.cachePrefix) {
          final String scope => SalesContractPage.listCacheKey(
            scope,
            widget.scopeHeaders,
          ),
          _ => null,
        }
      : (widget.path == SalesEngagementPage.endpoint ||
                widget.path == SalesBillingPlanPage.endpoint) &&
            widget.cachePrefix != null
      ? "${widget.cachePrefix}:${widget.path}:${widget.scopeHeaders['X-Suite-Branch'] ?? ''}"
      : widget.path == GstInvoicePage.listEndpoint
      ? GstInvoicePage.cacheKey(
          widget.cachePrefix,
          GstInvoicePage.listEndpoint,
          widget.scopeHeaders,
        )
      : widget.cachePrefix == null
      ? null
      : _stockAlerts || _stockSummary || _warehouseStock || _valuation ||
            _activityReport
      ? InventoryStockReceipts.reportCache(
          widget.cachePrefix!,
          widget.path!,
          widget.scopeHeaders['X-Suite-Branch'] ?? '',
        )
      : '${widget.cachePrefix}:${widget.path}';

  Future<List<Json>> _startLoad({bool reconnect = false}) {
    final result = _load(reconnect: reconnect);
    // FutureBuilder receives the same error even if the request finishes before it rebuilds.
    result.ignore();
    return result;
  }

  Future<List<Json>> _load({bool reconnect = false}) async {
    final path = widget.path;
    if (path == null) return [];
    final cacheKey = _cacheKey;
    final savedSearchKey =
        (_inventory ||
                _isCrm ||
                _crmCustomers ||
                _crmContacts ||
                _crmDeals ||
                _crmTasks ||
                _crmQuotations ||
                path == GstInvoicePage.listEndpoint ||
                path == '/srm/sales-orders') &&
            cacheKey != null
        ? '$cacheKey:recent-search-results'
        : null;
    final api = widget.controller.api;
    final revision = api.sessionRevision;
    final loadRevision = ++_loadRevision;
    _usedSavedFallback = false;
    _accessDenied = null;
    final page = _page;
    final searchTerm = _serverSearch;
    Future<void> loadSavedPages() async {
      if (_cachePagedRecords && cacheKey != null) {
        try {
          final saved = await SuiteReadCache.readPages(cacheKey);
          if (mounted &&
              api.sessionRevision == revision &&
              loadRevision == _loadRevision &&
              saved != null) {
            setState(() => _cached = saved);
          }
        } catch (_) {}
      }
      if (savedSearchKey != null) {
        try {
          final matches = await SuiteReadCache.read(savedSearchKey);
          if (mounted &&
              api.sessionRevision == revision &&
              loadRevision == _loadRevision &&
              matches != null) {
            final saved = <int, Json>{
              for (final row in _cached ?? const <Json>[])
                if (row['id'] case final int id) id: row,
            };
            for (final row in matches) {
              if (row['id'] case final int id) {
                final existing = saved[id];
                if (existing == null ||
                    SuiteReadCache.hasNewerVersion(row, existing)) {
                  saved[id] = row;
                }
              }
            }
            setState(() => _cached = saved.values.toList());
          }
        } catch (_) {
          // Recent search results are optional when local storage is unavailable.
        }
      }
    }

    var showSavedSnapshot = true;
    Future<List<Json>?> loadSavedSnapshot() async {
      if (cacheKey == null) return null;
      try {
        final cached = await SuiteReadCache.snapshot(cacheKey);
        if (showSavedSnapshot &&
            mounted &&
            api.sessionRevision == revision &&
            loadRevision == _loadRevision &&
            cached != null) {
          setState(() => _cached = cached.rows);
          final age = DateTime.now().difference(cached.savedAt);
          if (!reconnect &&
              !_offlineOnly &&
              !cached.invalidated &&
              searchTerm.isEmpty &&
              (_inventory ||
                  _warehouses ||
                  _warehouseStock ||
                  _stockSummary ||
                  _stockAlerts ||
                  _valuation ||
                  _activityReport ||
                  path == '/srm/sales-orders' ||
                  path == GstInvoicePage.listEndpoint ||
                  path == FinancePartyPage.endpoint) &&
              !age.isNegative &&
              age < SuiteReadCache.reuseWindow) {
            return cached.rows;
          }
        }
      } catch (_) {
        /* A cache failure does not block online reads. */
      }
      return null;
    }

    final refreshWithoutCache = reconnect && cacheKey != null;
    final savedSnapshot = loadSavedSnapshot();
    if (!refreshWithoutCache) {
      final fresh = await savedSnapshot;
      if (fresh != null) return fresh;
    }
    if (api.sessionRevision != revision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    if (_offlineOnly && !reconnect) {
      await loadSavedPages();
      if (api.sessionRevision != revision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      if (loadRevision == _loadRevision) {
        _usedSavedFallback = true;
      }
      return _cached ?? [];
    }
    dynamic data;
    try {
      final edits = _crmEdits;
      if (edits != null) {
        try {
          if (await edits.hasPending) await edits.sync(api);
        } catch (_) {
          // The list remains readable if the device edit store is unavailable.
        }
      }
      if (api.sessionRevision != revision) {
        throw ApiFailure('Your session ended. Sign in again.', 401);
      }
      data = await widget.controller.api.request(
        'GET',
        path,
        query: {
          ...widget.query,
          if (_appointmentDay case final DateTime day) ...{
            'from_at': day.toUtc().toIso8601String(),
            'until_at': DateTime(
              day.year,
              day.month,
              day.day + (_appointmentWeek ? 7 : 1),
            ).toUtc().toIso8601String(),
          },
          if (_crmCustomers)
            'state': jsonEncode({
              'page': page,
              'pageSize': 25,
              'search': searchTerm,
            })
          else ...{
            if (_hasPages) 'page': page,
            if (_batchTracking || _procurement == ProcurementRecord.order)
              'per_page': 25,
            if (_searchOnServer && searchTerm.isNotEmpty) 'search': searchTerm,
          },
        },
        scopeHeaders: widget.scopeHeaders,
      );
      showSavedSnapshot = false;
    } on ApiFailure catch (error) {
      if (cacheKey != null && (error.status == 401 || error.status == 403)) {
        showSavedSnapshot = false;
        if (mounted && loadRevision == _loadRevision) {
          setState(() {
            _cached = null;
            _customerCreateAllowed = false;
            _accessDenied = error;
          });
        }
        try {
          if (_cachePagedRecords) {
            await SuiteReadCache.clearPages(cacheKey);
          } else {
            await SuiteReadCache.clear(cacheKey);
            if (_inventory && widget.cachePrefix != null) {
              await SuiteReadCache.clear(
                SalesOrderDrafts.productPickerCacheKey(widget.cachePrefix!),
              );
            }
          }
          if (savedSearchKey != null) {
            await SuiteReadCache.clear(savedSearchKey);
          }
        } catch (_) {}
        return [];
      } else if (error.connectionFailure ||
          error.status == 429 ||
          (error.status ?? 0) >= 500) {
        await savedSnapshot;
        await loadSavedPages();
        if (mounted &&
            api.sessionRevision == revision &&
            loadRevision == _loadRevision &&
            _cached != null) {
          if (error.connectionFailure) _offlineOnly = true;
          _usedSavedFallback = true;
          return _cached!;
        }
      }
      showSavedSnapshot = false;
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
    if (_valuation && data is Json && records.isNotEmpty) {
      records[0] = {
        ...records.first,
        'totals_by_currency': data['totals_by_currency'],
        'unpriced_currency_items': data['unpriced_currency_items'],
      };
    }
    if (api.sessionRevision != revision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    if (loadRevision != _loadRevision) return records;
    _offlineOnly = false;
    if (_crmTasks && data is Json) {
      final filters = data['filters'] as Json?;
      _editableTaskProjects = {
        for (final project
            in (filters?['projects'] as List? ?? const []).whereType<Json>())
          if (project['can_manage_tasks'] == true && project['id'] is int)
            project['id'] as int,
      };
    }
    if (mounted && _crmCustomers && data is Json) {
      final allowed = (data['context'] as Json?)?['canCreate'] == true;
      if (allowed != _customerCreateAllowed) {
        setState(() => _customerCreateAllowed = allowed);
      }
    }
    if (_inventory && searchTerm.isEmpty) unawaited(_prepareInventoryDrafts());
    if (_hasPages) {
      final total = data is Json ? data['total'] : null;
      final pageSize = data is Json
          ? data['perPage'] ?? data['per_page'] ?? data['pageSize']
          : null;
      final pages = data is Json ? data['pages'] : null;
      final hasMore = data is Json ? data['has_more'] : null;
      _hasNextPage = hasMore is bool
          ? hasMore
          : pages is int
          ? page < pages
          : total is int && pageSize is int && page * pageSize < total;
    }
    if (cacheKey != null && (searchTerm.isEmpty || savedSearchKey != null)) {
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
              if (_isCrm) ...['source', 'rating'],
              if (_crmContacts) ...CrmContactPage.summaryFields.keys,
              if (_crmDeals) ...CrmDealPage.summaryFields,
              if (_crmCustomers) ...CrmCustomerPage.fields.keys,
              if (_crmTasks) ...['due_date', 'updated_at'],
              if (_inventory || path == '/srm/sales-orders') 'updated_at',
              if (_crmQuotations) ...CrmQuotationPage.fields,
              if (_crmQuoteApprovals) ..._approvalFields,
              if (_crmCpq) ...['rule_type', 'active'],
              if (_crmGuidedSelling) 'active',
              if (_batchTracking) ...InventoryBatchPage.fields.keys,
              if (_serialTracking) ...InventoryBatchPage.serialFields.keys,
              if (_procurement case final ProcurementRecord record) ...[
                record.number,
                ...record.fields.keys,
              ],
              if (_archivedOrders) 'number',
              'order_number',
              if (path == SalesContractPage.endpoint) 'contract_number',
              if (path == SalesEngagementPage.endpoint) 'engagement_number',
              if (path == SalesBillingPlanPage.endpoint)
                ...SalesBillingPlanPage.fields,
              'currency',
              'subtotal',
              'discount_amount',
              'tax_amount',
              'total_amount',
              'expected_start_date',
              'expected_end_date',
              'sku',
              'barcode',
              'category_name',
              'hsn_code',
              'sales_rate',
              'gst_rate',
              'item_name',
              'current_quantity',
              'reorder_level',
              'reorder_threshold',
              if (_stockAlerts) 'min_stock',
              'unit_code',
              if (_warehouses) ...[
                'warehouse_name',
                'warehouse_code',
                'branch',
                'address',
              ],
              if (_warehouseStock) ...[
                'stock_item_id',
                'warehouse_id',
                'warehouse_name',
                'quantity',
                'average_cost',
                'stock_value',
              ],
              if (_valuation) ...['stock_value', 'unpriced_currency_items'],
              if (_stockSummary) 'stock_value',
              if (_activityReport) ...[
                'last_movement_date',
                'age_days',
                'quantity_out',
                'movement_class',
              ],
              if (path == GstInvoicePage.listEndpoint)
                ...GstInvoicePage.summaryFields,
              if (path == FinancePartyPage.endpoint)
                ...FinancePartyPage.summaryFields,
            ])
              if (record[field] is String || record[field] is num)
                field: record[field],
            if (_crmTasks)
              'can_manage_tasks': _editableTaskProjects.contains(
                record['project_id'],
              ),
            if (_valuation && record['totals_by_currency'] is List)
              'totals_by_currency': record['totals_by_currency'],
          },
      ];
      Future<void> saveProjection() async {
        try {
          await SuiteReadCache.writePage(cacheKey, page, projection);
        } catch (_) {}
      }

      if (searchTerm.isNotEmpty && savedSearchKey != null) {
        if (projection.isNotEmpty) {
          try {
            await SuiteReadCache.write(
              savedSearchKey,
              projection,
              retainRecent: 100,
            );
          } catch (_) {
            // Search still works when local storage is unavailable.
          }
        }
      } else if (refreshWithoutCache || path == GstInvoicePage.listEndpoint) {
        _cached = projection;
        unawaited(saveProjection());
      } else {
        await saveProjection();
      }
    }
    return records;
  }

  Future<void> _openWarehouseForm([Json? warehouse]) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => InventoryWarehouseForm(
          api: widget.controller.api,
          scopeHeaders: widget.scopeHeaders,
          warehouse: warehouse,
        ),
      ),
    );
    if (!mounted || changed != true) return;
    _refresh();
    if (widget.cachePrefix case final scope?) {
      final branch = widget.scopeHeaders['X-Suite-Branch'] ?? '';
      try {
        await SuiteReadCache.clear('$scope:$_warehousesPath:$branch');
        await SuiteReadCache.invalidate('$scope:$_warehouseStockPath');
      } catch (_) {
        // The warehouse list can refresh directly from the API.
      }
    }
  }

  Future<void> _refreshStockLists([Set<int> products = const {}]) async {
    final scope = widget.cachePrefix;
    final api = widget.controller.api;
    final session = api.sessionRevision;
    if (scope != null) {
      await InventoryStockReceipts(scope).invalidateLists(products: products);
    }
    if (mounted && session == api.sessionRevision) _refresh();
  }

  Future<void> _refreshCrmRecords() async {
    if (_cacheKey case final key?) {
      try {
        await SuiteReadCache.clearPages(key);
      } catch (_) {}
    }
    if (mounted) _refresh();
  }

  CrmQuotationPage _quotationDetails(Json summary, {bool? offline}) =>
      CrmQuotationPage(
        api: widget.controller.api,
        summary: summary,
        cacheScope: widget.cachePrefix,
        offline: offline ?? (_offlineOnly || _usedSavedFallback),
        scopeHeaders: widget.scopeHeaders,
        canManage: widget.canManageQuotes,
        canCancel: widget.canCancelQuotes,
        canApprove: widget.canApproveQuotes,
        canSend: widget.canSendQuotes,
        canCreateRevision: widget.canCreateQuotes,
        canViewSalesOrder: widget.canViewQuoteSalesOrders,
        onChanged: _refreshCrmRecords,
      );

  Future<void> _openGuidedFlow({Json flow = const {}}) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => CrmGuidedSellingForm(
          api: widget.controller.api,
          scopeHeaders: widget.scopeHeaders,
          flow: flow,
        ),
      ),
    );
    if (mounted && saved == true) await _refreshCrmRecords();
  }

  void _openTracking(String path) => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => _SuiteRecords(
        title: path == InventoryBatchPage.batches
            ? 'Batches & Serials'
            : 'Serial numbers',
        controller: widget.controller,
        path: path,
        cachePrefix: widget.cachePrefix,
        scopeHeaders: widget.scopeHeaders,
        canCreateOrder: widget.canCreateOrder,
        offlineOnly: _offlineOnly || _usedSavedFallback,
      ),
    ),
  );

  void _openProcurementRecord(ProcurementRecord kind, Json row) =>
      Navigator.of(context).push<void>(
        MaterialPageRoute<void>(
          builder: (_) => InventoryProcurementPage(
            api: widget.controller.api,
            kind: kind,
            canReceive: widget.canCreateOrder,
            canIssue: widget.canEditOrders,
            canArchive: widget.canArchiveOrders,
            archived: _archivedOrders,
            canExport: widget.canExportSalesDocuments,
            onReceived: _refreshStockLists,
            onOrderChanged: _refreshCrmRecords,
            summary: _archivedOrders
                ? {...row, 'po_number': row['number']}
                : row,
            scopeHeaders: widget.scopeHeaders,
            cacheScope: widget.cachePrefix,
            offline: _offlineOnly || _usedSavedFallback,
          ),
        ),
      );

  Future<void> _createPurchaseOrder() async {
    final api = widget.controller.api;
    final revision = api.sessionRevision;
    final saved = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => InventoryPurchaseOrderForm(
          api: api,
          scopeHeaders: widget.scopeHeaders,
          cacheScope: widget.cachePrefix,
          offline: _offlineOnly || _usedSavedFallback,
        ),
      ),
    );
    if (!mounted || saved == null || revision != api.sessionRevision) return;
    if (saved['local'] == true) {
      _showPurchaseDrafts();
      return;
    }
    unawaited(_refreshCrmRecords());
    _openProcurementRecord(ProcurementRecord.order, saved);
  }

  Widget _employeeServices() {
    final api = widget.controller.api;
    final employee = widget.controller.user?.employeeId;
    final services = <(String, IconData, Widget)>[
      (
        'My Attendance',
        LucideIcons.clock,
        MyAttendancePage(
          api: api,
          cacheScope: widget.employeeCacheScope,
          offline: _offlineOnly,
        ),
      ),
      (
        'My Leave',
        LucideIcons.calendarDays,
        MyLeavePage(
          api: api,
          cacheScope: widget.employeeCacheScope,
          offline: _offlineOnly,
        ),
      ),
      (
        'My Roster',
        LucideIcons.calendarDays,
        MyRosterPage(
          api: api,
          employeeId: employee,
          cacheScope: widget.employeeCacheScope,
          offline: _offlineOnly,
        ),
      ),
      ('My Payslips', LucideIcons.fileText, MyPayslipsPage(api: api)),
      (
        'My Timesheets',
        LucideIcons.clipboardList,
        MyTimesheetsPage(
          api: api,
          employeeId: employee,
          canCreate: widget.canCreateTimesheets,
          cacheScope: widget.employeeCacheScope,
          offline: _offlineOnly,
        ),
      ),
    ];
    return PopupMenuButton<Widget>(
      tooltip: 'Employee services',
      icon: const Icon(LucideIcons.users),
      onSelected: (page) => Navigator.of(
        context,
      ).push(MaterialPageRoute<void>(builder: (_) => page)),
      itemBuilder: (_) => [
        for (final (label, icon, page) in services)
          PopupMenuItem(
            value: page,
            child: ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(icon),
              title: Text(label),
            ),
          ),
      ],
    );
  }

  SalesOrderDrafts? get _gstDrafts => widget.cachePrefix == null
      ? null
      : SalesOrderDrafts.gstInvoices(
          widget.cachePrefix!,
          invalidate: SuiteReadCache.invalidate,
        );

  InventoryOfflineCreates? get _gstBranches => widget.cachePrefix == null
      ? null
      : InventoryOfflineCreates(widget.cachePrefix!);

  void _openGstDrafts() {
    final drafts = _gstDrafts;
    if (drafts == null) return;
    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => SalesOrderDraftsPage(
          api: widget.controller.api,
          drafts: drafts,
          onSynced: _refresh,
          editGstDraft: widget.canCreateOrderInvoices
              ? (context, draft) async {
                  final headers =
                      (draft['headers'] as Json?)?.cast<String, String>() ??
                      const <String, String>{};
                  await showGstInvoiceDraftForm(
                    context,
                    api: widget.controller.api,
                    scopeHeaders: headers,
                    drafts: drafts,
                    branchStore: _gstBranches,
                    savedDraft: draft,
                    offline: _offlineOnly || _usedSavedFallback,
                    customerCacheScope: widget.cachePrefix,
                  );
                }
              : null,
        ),
      ),
    );
  }

  void _showPurchaseDrafts() {
    final scope = widget.cachePrefix;
    if (scope == null) return;
    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => SalesOrderDraftsPage(
          api: widget.controller.api,
          drafts: SalesOrderDrafts.purchaseOrders(
            scope,
            invalidate: SuiteReadCache.invalidate,
          ),
          correctPurchaseDraft: (draft) => InventoryPurchaseOrderForm(
            api: widget.controller.api,
            scopeHeaders: {
              for (final header in widget.scopeHeaders.entries)
                if (header.key != 'X-Suite-Branch') header.key: header.value,
              if (draft['branch'] case final String branch)
                'X-Suite-Branch': branch,
            },
            cacheScope: scope,
            offline: widget.controller.offline,
            rejectedDraft: draft,
          ),
          onSynced: _refreshCrmRecords,
        ),
      ),
    );
  }

  Future<void> _createTrackingRecord() async {
    final saved = await Navigator.of(context).push<Json>(
      MaterialPageRoute(
        builder: (_) => InventoryTrackingForm(
          api: widget.controller.api,
          scopeHeaders: widget.scopeHeaders,
          serial: _serialTracking,
        ),
      ),
    );
    if (!mounted || saved == null) return;
    final scope = widget.cachePrefix;
    if (_serialTracking && scope != null) {
      try {
        await SuiteReadCache.clearPages('$scope:${InventoryBatchPage.batches}');
        if (saved['batch_id'] case final int batch) {
          final branch = widget.scopeHeaders['X-Suite-Branch'] ?? '';
          await SuiteReadCache.clear(
            '$scope:${InventoryBatchPage.batches}/$batch:$branch',
          );
        }
      } catch (_) {}
    }
    if (mounted) await _refreshCrmRecords();
  }

  void _refresh() {
    _searchDebounce?.cancel();
    if (_searchOnServer && _serverSearch != _term) {
      _serverSearch = _term;
      _page = 1;
    }
    setState(() {
      _records = _startLoad(reconnect: true);
    });
  }

  void _changeSearch(String value) {
    setState(() => _term = value.trim());
    if (!_searchOnServer) return;
    _searchDebounce?.cancel();
    if (_offlineOnly) return;
    _searchDebounce = Timer(const Duration(milliseconds: 300), () {
      if (!mounted) return;
      setState(() {
        _serverSearch = _term;
        _page = 1;
        _records = _startLoad();
      });
    });
  }

  void _changePage(int offset) {
    setState(() {
      _page += offset;
      _records = _startLoad();
    });
  }

  Future<void> _chooseStockBranch() async {
    final revision = widget.controller.api.sessionRevision;
    final headers = {...widget.scopeHeaders}..remove('X-Suite-Branch');
    final branches = loadCrmDetail(
      api: widget.controller.api,
      path: '/branches/context',
      scope: widget.cachePrefix,
      headers: headers,
      offline: _offlineOnly || _usedSavedFallback,
      project: (data) => {'branches': data['branches']},
    );
    branches.ignore();
    final branch = await showDialog<Json>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Choose inventory branch'),
        children: [
          FutureBuilder(
            future: branches,
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                return ListTile(title: Text('${snapshot.error}'));
              }
              if (snapshot.connectionState != ConnectionState.done) {
                return const Center(child: CircularProgressIndicator());
              }
              final options = (snapshot.data?.record?['branches'] as List? ??
                      const [])
                  .whereType<Json>()
                  .where((row) => row['id'] is int && row['is_active'] == true);
              if (options.isEmpty) {
                return const ListTile(title: Text('No active branches found'));
              }
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  for (final option in options)
                    SimpleDialogOption(
                      onPressed: () => Navigator.pop(context, option),
                      child: Text('${option['name']}'),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
    if (!mounted ||
        branch == null ||
        revision != widget.controller.api.sessionRevision) {
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _SuiteRecords(
          title: 'Stock Summary · ${branch['name']}',
          controller: widget.controller,
          path: _stockSummaryPath,
          scopeHeaders: {...headers, 'X-Suite-Branch': '${branch['id']}'},
          cachePrefix: widget.cachePrefix,
          canViewFinanceInventory: widget.canViewFinanceInventory,
          offlineOnly: _offlineOnly || _usedSavedFallback,
        ),
      ),
    );
  }

  void _openStockLedger([Map<String, String> filters = const {}]) =>
      _openMovementReport(InventoryFinanceReport.stockLedger, filters);

  void _openMovementReport(
    InventoryFinanceReport report, [
    Map<String, String> filters = const {},
  ]) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => InventoryFinanceReportPage(
          api: widget.controller.api,
          report: report,
          scopeHeaders: widget.scopeHeaders,
          cacheScope: widget.cachePrefix,
          offline: _offlineOnly || _usedSavedFallback,
          initialFilters: filters,
        ),
      ),
    );
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    super.dispose();
  }

  AppBar _recordsAppBar(BuildContext context, {required List<Widget> actions}) {
    // Leave room for the back button, title and toolbar padding.
    final compact =
        MediaQuery.sizeOf(context).width < 220 + actions.length * 48;
    return AppBar(
      title: Text(widget.title),
      actions: compact ? null : actions,
      bottom: compact
          ? PreferredSize(
              preferredSize: const Size.fromHeight(48),
              child: SizedBox(
                height: 48,
                width: double.infinity,
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(children: actions),
                ),
              ),
            )
          : null,
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: _recordsAppBar(
      context,
      actions: [
        if (_appointments && widget.canCreateAppointment)
          FutureBuilder(
            future: _appointmentCapabilities,
            builder: (context, snapshot) {
              final caps = snapshot.data;
              final actions = caps is Json ? caps['appointment_actions'] : null;
              final canSchedule = actions is List
                  ? actions.contains('schedule')
                  : caps is Json && caps['manage'] == true;
              if (!canSchedule) return const SizedBox.shrink();
              return IconButton(
                tooltip: 'New appointment',
                icon: const Icon(LucideIcons.plus),
                onPressed: () async {
                  final booked = await Navigator.of(context).push<Json>(
                    MaterialPageRoute(
                      builder: (_) => AppointmentBookingPage(
                        api: widget.controller.api,
                        headers: widget.scopeHeaders,
                      ),
                    ),
                  );
                  if (!context.mounted || booked == null) return;
                  _refresh();
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Appointment booked.')),
                  );
                },
              );
            },
          ),
        if ((widget.canCreateOrder && (!_offlineOnly || _saleDrafts != null)) ||
            (widget.showInventory &&
                (widget.cachePrefix != null ||
                    (!_offlineOnly && !_usedSavedFallback))))
          PopupMenuButton<String>(
            tooltip: 'Sales order actions',
            onSelected: (action) async {
              if (action == 'payments') {
                await Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => PaymentSourceDirectory(
                      api: widget.controller.api,
                      scopeHeaders: widget.scopeHeaders,
                      cacheScope: widget.cachePrefix,
                      offline: _offlineOnly || _usedSavedFallback,
                    ),
                  ),
                );
                return;
              }
              if (action == 'drafts') {
                await Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => SalesOrderDraftsPage(
                      api: widget.controller.api,
                      drafts: _saleDrafts!,
                      onSynced: () {
                        if (mounted) _refresh();
                      },
                    ),
                  ),
                );
                return;
              }
              final saved = await Navigator.of(context).push<bool>(
                MaterialPageRoute<bool>(
                  builder: (_) => NewSalesOrderPage(
                    api: widget.controller.api,
                    drafts: _saleDrafts,
                    offline: _offlineOnly,
                  ),
                ),
              );
              if (saved == true && context.mounted) {
                if (!_offlineOnly) _refresh();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Sales order saved.')),
                );
              }
            },
            itemBuilder: (_) => [
              if (widget.canCreateOrder)
                const PopupMenuItem(
                  value: 'new',
                  child: Text('New sales order'),
                ),
              if (widget.showInventory &&
                  (widget.cachePrefix != null ||
                      (!_offlineOnly && !_usedSavedFallback)))
                const PopupMenuItem(
                  value: 'payments',
                  child: Text('Payment requests'),
                ),
              if (widget.canCreateOrder && _saleDrafts != null)
                const PopupMenuItem(
                  value: 'drafts',
                  child: Text('Order drafts'),
                ),
            ],
          ),
        if (_crmDeals &&
            (widget.canMoveDeals || widget.canManageQuotes) &&
            (widget.cachePrefix != null ||
                (!_offlineOnly && !_usedSavedFallback)))
          IconButton(
            tooltip: 'Payment requests',
            icon: const Icon(LucideIcons.banknote),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => PaymentSourceDirectory(
                  api: widget.controller.api,
                  scopeHeaders: widget.scopeHeaders,
                  crm: true,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_isCrm)
          IconButton(
            tooltip: 'CRM tasks',
            icon: const Icon(LucideIcons.listChecks),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Tasks',
                  controller: widget.controller,
                  path: CrmTaskPage.endpoint,
                  canEditFollowUps: widget.canEditFollowUps,
                  canAssignFollowUps: widget.canAssignFollowUps,
                  canCreateFollowUps: widget.canCreateFollowUps,
                  query: const {'sourceModule': 'crm', 'pageSize': 25},
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_crmTasks)
          IconButton(
            tooltip: 'Follow-ups',
            icon: const Icon(LucideIcons.calendarDays),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => CrmFollowUpsPage(
                  api: widget.controller.api,
                  headers: widget.scopeHeaders,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                  canEdit: widget.canEditFollowUps,
                  canAssign: widget.canAssignFollowUps,
                  canCreate: widget.canCreateFollowUps,
                ),
              ),
            ),
          ),
        if (_isCrm)
          IconButton(
            tooltip: 'Customers',
            icon: const Icon(LucideIcons.building2),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Customers',
                  controller: widget.controller,
                  path: CrmCustomerPage.endpoint,
                  collection: 'rows',
                  query: const {
                    'source': 'crm',
                    'role': 'Customer',
                    'entity_kind': 'all',
                  },
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_isCrm)
          IconButton(
            tooltip: 'Deals',
            icon: const Icon(LucideIcons.handshake),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Deals',
                  controller: widget.controller,
                  path: CrmDealPage.endpoint,
                  canMoveDeals: widget.canMoveDeals,
                  canCreateGuidedFlow: widget.canCreateGuidedFlow,
                  canEditGuidedFlow: widget.canEditGuidedFlow,
                  canCreateDeals: widget.canCreateDeals,
                  canManageQuotes: widget.canManageQuotes,
                  canCancelQuotes: widget.canCancelQuotes,
                  canCreateQuotes: widget.canCreateQuotes,
                  canViewQuoteSalesOrders: widget.canViewQuoteSalesOrders,
                  canApproveQuotes: widget.canApproveQuotes,
                  canSendQuotes: widget.canSendQuotes,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_isCrm)
          IconButton(
            tooltip: 'Contacts',
            icon: const Icon(LucideIcons.contact),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Contacts',
                  controller: widget.controller,
                  path: CrmContactPage.endpoint,
                  canCreateContacts: widget.canCreateContacts,
                  canEditContacts: widget.canEditContacts,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_crmCustomers &&
            _customerCreateAllowed &&
            !_offlineOnly &&
            !_usedSavedFallback)
          IconButton(
            tooltip: 'New customer',
            icon: const Icon(LucideIcons.plus),
            onPressed: () async {
              final created = await Navigator.of(context).push<bool>(
                MaterialPageRoute(
                  builder: (_) => CrmCustomerForm(
                    api: widget.controller.api,
                    scopeHeaders: widget.scopeHeaders,
                  ),
                ),
              );
              if (mounted && created == true) {
                _page = 1;
                await _refreshCrmRecords();
              }
            },
          ),
        if (_crmDeals)
          IconButton(
            tooltip: 'Pipeline',
            icon: const Icon(Icons.view_kanban_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => CrmPipelinePage(
                  api: widget.controller.api,
                  scopeHeaders: widget.scopeHeaders,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                  canMove: widget.canMoveDeals,
                  onDealChanged: _refreshCrmRecords,
                  dealBuilder: (summary, offline, refresh) => CrmDealPage(
                    api: widget.controller.api,
                    summary: summary,
                    offline: offline,
                    cacheScope: widget.cachePrefix,
                    scopeHeaders: widget.scopeHeaders,
                    canMove: widget.canMoveDeals,
                    onChanged: () {
                      refresh();
                      _refreshCrmRecords();
                    },
                    quotationBuilder: widget.canCreateQuotes
                        ? (quote) => _quotationDetails(quote, offline: false)
                        : null,
                  ),
                ),
              ),
            ),
          ),
        if (_crmDeals)
          IconButton(
            tooltip: 'Quotations',
            icon: const Icon(LucideIcons.fileText),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Quotations',
                  canCreateGuidedFlow: widget.canCreateGuidedFlow,
                  canEditGuidedFlow: widget.canEditGuidedFlow,
                  controller: widget.controller,
                  path: CrmQuotationPage.endpoint,
                  canManageQuotes: widget.canManageQuotes,
                  canCancelQuotes: widget.canCancelQuotes,
                  canViewQuoteSalesOrders: widget.canViewQuoteSalesOrders,
                  canApproveQuotes: widget.canApproveQuotes,
                  canSendQuotes: widget.canSendQuotes,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_crmQuotations)
          IconButton(
            tooltip: 'Quote Approvals',
            icon: const Icon(Icons.fact_check_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Quote Approvals',
                  controller: widget.controller,
                  path: _quoteApprovalsPath,
                  canManageQuotes: widget.canManageQuotes,
                  canCancelQuotes: widget.canCancelQuotes,
                  canViewQuoteSalesOrders: widget.canViewQuoteSalesOrders,
                  canApproveQuotes: widget.canApproveQuotes,
                  canSendQuotes: widget.canSendQuotes,
                  canCreateQuotes: widget.canCreateQuotes,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_crmQuotations)
          IconButton(
            tooltip: 'CPQ Rules',
            icon: const Icon(Icons.rule),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'CPQ Rules',
                  canCreateGuidedFlow: widget.canCreateGuidedFlow,
                  canEditGuidedFlow: widget.canEditGuidedFlow,
                  controller: widget.controller,
                  path: _cpqPath,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_crmCpq && !_offlineOnly && !_usedSavedFallback)
          IconButton(
            tooltip: 'Evaluate CPQ rules',
            icon: const Icon(Icons.calculate_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => CrmCpqEvaluator(
                  api: widget.controller.api,
                  scopeHeaders: widget.scopeHeaders,
                ),
              ),
            ),
          ),
        if (_crmCpq)
          IconButton(
            tooltip: 'Guided Selling',
            icon: const Icon(Icons.alt_route),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Guided Selling',
                  controller: widget.controller,
                  path: CrmGuidedSellingForm.endpoint,
                  canCreateGuidedFlow: widget.canCreateGuidedFlow,
                  canEditGuidedFlow: widget.canEditGuidedFlow,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_crmGuidedSelling &&
            widget.canCreateGuidedFlow &&
            !_offlineOnly &&
            !_usedSavedFallback)
          IconButton(
            tooltip: 'New guided selling flow',
            icon: const Icon(Icons.add),
            onPressed: _openGuidedFlow,
          ),
        if (_crmDeals &&
            widget.canCreateDeals &&
            !_offlineOnly &&
            !_usedSavedFallback)
          IconButton(
            tooltip: 'New deal',
            icon: const Icon(LucideIcons.plus),
            onPressed: () async {
              final created = await Navigator.of(context).push<bool>(
                MaterialPageRoute(
                  builder: (_) => CrmDealForm(
                    api: widget.controller.api,
                    scopeHeaders: widget.scopeHeaders,
                  ),
                ),
              );
              if (mounted && created == true) {
                _page = 1;
                await _refreshCrmRecords();
              }
            },
          ),
        if (_crmContacts &&
            widget.canCreateContacts &&
            !_offlineOnly &&
            !_usedSavedFallback)
          IconButton(
            tooltip: 'New contact',
            icon: const Icon(LucideIcons.userPlus),
            onPressed: () async {
              final created = await Navigator.of(context).push<bool>(
                MaterialPageRoute(
                  builder: (_) => CrmContactForm(
                    api: widget.controller.api,
                    scopeHeaders: widget.scopeHeaders,
                  ),
                ),
              );
              if (mounted && created == true) {
                _page = 1;
                await _refreshCrmRecords();
              }
            },
          ),
        if (_isCrm &&
            widget.canCreateLead &&
            (!_offlineOnly || _crmEdits != null))
          IconButton(
            tooltip: 'New lead',
            icon: const Icon(LucideIcons.plus),
            onPressed: () async {
              final created = await Navigator.of(context).push<bool>(
                MaterialPageRoute<bool>(
                  builder: (_) => CrmNewLeadPage(
                    api: widget.controller.api,
                    queue: _crmEdits,
                    offline: _offlineOnly,
                  ),
                ),
              );
              if (created == true && context.mounted) {
                _page = 1;
                if (!_offlineOnly) _refresh();
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(const SnackBar(content: Text('Lead saved.')));
              }
            },
          ),
        if (_crmEdits case final CrmOfflineEdits queue)
          IconButton(
            tooltip: 'Lead drafts',
            icon: const Icon(LucideIcons.fileText),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => CrmLeadDraftsPage(
                  queue: queue,
                  api: widget.controller.api,
                  canEdit: widget.canCreateLead,
                  onSynced: () {
                    if (mounted) {
                      _page = 1;
                      _refresh();
                    }
                  },
                ),
              ),
            ),
          ),
        if (widget.path == '/employees/') _employeeServices(),
        IconButton(
          tooltip: 'Refresh',
          icon: const Icon(LucideIcons.refreshCw),
          onPressed: _refresh,
        ),
        if (_inventory)
          PopupMenuButton<ProcurementRecord>(
            tooltip: 'Procurement',
            icon: const Icon(Icons.receipt_long_outlined),
            onSelected: (kind) => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: kind.title,
                  controller: widget.controller,
                  path: kind.path,
                  canArchiveOrders: widget.canArchiveOrders,
                  canExportSalesDocuments: widget.canExportSalesDocuments,
                  canCreateOrder: widget.canCreateOrder,
                  canEditOrders: widget.canEditOrders,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
            itemBuilder: (_) => [
              for (final kind in ProcurementRecord.values)
                PopupMenuItem(value: kind, child: Text(kind.title)),
            ],
          ),
        if (_procurement == ProcurementRecord.order && !_archivedOrders)
          IconButton(
            tooltip: 'Archived orders',
            icon: const Icon(Icons.archive_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Archived orders',
                  controller: widget.controller,
                  path: _archivedOrdersPath,
                  query: const {'include_removed': true, 'status': 'archived'},
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_procurement == ProcurementRecord.order &&
            !_archivedOrders &&
            widget.canCreateOrder &&
            (!(_offlineOnly || _usedSavedFallback) ||
                widget.cachePrefix != null))
          IconButton(
            tooltip: 'New purchase order',
            icon: const Icon(Icons.add),
            onPressed: _createPurchaseOrder,
          ),
        if (_procurement == ProcurementRecord.order &&
            !_archivedOrders &&
            widget.canCreateOrder &&
            widget.cachePrefix != null)
          IconButton(
            tooltip: 'Purchase order drafts',
            icon: const Icon(Icons.pending_actions),
            onPressed: _showPurchaseDrafts,
          ),
        if (_inventory)
          IconButton(
            tooltip: 'Batches & Serials',
            icon: const Icon(Icons.qr_code_2),
            onPressed: () => _openTracking(InventoryBatchPage.batches),
          ),
        if (_batchTracking)
          IconButton(
            tooltip: 'Serial numbers',
            icon: const Icon(Icons.tag_outlined),
            onPressed: () => _openTracking(InventoryBatchPage.serials),
          ),
        if ((_batchTracking || _serialTracking) &&
            widget.canCreateOrder &&
            !_offlineOnly &&
            !_usedSavedFallback)
          IconButton(
            tooltip: _serialTracking
                ? 'Register serial number'
                : 'Create batch',
            icon: const Icon(Icons.add),
            onPressed: _createTrackingRecord,
          ),
        if (_inventory)
          IconButton(
            tooltip: 'Stock Summary',
            icon: const Icon(LucideIcons.list),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Stock Summary',
                  controller: widget.controller,
                  path: _stockSummaryPath,
                  canViewFinanceInventory: widget.canViewFinanceInventory,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_inventory)
          IconButton(
            tooltip: 'Warehouses',
            icon: const Icon(LucideIcons.warehouse),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Warehouses',
                  controller: widget.controller,
                  path: _warehousesPath,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  canCreateOrder: widget.canCreateOrder,
                  canEditWarehouses: widget.canEditWarehouses,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_inventory)
          IconButton(
            tooltip: 'Low stock alerts',
            icon: const Icon(LucideIcons.bell),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Low stock alerts',
                  controller: widget.controller,
                  path: _reorderPath,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_warehouses &&
            !_offlineOnly &&
            !_usedSavedFallback &&
            widget.canCreateOrder)
          IconButton(
            tooltip: 'New warehouse',
            icon: const Icon(LucideIcons.plus),
            onPressed: _openWarehouseForm,
          ),
        if (_warehouses)
          IconButton(
            tooltip: 'Warehouse Stock',
            icon: const Icon(LucideIcons.boxes),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Warehouse Stock',
                  controller: widget.controller,
                  path: _warehouseStockPath,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_stockSummary)
          IconButton(
            tooltip: 'Choose inventory branch',
            icon: const Icon(LucideIcons.gitBranch),
            onPressed: _chooseStockBranch,
          ),
        if (_stockSummary)
          IconButton(
            tooltip: 'Stock Ledger',
            icon: const Icon(LucideIcons.bookOpen),
            onPressed: _openStockLedger,
          ),
        if (_stockSummary)
          PopupMenuButton<Object>(
            tooltip: 'Stock activity reports',
            icon: const Icon(LucideIcons.chartNoAxesColumn),
            onSelected: (report) {
              if (report is InventoryFinanceReport) {
                _openMovementReport(report);
                return;
              }
              final path = report as String;
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => _SuiteRecords(
                    title: InventoryStockReceipts.activityReports[path]!,
                    controller: widget.controller,
                    path: path,
                    scopeHeaders: widget.scopeHeaders,
                    cachePrefix: widget.cachePrefix,
                    offlineOnly: _offlineOnly || _usedSavedFallback,
                  ),
                ),
              );
            },
            itemBuilder: (_) => [
              for (final report in InventoryFinanceReport.values)
                if (report.analysisReport &&
                    report != InventoryFinanceReport.stockLedger)
                  PopupMenuItem(value: report, child: Text(report.title)),
              for (final report
                  in InventoryStockReceipts.activityReports.entries)
                PopupMenuItem(value: report.key, child: Text(report.value)),
            ],
          ),
        if (widget.path == FinancePartyPage.endpoint)
          IconButton(
            tooltip: 'Voucher register',
            icon: const Icon(LucideIcons.bookOpen),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => FinanceVouchersPage(
                  api: widget.controller.api,
                  canPost: widget.canPostVoucher,
                  canCreate: widget.canCreateVoucher,
                  canEdit: widget.canEditVoucher,
                  canCancel: widget.canCancelVoucher,
                  canReverse: widget.canReverseVoucher,
                  scopeHeaders: widget.scopeHeaders,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (widget.path == FinancePartyPage.endpoint)
          IconButton(
            tooltip: 'Chart of Accounts',
            icon: const Icon(LucideIcons.gitBranch),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => FinanceChartPage(
                  api: widget.controller.api,
                  scopeHeaders: widget.scopeHeaders,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (widget.canViewFinanceInventory &&
            (_stockSummary || widget.path == FinancePartyPage.endpoint))
          PopupMenuButton<InventoryFinanceReport>(
            tooltip: 'Inventory financial reports',
            icon: const Icon(Icons.analytics_outlined),
            onSelected: (report) => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => InventoryFinanceReportPage(
                  api: widget.controller.api,
                  report: report,
                  financeAnalysis: report.analysisReport,
                  scopeHeaders: widget.scopeHeaders,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
            itemBuilder: (_) => [
              for (final report in InventoryFinanceReport.values)
                if (!report.analysisReport ||
                    widget.path == FinancePartyPage.endpoint)
                  PopupMenuItem(value: report, child: Text(report.title)),
            ],
          ),
        if (_warehouseStock)
          IconButton(
            tooltip: 'Inventory Valuation',
            icon: const Icon(LucideIcons.chartNoAxesColumn),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Inventory Valuation',
                  controller: widget.controller,
                  path: _valuationPath,
                  scopeHeaders: widget.scopeHeaders,
                  cachePrefix: widget.cachePrefix,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (_inventoryDrafts != null)
          IconButton(
            tooltip: 'Product drafts',
            icon: const Icon(LucideIcons.packagePlus),
            onPressed: () async {
              await Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => InventoryDraftsPage(
                    offline: _offlineOnly,
                    api: widget.controller.api,
                    drafts: _inventoryDrafts,
                  ),
                ),
              );
              if (mounted) {
                setState(() {
                  _records = _startLoad(reconnect: true);
                });
              }
            },
          ),
        if (widget.path == GstInvoicePage.listEndpoint &&
            widget.canViewCollections)
          IconButton(
            tooltip: 'Collections',
            icon: const Icon(LucideIcons.banknote),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => GstCollectionsPage(
                  api: widget.controller.api,
                  scopeHeaders: widget.scopeHeaders,
                  cacheScope: widget.cachePrefix,
                  offline: _offlineOnly || _usedSavedFallback,
                  canExport: widget.canExportSalesDocuments,
                ),
              ),
            ),
          ),
        if (widget.path == GstInvoicePage.listEndpoint &&
            widget.cachePrefix != null)
          IconButton(
            tooltip: 'Saved GST drafts',
            icon: const Icon(LucideIcons.upload),
            onPressed: _openGstDrafts,
          ),
        if (widget.path == GstInvoicePage.listEndpoint &&
            widget.canCreateOrderInvoices &&
            ((!_offlineOnly && !_usedSavedFallback) || _gstDrafts != null))
          IconButton(
            tooltip: 'New GST invoice draft',
            icon: const Icon(LucideIcons.plus),
            onPressed: () async {
              final api = widget.controller.api;
              final revision = api.sessionRevision;
              final invoice = await showGstInvoiceDraftForm(
                context,
                api: api,
                scopeHeaders: widget.scopeHeaders,
                drafts: _gstDrafts,
                branchStore: _gstBranches,
                offline: _offlineOnly || _usedSavedFallback,
                customerCacheScope: widget.cachePrefix,
              );
              if (!context.mounted ||
                  invoice == null ||
                  api.sessionRevision != revision) {
                return;
              }
              if (invoice['local'] == true) {
                _openGstDrafts();
                return;
              }
              _refresh();
              await Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => GstInvoicePage(
                    api: api,
                    id: invoice['id'] as int,
                    summary: invoice,
                    cacheScope: widget.cachePrefix,
                    scopeHeaders:
                        invoice['draft_scope_headers']
                            as Map<String, String>? ??
                        widget.scopeHeaders,
                    onChanged: _refresh,
                    canEdit: true,
                    canIssue: widget.canIssueInvoices,
                    canExport: widget.canExportSalesDocuments,
                  ),
                ),
              );
            },
          ),
        if (widget.path == SalesEngagementPage.endpoint)
          IconButton(
            tooltip: 'Billing plans',
            icon: const Icon(LucideIcons.calendarDays),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Billing plans',
                  controller: widget.controller,
                  path: SalesBillingPlanPage.endpoint,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  canEditOrders: widget.canEditOrders,
                  canIssueInvoices: widget.canIssueInvoices,
                  canCreateOrderInvoices: widget.canCreateOrderInvoices,
                  canExportSalesDocuments: widget.canExportSalesDocuments,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (widget.showInventory)
          IconButton(
            tooltip: 'Engagements',
            icon: const Icon(LucideIcons.briefcase),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Engagements',
                  controller: widget.controller,
                  path: SalesEngagementPage.endpoint,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  canEditOrders: widget.canEditWarehouses,
                  canIssueInvoices: widget.canIssueInvoices,
                  canCreateOrderInvoices: widget.canCreateOrderInvoices,
                  canExportSalesDocuments: widget.canExportSalesDocuments,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (widget.showInventory)
          IconButton(
            tooltip: 'Contracts',
            icon: const Icon(LucideIcons.fileText),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'Contracts',
                  controller: widget.controller,
                  path: SalesContractPage.endpoint,
                  cachePrefix: widget.cachePrefix,
                  scopeHeaders: widget.scopeHeaders,
                  canEditOrders: widget.canEditWarehouses,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
          ),
        if (widget.showInventory)
          IconButton(
            tooltip: 'GST Billing',
            icon: const Icon(LucideIcons.receipt),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => _SuiteRecords(
                  title: 'GST Billing',
                  controller: widget.controller,
                  path: GstInvoicePage.listEndpoint,
                  scopeHeaders: widget.scopeHeaders,
                  query: const {'summary_only': true},
                  cachePrefix: widget.cachePrefix,
                  canViewCollections: widget.canViewCollections,
                  canExportSalesDocuments: widget.canExportSalesDocuments,
                  canIssueInvoices: widget.canIssueInvoices,
                  canCreateOrderInvoices: widget.canCreateOrderInvoices,
                  offlineOnly: _offlineOnly || _usedSavedFallback,
                ),
              ),
            ),
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
                  path: InventoryOfflineCreates.itemsEndpoint,
                  canExportSalesDocuments: widget.canExportSalesDocuments,
                  canViewFinanceInventory: widget.canViewFinanceInventory,
                  canEditOrders:
                      widget.canEditOrders && widget.canEditWarehouses,
                  canEditInventoryProducts: widget.canEditInventoryProducts,
                  canArchiveOrders: widget.canArchiveOrders,
                  query: const {'summary_only': true},
                  cachePrefix: widget.cachePrefix,
                  canCreateOrder: widget.canCreateOrder,
                  canEditWarehouses: widget.canEditWarehouses,
                  offlineOnly: _offlineOnly,
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
              final error = _accessDenied ?? snapshot.error;
              final temporary =
                  error is ApiFailure &&
                  (error.status == null ||
                      error.status == 429 ||
                      (error.status ?? 0) >= 500);
              if (error != null && (_cached == null || !temporary)) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(error.toString(), textAlign: TextAlign.center),
                        TextButton(
                          onPressed: _refresh,
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
              if (rows.isEmpty &&
                  !_appointments &&
                  !_stockAlerts &&
                  !_searchOnServer &&
                  !_usedSavedFallback) {
                return const Center(child: Text('No records found'));
              }
              final cached = snapshot.data == null || _usedSavedFallback;
              final loading = snapshot.connectionState != ConnectionState.done;
              final search =
                  _searchOnServer ||
                  widget.cachePrefix != null ||
                  _stockAlerts ||
                  _stockSummary ||
                  _warehouses ||
                  _warehouseStock ||
                  _valuation ||
                  _activityReport ||
                  _appointments ||
                  widget.path == GstInvoicePage.listEndpoint ||
                  widget.path == FinancePartyPage.endpoint;
              final candidates = _stockAlerts
                  ? (rows.where(_lowStock).toList()..sort(
                      (a, b) => _stockNumber(
                        a['current_quantity'],
                      )!.compareTo(_stockNumber(b['current_quantity'])!),
                    ))
                  : _appointments && _appointmentStatus.isNotEmpty
                  ? rows
                        .where((row) => row['status'] == _appointmentStatus)
                        .toList()
                  : rows;
              final hasServerResults =
                  _searchOnServer &&
                  !cached &&
                  !loading &&
                  _term == _serverSearch;
              final visible = _term.isEmpty || hasServerResults
                  ? candidates
                  : candidates
                        .where(
                          (item) =>
                              [
                                    'title',
                                    'name',
                                    'first_name',
                                    'last_name',
                                    'order_number',
                                    'invoice_number',
                                    'legal_name',
                                    'trade_name',
                                    'party_code',
                                    'employee_id',
                                    'status',
                                    'sku',
                                    'barcode',
                                    'category_name',
                                    'item_name',
                                    if (_warehouses) ...[
                                      'warehouse_name',
                                      'warehouse_code',
                                      'branch',
                                      'address',
                                    ],
                                    if (_warehouseStock) 'warehouse_name',
                                    'full_name',
                                    'company_name',
                                    if (_crmContacts || _crmCustomers) ...[
                                      'email',
                                      'phone',
                                    ],
                                    if (_crmDeals) 'stage_name',
                                    if (_crmQuotations) 'quote_number',
                                    if (_crmCpq) 'rule_type',
                                    if (_batchTracking) 'batch_number',
                                    if (_serialTracking) ...[
                                      'serial_number',
                                      'reference_number',
                                    ],
                                    if (_procurement
                                        case final ProcurementRecord
                                            record) ...[
                                      record.number,
                                      'vendor_name',
                                      'reference_number',
                                    ],
                                    if (_archivedOrders) 'number',
                                    if (_crmQuoteApprovals) ...[
                                      'quote_id',
                                      'reason',
                                      'comments',
                                    ],
                                  ]
                                  .map((key) => item[key] ?? '')
                                  .followedBy([
                                    if (_appointments && item['data'] is Json)
                                      (item['data'] as Json)['customer_name'] ??
                                          '',
                                  ])
                                  .join(' ')
                                  .toLowerCase()
                                  .contains(_term.toLowerCase()),
                        )
                        .toList();
              return Column(
                children: [
                  if (_appointments)
                    ListTile(
                      leading: const Icon(LucideIcons.calendar),
                      title: Text(switch (_appointmentDay) {
                        final DateTime day => MaterialLocalizations.of(
                          context,
                        ).formatMediumDate(day),
                        null => 'Choose schedule date',
                      }),
                      subtitle: const Text('Device time zone'),
                      onTap: _pickAppointmentDay,
                      trailing: _appointmentDay == null
                          ? null
                          : IconButton(
                              tooltip: 'Clear schedule date',
                              onPressed: () => _setAppointmentDay(null),
                              icon: const Icon(Icons.clear),
                            ),
                    ),
                  if (_appointments)
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        IconButton(
                          tooltip: _appointmentWeek
                              ? 'Previous week'
                              : 'Previous day',
                          onPressed: () => _moveAppointmentDay(-1),
                          icon: const Icon(Icons.chevron_left),
                        ),
                        TextButton(
                          onPressed: () {
                            final now = DateTime.now();
                            _setAppointmentDay(
                              DateTime(now.year, now.month, now.day),
                            );
                          },
                          child: const Text('Today'),
                        ),
                        IconButton(
                          tooltip: _appointmentWeek ? 'Next week' : 'Next day',
                          onPressed: () => _moveAppointmentDay(1),
                          icon: const Icon(Icons.chevron_right),
                        ),
                      ],
                    ),
                  if (_appointments)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: SegmentedButton<bool>(
                        segments: const [
                          ButtonSegment(value: false, label: Text('Day')),
                          ButtonSegment(value: true, label: Text('Week')),
                        ],
                        selected: {_appointmentWeek},
                        onSelectionChanged: (selection) {
                          final day = _appointmentDay ?? DateTime.now();
                          _setAppointmentDay(
                            DateTime(day.year, day.month, day.day),
                            week: selection.single,
                          );
                        },
                      ),
                    ),
                  if (_stockAlerts)
                    ListTile(
                      leading: const Icon(LucideIcons.bell),
                      title: Text(
                        candidates.length == 1
                            ? '1 item needs attention'
                            : '${candidates.length} items need attention',
                      ),
                      subtitle: const Text(
                        'Compares warehouse stock on hand with the reorder '
                        'level, or minimum stock when no reorder level is set.',
                      ),
                    ),
                  if (_valuation && rows.isNotEmpty)
                    ExpansionTile(
                      title: const Text('Inventory value by currency'),
                      children: [
                        for (final total
                            in (rows.first['totals_by_currency'] as List? ??
                                    const [])
                                .whereType<Json>())
                          ListTile(
                            title: Text('${total['currency']}'),
                            trailing: Text('${total['total_inventory_value']}'),
                          ),
                        if ((rows.first['unpriced_currency_items'] as int? ??
                                0) >
                            0)
                          ListTile(
                            title: Text(
                              "${rows.first['unpriced_currency_items']} items have no currency",
                            ),
                          ),
                      ],
                    ),
                  if (search)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                      child: TextField(
                        onChanged: _changeSearch,
                        decoration: InputDecoration(
                          prefixIcon: const Icon(LucideIcons.search),
                          labelText: _appointments
                              ? 'Search customer'
                              : switch (widget.path) {
                                  CrmLeadPage.endpoint =>
                                    cached
                                        ? 'Search saved leads'
                                        : 'Search leads',
                                  CrmContactPage.endpoint =>
                                    cached
                                        ? 'Search saved contacts'
                                        : 'Search contacts',
                                  CrmDealPage.endpoint =>
                                    cached
                                        ? 'Search saved deals'
                                        : 'Search deals',
                                  CrmCustomerPage.endpoint =>
                                    cached
                                        ? 'Search saved customers'
                                        : 'Search customers',
                                  CrmTaskPage.endpoint =>
                                    cached
                                        ? 'Search saved tasks'
                                        : 'Search tasks',
                                  CrmQuotationPage.endpoint =>
                                    cached
                                        ? 'Search saved quotations'
                                        : 'Search quotations',
                                  '/srm/inventory/items' =>
                                    cached
                                        ? 'Search saved products'
                                        : 'Search products',
                                  _reorderPath ||
                                  _stockSummaryPath => 'Search products',
                                  _warehousesPath => 'Search warehouses',
                                  _warehouseStockPath =>
                                    'Search products or warehouses',
                                  _valuationPath => 'Search products',
                                  _ when _activityReport => 'Search products',
                                  GstInvoicePage.listEndpoint =>
                                    cached
                                        ? 'Search saved invoices'
                                        : 'Search invoices',
                                  FinancePartyPage.endpoint => 'Search parties',
                                  '/employees/' => 'Search employees',
                                  '/srm/sales-orders' =>
                                    cached
                                        ? 'Search saved orders'
                                        : 'Search orders',
                                  _ => 'Search saved orders',
                                },
                        ),
                      ),
                    ),
                  if (_appointments)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                      child: DropdownButtonFormField<String>(
                        initialValue: _appointmentStatus,
                        decoration: const InputDecoration(labelText: 'Status'),
                        items: [
                          for (final (value, label) in const [
                            ('', 'All statuses'),
                            ('booked', 'Confirmed'),
                            ('checked_in', 'Checked in'),
                            ('in_service', 'In service'),
                            ('completed', 'Completed'),
                            ('cancelled', 'Cancelled'),
                            ('no_show', 'No show'),
                          ])
                            DropdownMenuItem(value: value, child: Text(label)),
                        ],
                        onChanged: (value) => setState(() {
                          _appointmentStatus = value ?? '';
                        }),
                      ),
                    ),
                  if (visible.isEmpty &&
                      (rows.isNotEmpty || !_usedSavedFallback))
                    Text(
                      _stockAlerts && _term.isEmpty
                          ? 'No low stock items'
                          : _appointments
                          ? 'No appointments match this view'
                          : 'No matching records',
                    ),
                  if (_hasPages && !cached && (_page > 1 || _hasNextPage))
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        TextButton(
                          onPressed: loading || _page <= 1
                              ? null
                              : () => _changePage(-1),
                          child: const Text('Previous'),
                        ),
                        Text('Page $_page'),
                        TextButton(
                          onPressed: loading || !_hasNextPage
                              ? null
                              : () => _changePage(1),
                          child: const Text('Next'),
                        ),
                      ],
                    ),
                  Expanded(
                    child: ListView.builder(
                      itemCount: visible.length + (cached ? 1 : 0),
                      itemBuilder: (_, index) {
                        if (cached && index == 0) {
                          return ListTile(
                            title: Text(
                              _offlineOnly && rows.isEmpty
                                  ? 'Offline · No saved records'
                                  : snapshot.hasError || _usedSavedFallback
                                  ? 'Refresh unavailable · Saved records'
                                  : 'Saved records · Refreshing',
                            ),
                          );
                        }
                        final item = visible[index - (cached ? 1 : 0)];
                        if (widget.path == PowerEnvironmentPage.endpoint &&
                            item['key'] is String) {
                          final key = item['key'] as String;
                          final enabled = item['enabled'] == true;
                          return ListTile(
                            title: Text(key),
                            subtitle: Text(enabled ? 'Enabled' : 'Disabled'),
                            onTap: enabled
                                ? () => Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => PowerEnvironmentPage(
                                        api: widget.controller.api,
                                        environment: key,
                                      ),
                                    ),
                                  )
                                : null,
                          );
                        }
                        final name = [
                          item['first_name'],
                          item['last_name'],
                        ].whereType<String>().join(' ');
                        final label =
                            (_warehouses ? item['warehouse_name'] : null) ??
                            item['item_name'] ??
                            item['title'] ??
                            item['name'] ??
                            item['legal_name'] ??
                            item['full_name'] ??
                            item['order_number'] ??
                            item['invoice_number'] ??
                            item['quote_number'] ??
                            item['batch_number'] ??
                            item['serial_number'] ??
                            item[_procurement?.number] ??
                            (_archivedOrders ? item['number'] : null) ??
                            (name.isEmpty
                                ? 'Record ${item['id'] ?? index + 1}'
                                : name);
                        final subtitle = [
                          if (widget.path == SalesContractPage.endpoint)
                            item['contract_number'],
                          if (widget.path == SalesEngagementPage.endpoint)
                            item['engagement_number'],
                          if (_procurement != null) ...[
                            item['vendor_name'],
                            if (item['expected_date'] != null)
                              "Expected ${item['expected_date']}",
                            item['receipt_date'],
                            if (item['total_amount'] != null)
                              "Total ${item['total_amount']}",
                          ],
                          if (_batchTracking) ...[
                            if (item['expiry_date'] != null)
                              "Expires ${item['expiry_date']}",
                            if (item['available_quantity'] != null)
                              "${item['available_quantity']} available",
                            if (item['serial_count'] != null)
                              "${item['serial_count']} serials",
                          ],
                          if (_serialTracking) ...[
                            item['reference_number'],
                            if (item['batch_id'] != null)
                              "Batch #${item['batch_id']}",
                            if (item['received_date'] != null)
                              "Received ${item['received_date']}",
                          ],
                          if (_crmGuidedSelling)
                            if (item['active'] case final bool active)
                              active ? 'Active' : 'Inactive',
                          if (_crmCpq) ...[
                            item['rule_type'],
                            if (item['active'] case final bool active)
                              active ? 'Active' : 'Inactive',
                          ],
                          if (_crmQuotations) ...[
                            if ((item['grand_total'] ?? item['total_amount']) !=
                                null)
                              "${item['grand_total'] ?? item['total_amount']} ${item['currency'] ?? ''}",
                            if (item['expiry_date'] != null)
                              "Expires ${item['expiry_date']}",
                          ],
                          if (_crmTasks && item['due_date'] != null)
                            "Due ${item['due_date']}",
                          if (_crmCustomers) ...[
                            item['entityKind'],
                            item['email'],
                            item['phone'],
                          ],
                          if (_crmDeals) ...[
                            item['company_name'],
                            item['stage_name'],
                            if (item['amount'] != null)
                              '${item['amount']} ${item['currency'] ?? ''}'
                                  .trim(),
                          ],
                          if (_crmContacts) ...[
                            item['company_name'],
                            item['email'],
                            item['phone'],
                          ],
                          if (_warehouseStock) item['warehouse_name'],
                          if (_warehouses) ...[
                            item['warehouse_code'],
                            item['branch'],
                            item['address'],
                          ],
                          item['sku'],
                          item['status'],
                          if (_stockAlerts) ...[
                            'On hand ${item['current_quantity']}',
                            if (item['reorder_level'] != null)
                              'Reorder level ${item['reorder_level']}',
                            if (item['min_stock'] != null)
                              'Minimum stock ${item['min_stock']}',
                            'Reorder at ${item['reorder_threshold']}',
                          ],
                        ].whereType<String>().join(' · ');
                        final procurement = _procurement;
                        if (procurement != null && item['id'] is int) {
                          return ListTile(
                            title: Text('$label'),
                            subtitle: subtitle.isEmpty ? null : Text(subtitle),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () =>
                                _openProcurementRecord(procurement, item),
                          );
                        }
                        if (_batchTracking && item['id'] is int) {
                          return ListTile(
                            title: Text('$label'),
                            subtitle: subtitle.isEmpty ? null : Text(subtitle),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => InventoryBatchPage(
                                  api: widget.controller.api,
                                  summary: item,
                                  scopeHeaders: widget.scopeHeaders,
                                  cacheScope: widget.cachePrefix,
                                  offline: _offlineOnly || _usedSavedFallback,
                                ),
                              ),
                            ),
                          );
                        }
                        if (_crmGuidedSelling) {
                          return ListTile(
                            title: Text('$label'),
                            subtitle: subtitle.isEmpty ? null : Text(subtitle),
                            trailing:
                                widget.canEditGuidedFlow &&
                                    !_offlineOnly &&
                                    !_usedSavedFallback &&
                                    item['id'] is int
                                ? IconButton(
                                    tooltip: 'Edit $label',
                                    icon: const Icon(Icons.edit_outlined),
                                    onPressed: () =>
                                        _openGuidedFlow(flow: item),
                                  )
                                : null,
                          );
                        }
                        if (_crmQuoteApprovals) {
                          final quote = item['quote_id'];
                          final approver =
                              item['approver_user_id'] ?? item['approved_by'];
                          return ListTile(
                            title: Text(
                              quote == null ? '$label' : 'Quotation #$quote',
                            ),
                            subtitle: Text(
                              [
                                    item['status'],
                                    item['reason'],
                                    item['comments'],
                                    if (approver != null) 'Approver #$approver',
                                    if (item['submitted_at']
                                        case final String submitted)
                                      'Submitted $submitted',
                                    if (item['decided_at']
                                        case final String decided)
                                      'Decided $decided',
                                  ]
                                  .whereType<String>()
                                  .where((text) => text.isNotEmpty)
                                  .join('\n'),
                            ),
                            trailing: quote is int
                                ? const Icon(Icons.chevron_right)
                                : null,
                            onTap: quote is int
                                ? () => Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) =>
                                          _quotationDetails({'id': quote}),
                                    ),
                                  )
                                : null,
                          );
                        }
                        if (_warehouses) {
                          return ListTile(
                            title: Text('$label'),
                            subtitle: subtitle.isEmpty ? null : Text(subtitle),
                            trailing:
                                widget.canEditWarehouses &&
                                    !_offlineOnly &&
                                    !_usedSavedFallback &&
                                    item['id'] is int
                                ? IconButton(
                                    tooltip: 'Edit $label',
                                    icon: const Icon(LucideIcons.pencil),
                                    onPressed: () => _openWarehouseForm(item),
                                  )
                                : null,
                          );
                        }
                        if (_warehouseStock || _valuation || _stockSummary) {
                          final currency =
                              item['currency'] ?? 'Currency unavailable';
                          final product =
                              item[_warehouseStock ? 'stock_item_id' : 'id'];
                          final warehouse = _warehouseStock
                              ? item['warehouse_id']
                              : null;
                          return ListTile(
                            title: Text('$label'),
                            trailing: product is int
                                ? IconButton(
                                    tooltip: 'Stock ledger for $label',
                                    icon: const Icon(LucideIcons.bookOpen),
                                    onPressed: () => _openStockLedger({
                                      'product_id': '$product',
                                      if (warehouse is int)
                                        'warehouse_id': '$warehouse',
                                    }),
                                  )
                                : null,
                            subtitle: Text(
                              [
                                subtitle,
                                'Quantity ${item[_warehouseStock ? 'quantity' : 'current_quantity'] ?? '—'}',
                                if (_warehouseStock)
                                  'Average cost ${item['average_cost'] ?? '—'} $currency',
                                'Stock value ${item['stock_value'] ?? '—'} $currency'
                                    .trim(),
                                if (_stockSummary && _lowStock(item))
                                  'Low stock · reorder at ${item['reorder_threshold']}',
                              ].where((text) => text.isNotEmpty).join('\n'),
                            ),
                          );
                        }
                        if (_activityReport) {
                          final movement = item['last_movement_date'];
                          return ListTile(
                            title: Text('$label'),
                            subtitle: Text(
                              [
                                if (subtitle.isNotEmpty) subtitle,
                                if (widget.path!.endsWith(
                                  '/fast-slow-moving',
                                )) ...[
                                  'Quantity issued ${item['quantity_out'] ?? '—'}',
                                  switch (item['movement_class']) {
                                    'fast' => 'Fast moving',
                                    'slow' => 'Slow moving',
                                    'non_moving' => 'Non-moving',
                                    _ => 'Movement class unavailable',
                                  },
                                ] else if (movement != null) ...[
                                  'Last movement $movement',
                                  'Days since last movement ${item['age_days'] ?? '—'}',
                                ] else
                                  'No movement recorded',
                              ].join('\n'),
                            ),
                          );
                        }
                        final appointmentId = item['id'];
                        if (widget.query['kind'] == 'appointment' &&
                            appointmentId is int) {
                          return ListTile(
                            title: Text('$label'),
                            subtitle: subtitle.isEmpty ? null : Text(subtitle),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () => Navigator.of(context).push(
                              MaterialPageRoute<void>(
                                builder: (_) => _AppointmentDetails(
                                  controller: widget.controller,
                                  id: appointmentId,
                                  scopeHeaders: widget.scopeHeaders,
                                  onChanged: () {
                                    if (mounted) {
                                      setState(() {
                                        _records = _startLoad();
                                      });
                                    }
                                  },
                                ),
                              ),
                            ),
                          );
                        }
                        return ListTile(
                          title: Text('$label'),
                          subtitle: subtitle.isEmpty ? null : Text(subtitle),
                          trailing: _stockAlerts
                              ? Text(
                                  _stockNumber(item['current_quantity'])! <= 0
                                      ? 'Out of stock'
                                      : '${item['current_quantity']} left',
                                )
                              : null,
                          onTap:
                              (_inventory ||
                                      _stockAlerts ||
                                      widget.path == '/employees/' ||
                                      widget.path == '/srm/sales-orders' ||
                                      widget.path ==
                                          SalesEngagementPage.endpoint ||
                                      widget.path ==
                                          SalesBillingPlanPage.endpoint ||
                                      widget.path ==
                                          SalesContractPage.endpoint ||
                                      widget.path ==
                                          GstInvoicePage.listEndpoint ||
                                      widget.path == CrmLeadPage.endpoint ||
                                      _crmContacts ||
                                      _crmDeals ||
                                      _crmCustomers ||
                                      _crmTasks ||
                                      _crmQuotations ||
                                      widget.path ==
                                          FinancePartyPage.endpoint) &&
                                  item['id'] is int
                              ? () => Navigator.of(context).push(
                                  MaterialPageRoute<void>(
                                    builder: (_) => widget.path == '/employees/'
                                        ? _EmployeeDetailsPage(
                                            api: widget.controller.api,
                                            id: item['id'] as int,
                                          )
                                        : _crmQuotations
                                        ? _quotationDetails(item)
                                        : _crmTasks
                                        ? CrmTaskPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            scopeHeaders: widget.scopeHeaders,
                                            canEdit:
                                                _offlineOnly ||
                                                    _usedSavedFallback
                                                ? item['can_manage_tasks'] ==
                                                      true
                                                : _editableTaskProjects
                                                      .contains(
                                                        item['project_id'],
                                                      ),
                                            onChanged: _refresh,
                                          )
                                        : _crmCustomers
                                        ? CrmCustomerPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            scopeHeaders: widget.scopeHeaders,
                                            onChanged: _refreshCrmRecords,
                                          )
                                        : _crmDeals
                                        ? CrmDealPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            scopeHeaders: widget.scopeHeaders,
                                            canMove: widget.canMoveDeals,
                                            onChanged: _refreshCrmRecords,
                                            quotationBuilder:
                                                !widget.canCreateQuotes
                                                ? null
                                                : (quote) => CrmQuotationPage(
                                                    api: widget.controller.api,
                                                    summary: quote,
                                                    offline: false,
                                                    cacheScope:
                                                        widget.cachePrefix,
                                                    scopeHeaders:
                                                        widget.scopeHeaders,
                                                    canManage:
                                                        widget.canManageQuotes,
                                                    canCancel:
                                                        widget.canCancelQuotes,
                                                    canApprove:
                                                        widget.canApproveQuotes,
                                                    canSend:
                                                        widget.canSendQuotes,
                                                    canCreateRevision:
                                                        widget.canCreateQuotes,
                                                    canViewSalesOrder: widget
                                                        .canViewQuoteSalesOrders,
                                                  ),
                                          )
                                        : _crmContacts
                                        ? CrmContactPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            scopeHeaders: widget.scopeHeaders,
                                            canEdit: widget.canEditContacts,
                                            onSaved: _refreshCrmRecords,
                                          )
                                        : widget.path == CrmLeadPage.endpoint
                                        ? CrmLeadPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            offlineEdits: _crmEdits,
                                            onSaved: () {
                                              if (mounted) {
                                                setState(() {
                                                  _records = _startLoad();
                                                });
                                              }
                                            },
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                          )
                                        : widget.path ==
                                              SalesBillingPlanPage.endpoint
                                        ? SalesBillingPlanPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            scopeHeaders: widget.scopeHeaders,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            canEdit: widget.canEditOrders,
                                            canApprove: widget.canIssueInvoices,
                                            canCreateInvoice:
                                                widget.canCreateOrderInvoices,
                                            canExportInvoice:
                                                widget.canExportSalesDocuments,
                                            onChanged: _refresh,
                                          )
                                        : widget.path ==
                                              SalesEngagementPage.endpoint
                                        ? SalesEngagementPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            scopeHeaders: widget.scopeHeaders,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            canEdit: widget.canEditOrders,
                                            canApproveInvoices:
                                                widget.canIssueInvoices,
                                            canCreateInvoices:
                                                widget.canCreateOrderInvoices,
                                            canExportInvoices:
                                                widget.canExportSalesDocuments,
                                            onChanged: _refresh,
                                          )
                                        : widget.path ==
                                              SalesContractPage.endpoint
                                        ? SalesContractPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            scopeHeaders: widget.scopeHeaders,
                                            cacheScope: widget.cachePrefix,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            canEdit: widget.canEditOrders,
                                            onChanged: _refresh,
                                          )
                                        : widget.path == '/srm/sales-orders'
                                        ? SalesOrderPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            canEdit: widget.canEditOrders,
                                            canManageBilling:
                                                widget.canEditWarehouses,
                                            canApproveInvoices:
                                                widget.canIssueInvoices,
                                            canExportInvoices:
                                                widget.canExportSalesDocuments,
                                            invoiceBuilder:
                                                widget.canCreateOrderInvoices
                                                ? (invoice) => GstInvoicePage(
                                                    api: widget.controller.api,
                                                    id: invoice['id'] as int,
                                                    summary: invoice,
                                                    scopeHeaders:
                                                        widget.scopeHeaders,
                                                    cacheScope:
                                                        widget.cachePrefix,
                                                    canEdit: true,
                                                    canExport: widget
                                                        .canExportSalesDocuments,
                                                    canIssue:
                                                        widget.canIssueInvoices,
                                                  )
                                                : null,
                                            onChanged: _refresh,
                                            cacheScope: widget.cachePrefix,
                                            scopeHeaders: widget.scopeHeaders,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                          )
                                        : widget.path ==
                                              GstInvoicePage.listEndpoint
                                        ? GstInvoicePage(
                                            api: widget.controller.api,
                                            id: item['id'] as int,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            scopeHeaders: widget.scopeHeaders,
                                            onChanged: _refresh,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                            canExport:
                                                widget.canExportSalesDocuments,
                                            canIssue: widget.canIssueInvoices,
                                            canEdit:
                                                widget
                                                        .controller
                                                        .user
                                                        ?.isSuperuser ==
                                                    true ||
                                                widget
                                                        .controller
                                                        .user
                                                        ?.permissions
                                                        .any(
                                                          const {
                                                            'srm_invoice_create',
                                                            'srm_admin',
                                                          }.contains,
                                                        ) ==
                                                    true,
                                          )
                                        : widget.path ==
                                              FinancePartyPage.endpoint
                                        ? FinancePartyPage(
                                            api: widget.controller.api,
                                            id: item['id'] as int,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            scopeHeaders: widget.scopeHeaders,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
                                          )
                                        : InventoryProductPage(
                                            api: widget.controller.api,
                                            summary: item,
                                            cacheScope: widget.cachePrefix,
                                            scopeHeaders: widget.scopeHeaders,
                                            canRecordStock:
                                                _inventory &&
                                                widget.canCreateOrder,
                                            canEditProduct:
                                                _inventory &&
                                                widget.canEditInventoryProducts,
                                            onStockChanged: _refreshStockLists,
                                            offline:
                                                _offlineOnly ||
                                                _usedSavedFallback,
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

class _EmployeeDetailsPage extends StatefulWidget {
  const _EmployeeDetailsPage({required this.api, required this.id});

  final ApiClient api;
  final int id;

  @override
  State<_EmployeeDetailsPage> createState() => _EmployeeDetailsPageState();
}

class _EmployeeDetailsPageState extends State<_EmployeeDetailsPage> {
  late Future<Json> _employee = _load();
  Future<List<(String, String)?>>? _organizationLabels;

  Future<Json> _load() async {
    final revision = widget.api.sessionRevision;
    final employee =
        await widget.api.request('GET', '/employees/${widget.id}') as Json;
    if (revision != widget.api.sessionRevision) {
      throw ApiFailure('Your session ended. Sign in again.', 401);
    }
    _organizationLabels = Future.wait([
      if (employee['department_id'] case final int id)
        _lookupLabel('Department', '/company/departments/', id, revision, {
          if (employee['branch_id'] case final int branch) 'branch_id': branch,
        }),
      if (employee['designation_id'] case final int id)
        _lookupLabel('Designation', '/company/designations/', id, revision, {
          if (employee['department_id'] case final int department)
            'department_id': department,
        }),
    ]);
    return employee;
  }

  Future<(String, String)?> _lookupLabel(
    String label,
    String path,
    int id,
    int revision,
    Map<String, dynamic> query,
  ) async {
    try {
      final items = await widget.api.request('GET', path, query: query);
      if (revision != widget.api.sessionRevision || items is! List) return null;
      final row = items
          .whereType<Json>()
          .where((item) => item['id'] == id)
          .firstOrNull;
      if (row?['name'] case final String name when name.isNotEmpty) {
        return (label, name);
      }
    } catch (_) {
      // Some directory users cannot view company configuration.
    }
    return null;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Employee profile')),
    body: FutureBuilder<Json>(
      future: _employee,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return ListTile(
            title: Text('${snapshot.error}'),
            trailing: TextButton(
              onPressed: () => setState(() {
                _employee = _load();
              }),
              child: const Text('Retry'),
            ),
          );
        }
        final employee = snapshot.requireData;
        final name = [
          employee['first_name'],
          employee['middle_name'],
          employee['last_name'],
        ].whereType<String>().where((part) => part.isNotEmpty).join(' ');
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              name.isEmpty ? 'Employee' : name,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            FutureBuilder<List<(String, String)?>>(
              future: _organizationLabels,
              builder: (context, labels) => Column(
                children: [
                  for (final (label, name) in (labels.data ?? []).nonNulls)
                    ListTile(title: Text(label), subtitle: Text(name)),
                ],
              ),
            ),
            for (final field in const {
              'employee_id': 'Employee code',
              'work_email': 'Work email',
              'office_extension': 'Office extension',
              'employment_type': 'Employment type',
              'work_location': 'Work location',
              'date_of_joining': 'Date of joining',
              'status': 'Status',
            }.entries)
              if (employee[field.key] case final String value
                  when value.isNotEmpty)
                ListTile(
                  title: Text(field.value),
                  subtitle: SelectableText(value),
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
    this.cacheScope,
    this.scopeHeaders = const {},
    this.canRecordStock = false,
    this.canEditProduct = false,
    this.onStockChanged,
  });
  final ApiClient api;
  final Json summary;
  final bool offline;
  final String? cacheScope;
  final Map<String, String> scopeHeaders;
  final bool canRecordStock;
  final bool canEditProduct;
  final ValueChanged<Set<int>>? onStockChanged;

  @override
  State<InventoryProductPage> createState() => _InventoryProductPageState();
}

class _InventoryProductPageState extends State<InventoryProductPage> {
  Json? _saved;
  late final _editorQueue = widget.canEditProduct && widget.cacheScope != null
      ? InventoryOfflineCreates(
          widget.cacheScope!,
          invalidate: SuiteReadCache.invalidate,
        )
      : null;
  late var _savedEdit = _readSavedEdit();
  bool _savingEdit = false;

  Future<Json?> _readSavedEdit() async => (await _editorQueue?.entries())
      ?.where((row) => row['product_id'] == widget.summary['id'])
      .firstOrNull;
  late bool _offline = widget.offline;
  late Future<Json?> _product = _load();

  static const _fields = {
    'sku': 'SKU',
    'unit_code': 'Unit',
    'current_quantity': 'On hand',
    'reorder_level': 'Reorder level',
    'barcode': 'Barcode',
    'category_name': 'Category',
    'hsn_code': 'HSN code',
    'sales_rate': 'Sales price',
    'gst_rate': 'GST rate (%)',
    'description': 'Description',
  };

  Future<Json?> _load({bool reconnect = false}) async {
    final api = widget.api;
    final revision = api.sessionRevision;
    try {
      final result = await loadCrmDetail(
        api: api,
        path: '/srm/inventory/items/${widget.summary['id']}',
        scope: widget.cacheScope,
        headers: widget.scopeHeaders,
        offline: _offline && !reconnect,
        reuseFresh:
            !reconnect && !widget.canRecordStock && !widget.canEditProduct,
        onCached: (saved) {
          if (mounted) setState(() => _saved = saved);
        },
        project: (data) => {
          for (final field in [
            'item_name',
            'name',
            'updated_at',
            ..._fields.keys,
          ])
            field: data[field],
          'balances': [
            for (final row
                in (data['balances'] as List? ?? []).whereType<Json>())
              {
                for (final field in const [
                  'warehouse_id',
                  'warehouse_name',
                  'quantity',
                ])
                  field: row[field],
              },
          ],
          'ledger': [
            for (final row in (data['ledger'] as List? ?? []).whereType<Json>())
              {
                for (final field in const [
                  'movement_number',
                  'movement_type',
                  'movement_date',
                  'warehouse_name',
                  'quantity_in',
                  'quantity_out',
                ])
                  field: row[field],
              },
          ],
        },
      );
      if (!mounted || revision != api.sessionRevision) return null;
      if (!result.live) {
        setState(() => _saved = result.record);
        return null;
      }
      _offline = false;
      return result.record;
    } on ApiFailure catch (error) {
      if (mounted && const {401, 403, 404}.contains(error.status)) {
        setState(() => _saved = null);
      }
      rethrow;
    }
  }

  void _refresh() => setState(() {
    _product = _load(reconnect: true);
    _savedEdit = _readSavedEdit();
  });

  Future<void> _editProduct(
    Json product, {
    required bool offline,
    Json? rejected,
  }) async {
    final queue = _editorQueue!;
    final revision = widget.api.sessionRevision;
    if (_savingEdit) return;
    setState(() => _savingEdit = true);
    try {
      final branches = await queue.writableBranches(
        widget.api,
        offline: offline,
      );
      if (!mounted || widget.api.sessionRevision != revision) return;
      final rejectedBranch = rejected?['branch'] as int?;
      if (rejectedBranch != null &&
          !branches.any((row) => row['id'] == rejectedBranch)) {
        throw StateError('The saved edit’s branch is no longer writable.');
      }
      final selected = int.tryParse(
        widget.scopeHeaders['X-Suite-Branch'] ?? '',
      );
      final branch =
          rejectedBranch ??
          (branches.any((row) => row['id'] == selected)
              ? selected
              : branches.length == 1
              ? branches.single['id'] as int
              : await showDialog<int>(
                  context: context,
                  builder: (context) => SimpleDialog(
                    title: const Text('Choose a writable branch'),
                    children: [
                      for (final row in branches)
                        SimpleDialogOption(
                          onPressed: () => Navigator.pop(context, row['id']),
                          child: Text('${row['name']}'),
                        ),
                      if (branches.isEmpty)
                        const ListTile(
                          title: Text('No writable branches available'),
                        ),
                    ],
                  ),
                ));
      if (!mounted ||
          branch == null ||
          widget.api.sessionRevision != revision) {
        return;
      }
      final id = widget.summary['id'] as int;
      final reference = rejected == null
          ? product
          : await widget.api.request(
                  'GET',
                  '${InventoryOfflineCreates.itemsEndpoint}/$id',
                  scopeHeaders: {
                    ...widget.scopeHeaders,
                    'X-Suite-Organization': queue.organizationId,
                    'X-Suite-Branch': '$branch',
                  },
                )
                as Json;
      if (!mounted || widget.api.sessionRevision != revision) return;
      if (!reference.containsKey('updated_at')) {
        throw StateError('The product version is unavailable.');
      }
      final changes = await showDialog<Json>(
        context: context,
        builder: (_) => _InventoryProductEditDialog(
          product: reference,
          offline: offline,
          proposed: rejected?['changes'] as Json?,
        ),
      );
      if (!mounted ||
          changes == null ||
          widget.api.sessionRevision != revision) {
        return;
      }
      if (rejected != null && changes.isEmpty) {
        await queue.discard(rejected['operation'] as String);
        if (mounted && widget.api.sessionRevision == revision) _refresh();
        return;
      }
      await queue.enqueueEdit(
        productId: widget.summary['id'] as int,
        name: '${reference['item_name'] ?? reference['name']}',
        sku: '${reference['sku'] ?? ''}',
        branchId: branch,
        changes: {...changes, 'expected_updated_at': reference['updated_at']},
        replaceRejected: rejected?['operation'] as String?,
      );
      if (!offline && widget.api.sessionRevision == revision) {
        await queue.sync(widget.api, onlyProduct: widget.summary['id'] as int);
      }
      if (!mounted || widget.api.sessionRevision != revision) return;
      if (offline) {
        setState(() {
          _savedEdit = _readSavedEdit();
        });
      } else {
        _refresh();
      }
    } catch (error) {
      if (mounted && widget.api.sessionRevision == revision) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _savingEdit = false);
    }
  }

  Future<void> _syncProductEdit() async {
    if (_savingEdit) return;
    setState(() => _savingEdit = true);
    try {
      await _editorQueue!.sync(
        widget.api,
        onlyProduct: widget.summary['id'] as int,
        reportTemporaryFailure: true,
      );
      if (mounted) _refresh();
    } on ApiFailure catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _savingEdit = false);
    }
  }

  Future<void> _recordStock() async {
    final id = widget.summary['id'];
    if (id is! int) return;
    final session = widget.api.sessionRevision;
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => InventoryStockMovementPage(
          api: widget.api,
          productId: id,
          scopeHeaders: widget.scopeHeaders,
          cacheScope: widget.cacheScope,
          offline: _offline,
        ),
      ),
    );
    if (mounted && changed == true && session == widget.api.sessionRevision) {
      widget.onStockChanged?.call({id});
      _refresh();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Product details'),
      actions: [
        IconButton(
          tooltip: 'Refresh product',
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<Json?>(
      future: _product,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${snapshot.error}'),
                TextButton(onPressed: _refresh, child: const Text('Retry')),
              ],
            ),
          );
        }
        final pending = snapshot.connectionState != ConnectionState.done;
        final details = (pending ? null : snapshot.data) ?? _saved;
        final data = details ?? widget.summary;
        final ledger = (data['ledger'] as List? ?? []).whereType<Json>();
        final balances = (data['balances'] as List? ?? []).whereType<Json>();
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '${data['item_name'] ?? data['name'] ?? 'Product'}',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (pending) const LinearProgressIndicator(),
            if (_editorQueue != null && !pending)
              FutureBuilder<Json?>(
                future: _savedEdit,
                builder: (context, edit) {
                  if (edit.connectionState != ConnectionState.done ||
                      edit.hasError) {
                    return const SizedBox.shrink();
                  }
                  if (edit.data case final entry?) {
                    final changes = entry['changes'] as Json;
                    final rejected = entry['error'] as String?;
                    return ListTile(
                      title: Text(
                        rejected == null
                            ? 'Product edit saved · awaiting sync'
                            : 'Saved product edit needs review',
                      ),
                      subtitle: Text(
                        rejected ??
                            [
                              if (changes['item_name'] case final String name)
                                'Name: $name',
                              if (changes['description']
                                  case final String notes)
                                'Description: $notes',
                              if (changes['reorder_level']
                                  case final String level)
                                'Reorder level: $level',
                            ].join('\n'),
                      ),
                      trailing: TextButton(
                        onPressed: _savingEdit
                            ? null
                            : rejected == null
                            ? _syncProductEdit
                            : () => _editProduct(
                                data,
                                offline: false,
                                rejected: entry,
                              ),
                        child: Text(
                          rejected == null ? 'Sync now' : 'Review edit',
                        ),
                      ),
                    );
                  }
                  if (details == null || !details.containsKey('updated_at')) {
                    return const SizedBox.shrink();
                  }
                  return OutlinedButton(
                    onPressed: _savingEdit
                        ? null
                        : () => _editProduct(
                            details,
                            offline: snapshot.data == null,
                          ),
                    child: const Text('Edit product details'),
                  );
                },
              ),
            if (widget.canRecordStock &&
                !pending &&
                (snapshot.data != null ||
                    (_offline && widget.cacheScope != null)))
              OutlinedButton.icon(
                onPressed: _recordStock,
                icon: const Icon(LucideIcons.packagePlus),
                label: const Text('Record stock movement'),
              ),
            if (!pending && snapshot.data == null)
              ListTile(
                title: Text(
                  '${_offline ? 'Offline · ' : ''}'
                  '${details == null ? 'Saved product summary' : 'Saved product details'}',
                ),
                trailing: TextButton(
                  onPressed: _refresh,
                  child: Text(_offline ? 'Reconnect' : 'Refresh'),
                ),
              ),
            for (final field in _fields.entries)
              if (data[field.key] != null)
                ListTile(
                  title: Text(field.value),
                  trailing: Text('${data[field.key]}'),
                ),
            if (balances.isNotEmpty) ...[
              const Divider(),
              Text(
                'Warehouse balances',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              for (final balance in balances)
                ListTile(
                  title: Text(
                    balance['warehouse_name']?.toString() ??
                        "Warehouse #${balance['warehouse_id']}",
                  ),
                  trailing: Text(
                    [
                      balance['quantity'] ?? '—',
                      if (data['unit_code'] != null) data['unit_code'],
                    ].join(' '),
                  ),
                ),
            ],
            if (details != null) ...[
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
                    [
                      if (row['warehouse_name'] != null) row['warehouse_name'],
                      if (row['movement_date'] != null) row['movement_date'],
                      'In ${row['quantity_in'] ?? 0}',
                      'Out ${row['quantity_out'] ?? 0}',
                    ].join(' · '),
                  ),
                ),
            ],
          ],
        );
      },
    ),
  );
}

class _InventoryProductEditDialog extends StatefulWidget {
  const _InventoryProductEditDialog({
    required this.product,
    required this.offline,
    this.proposed,
  });

  final Json product;
  final bool offline;
  final Json? proposed;

  @override
  State<_InventoryProductEditDialog> createState() =>
      _InventoryProductEditDialogState();
}

class _InventoryProductEditDialogState
    extends State<_InventoryProductEditDialog> {
  final _form = GlobalKey<FormState>();
  late final _changes = <String, dynamic>{
    for (final field in ['item_name', 'description', 'reorder_level'])
      if (widget.proposed?[field] case final String value
          when value != '${widget.product[field] ?? ''}')
        field: value,
  };

  String? _current(String field) => widget.proposed?.containsKey(field) == true
      ? 'Current: ${widget.product[field] ?? '—'}'
      : null;

  void _track(String field, String value) {
    final text = value.trim();
    if (text == '${widget.product[field] ?? ''}') {
      _changes.remove(field);
    } else {
      _changes[field] = text;
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(
      widget.proposed == null ? 'Edit product details' : 'Review product edit',
    ),
    scrollable: true,
    content: Form(
      key: _form,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextFormField(
            initialValue:
                '${widget.proposed?['item_name'] ?? widget.product['item_name'] ?? ''}',
            maxLength: 220,
            decoration: InputDecoration(
              labelText: 'Product name',
              helperText: _current('item_name'),
            ),
            validator: (value) =>
                (value ?? '').trim().isEmpty ? 'Enter a product name' : null,
            onChanged: (value) => _track('item_name', value),
          ),
          TextFormField(
            initialValue:
                '${widget.proposed?['description'] ?? widget.product['description'] ?? ''}',
            maxLength: 4000,
            maxLines: 3,
            decoration: InputDecoration(
              labelText: 'Description',
              helperText: _current('description'),
            ),
            onChanged: (value) => _track('description', value),
          ),
          TextFormField(
            initialValue:
                '${widget.proposed?['reorder_level'] ?? widget.product['reorder_level'] ?? 0}',
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: 'Reorder level',
              helperText: _current('reorder_level'),
            ),
            validator: (value) =>
                RegExp(r'^\d{1,11}(\.\d{1,3})?$').hasMatch(value?.trim() ?? '')
                ? null
                : 'Enter a nonnegative amount with up to 3 decimal places',
            onChanged: (value) => _track('reorder_level', value),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
      if (widget.proposed != null)
        TextButton(
          onPressed: () => Navigator.pop(context, <String, dynamic>{}),
          child: const Text('Keep server values'),
        ),
      FilledButton(
        onPressed: () {
          if (_form.currentState!.validate()) {
            Navigator.pop(context, _changes.isEmpty ? null : _changes);
          }
        },
        child: Text(widget.offline ? 'Save edit offline' : 'Save changes'),
      ),
    ],
  );
}
