import 'package:flutter/foundation.dart';

import 'core/api_client.dart';
import 'core/models.dart';
import 'features/pms_repository.dart';

class AppController extends ChangeNotifier {
  AppController(this.api) : repository = PmsRepository(api) {
    api.onExpired = () {
      _reset();
      notifyListeners();
    };
  }
  final ApiClient api;
  final PmsRepository repository;
  SessionUser? user;
  List<Workspace> workspaces = [];
  Workspace? selected;
  Overview? overview;
  String? error, mfaToken;
  bool loading = true, busy = false;
  int _revision = 0;

  void _reset() {
    _revision++;
    user = null;
    workspaces = [];
    selected = null;
    overview = null;
    mfaToken = null;
    loading = false;
    busy = false;
  }

  Future<void> start() async {
    try {
      await api.restore();
      if (api.hasSession) await loadAccount();
    } catch (e) {
      error = '$e';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> authenticate(
    String email,
    String password, {
    String? code,
    bool recovery = false,
  }) async {
    if (busy) return;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final result = mfaToken == null
          ? await api.login(email.trim(), password)
          : await api.request(
                  'POST',
                  '/auth/mfa/verify',
                  auth: false,
                  data: {
                    'mfa_token': mfaToken,
                    'code': code?.trim(),
                    'method': recovery ? 'recovery' : 'totp',
                    'trust_device': false,
                  },
                )
                as Json;
      if (result['mfa_required'] == true) {
        mfaToken = result['mfa_token'] as String;
      } else {
        await api.acceptTokens(result);
        mfaToken = null;
        await loadAccount();
      }
    } catch (e) {
      error = '$e';
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  void cancelMfa() {
    mfaToken = null;
    error = null;
    notifyListeners();
  }

  Future<void> loadAccount() async {
    final revision = ++_revision;
    loading = true;
    error = null;
    overview = null;
    notifyListeners();
    try {
      final account = await repository.me();
      final items = await repository.workspaces();
      if (revision != _revision) return;
      user = account;
      workspaces = items;
      final previousId = selected?.id;
      selected =
          items.where((w) => w.id == previousId).firstOrNull ??
          items.firstOrNull;
      if (selected != null) await selectWorkspace(selected!);
    } catch (e) {
      if (revision == _revision) error = '$e';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> selectWorkspace(Workspace workspace) async {
    final revision = ++_revision;
    selected = workspace;
    overview = null;
    error = null;
    loading = true;
    notifyListeners();
    try {
      final result = await repository.overview(workspace.id);
      if (revision != _revision) return;
      overview = result;
      selected = Workspace(workspace.id, workspace.name, result.role);
    } catch (e) {
      if (revision == _revision) {
        error = '$e';
        // Do not leave stale editing capabilities enabled after an access failure.
        overview = null;
      }
    } finally {
      if (revision == _revision) {
        loading = false;
        notifyListeners();
      }
    }
  }

  Future<WorkTask?> taskDetails(int id) async {
    if (busy) return null;
    final revision = _revision;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final task = await repository.task(id);
      return revision == _revision ? task : null;
    } catch (e) {
      if (revision == _revision) error = '$e';
      return null;
    } finally {
      if (revision == _revision) {
        busy = false;
        notifyListeners();
      }
    }
  }

  Future<bool> mutate(Future<void> Function() action) async {
    if (busy) return false;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await action();
      if (selected != null) await selectWorkspace(selected!);
      return true;
    } catch (e) {
      error = '$e';
      if (e is ApiFailure && const {403, 404}.contains(e.status)) {
        overview = null;
      }
      return false;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  Future<void> signOut() async {
    if (busy) return;
    busy = true;
    notifyListeners();
    try {
      await api.logout();
    } catch (_) {
      /* Local credentials are cleared even when the server is offline. */
    } finally {
      _reset();
      error = null;
      notifyListeners();
    }
  }
}
