import 'dart:io';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:uuid/uuid.dart';
import '../app_controller.dart';
import '../core/models.dart';
import '../core/api_client.dart';
import 'contract_form.dart';
import 'pms_catalog.dart';
import 'pms_native_views.dart';
import 'pms_board_page.dart';
import 'pms_planner_page.dart';

class PmsFeatureHub extends StatefulWidget {
  const PmsFeatureHub({
    super.key,
    required this.controller,
    this.project,
    this.task,
  });
  final AppController controller;
  final Project? project;
  final WorkTask? task;
  @override
  State<PmsFeatureHub> createState() => _PmsFeatureHubState();
}

class _PmsFeatureHubState extends State<PmsFeatureHub> {
  final _catalog = PmsCatalog.load();
  String _search = '';
  Project? _project;
  Future<void> _open(
    PmsOperation operation,
    Map<String, dynamic> scope,
    Json initial,
  ) async {
    final catalog = await _catalog;
    if (!mounted) return;
    Widget page;
    if (operation.method == 'GET' &&
        operation.path == '/project-management/planner') {
      page = PmsPlannerPage(
        controller: widget.controller,
        projectId: scope['project_id'],
        catalog: catalog,
        openAction: _open,
      );
    } else if (operation.method == 'GET' &&
        operation.path.endsWith('/board') &&
        scope['project_id'] != null) {
      page = PmsBoardPage(
        controller: widget.controller,
        projectId: scope['project_id'],
        catalog: catalog,
        openAction: _open,
      );
    } else if (operation.path.startsWith('/project-management/timer')) {
      page = PmsTimerPage(
        controller: widget.controller,
        projectId: scope['project_id'] as int?,
        taskId: scope['task_id'] as int?,
      );
    } else if (operation.method == 'GET' &&
        operation.path ==
            '/project-management/workspaces/{wid}/chat/conversations') {
      page = PmsMessagesPage(
        controller: widget.controller,
        workspaceId: scope['workspace_id'] as int,
        catalog: catalog,
        openAction: _open,
      );
    } else {
      page = PmsOperationPage(
        controller: widget.controller,
        catalog: catalog,
        operation: operation,
        scope: scope,
        initial: initial,
      );
    }
    await Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  @override
  void initState() {
    super.initState();
    _project =
        widget.project ??
        widget.controller.overview?.projects
            .where((p) => p.id == widget.task?.projectId)
            .firstOrNull;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.task?.key ?? 'PMS features')),
    body: FutureBuilder<PmsCatalog>(
      future: _catalog,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Center(child: Text('${snapshot.error}'));
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final catalog = snapshot.data!;
        final scope = baseContext(
          widget.controller,
          project: _project,
          task: widget.task,
        );
        final operations = catalog.operations
            .where(
              (o) =>
                  !o.internal &&
                  (!o.restricted ||
                      widget.controller.user?.isSuperuser == true) &&
                  (!o.path.startsWith('/project-management/timer/')) &&
                  (widget.task == null ||
                      o.path.contains('{task_id}') ||
                      o.path.contains('/comments/') ||
                      o.path.contains('/checklist/') ||
                      o.path.contains('/task-dependencies/')) &&
                  '${o.area} ${o.title} ${o.path.split('/').where((s) => !s.startsWith('{')).join(' ')}'
                      .toLowerCase()
                      .contains(_search.toLowerCase()),
            )
            .toList();
        final areas = operations.map((o) => o.area).toSet().toList()..sort();
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  if (widget.task == null)
                    DropdownButtonFormField<int>(
                      initialValue: _project?.id,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Project scope',
                      ),
                      items: [
                        const DropdownMenuItem<int>(
                          value: null,
                          child: Text('Workspace-wide'),
                        ),
                        ...?widget.controller.overview?.projects.map(
                          (p) => DropdownMenuItem(
                            value: p.id,
                            child: Text(p.name),
                          ),
                        ),
                      ],
                      onChanged: (id) => setState(
                        () => _project = widget.controller.overview?.projects
                            .where((p) => p.id == id)
                            .firstOrNull,
                      ),
                    ),
                  const SizedBox(height: 12),
                  TextField(
                    decoration: const InputDecoration(
                      labelText: 'Find a feature',
                      prefixIcon: Icon(Icons.search),
                    ),
                    onChanged: (s) => setState(() => _search = s),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                key: const PageStorageKey('pms-features'),
                children: [
                  for (final area in areas)
                    ExpansionTile(
                      key: ValueKey('$area-$_search'),
                      title: Text(area),
                      initiallyExpanded: _search.isNotEmpty,
                      children: operations
                          .where((o) => o.area == area)
                          .map(
                            (o) => ListTile(
                              leading: Icon(
                                !o.available
                                    ? Icons.cloud_off
                                    : o.download
                                    ? Icons.download_outlined
                                    : o.method == 'GET'
                                    ? Icons.view_list_outlined
                                    : o.method == 'DELETE'
                                    ? Icons.delete_outline
                                    : Icons.edit_outlined,
                              ),
                              title: Text(_operationLabel(o)),
                              subtitle: !o.available
                                  ? const Text(
                                      'Not available on this deployment',
                                    )
                                  : !o.allowed(widget.controller)
                                  ? const Text(
                                      'Your current role is read-only for this action',
                                    )
                                  : null,
                              enabled:
                                  o.available && o.allowed(widget.controller),
                              onTap: () => _open(o, scope, {}),
                            ),
                          )
                          .toList(),
                    ),
                ],
              ),
            ),
          ],
        );
      },
    ),
  );
}

String _operationLabel(PmsOperation op) {
  const vague = {
    'Listing',
    'Detail',
    'Create',
    'Edit',
    'Save',
    'History',
    'Preview',
    'Restore',
    'Permanent',
    'Trash',
    'Query',
    'Start',
    'Stop',
    'Download',
    'Export',
    'Responses',
    'Read',
    'Mute',
    'Join',
    'Send',
    'Cancel Upload',
    'Draft',
    'Policy Update',
    'Full Policy',
    'Full Download',
    'Read All',
    'Revoke',
    'Accept',
    'Preferences',
    'Connections',
    'Sources',
    'Library',
  };
  if (!vague.contains(op.title)) return op.title;
  final parts = op.path
      .split('/')
      .where((p) => p.isNotEmpty && !p.startsWith('{'))
      .toList();
  final resource = parts.length > 1
      ? parts[1] == 'workspaces' && parts.length > 2
            ? parts[2]
            : parts[1]
      : 'work';
  return '${op.title} · ${fieldLabel(resource.replaceAll('-', '_'))}';
}

class PmsOperationPage extends StatefulWidget {
  const PmsOperationPage({
    super.key,
    required this.controller,
    required this.catalog,
    required this.operation,
    required this.scope,
    this.initial = const {},
  });
  final AppController controller;
  final PmsCatalog catalog;
  final PmsOperation operation;
  final Map<String, dynamic> scope;
  final Json initial;
  @override
  State<PmsOperationPage> createState() => _PmsOperationPageState();
}

class _PmsOperationPageState extends State<PmsOperationPage> {
  Json _body = {}, _query = {}, _path = {};
  Json _initial = {};
  int _recordGeneration = 0;
  bool _editUnavailable = false;
  dynamic _result;
  String? _error, _notice;
  bool _loading = false, _showFilters = false, _sharing = false;
  List<int>? _download;
  String _filename = 'pms-document';
  final _formKey = GlobalKey<FormState>();
  final _formScroll = ScrollController();
  void _revealStatus() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _formScroll.hasClients) _formScroll.jumpTo(0);
    });
  }

  @override
  void dispose() {
    _formScroll.dispose();
    super.dispose();
  }

  PmsOperation get op => widget.operation;
  bool get _stableTypeName =>
      op.method == 'PUT' &&
      op.path == '/project-management/task-types/{type_id}';
  bool get _taskTagAdd =>
      op.method == 'POST' &&
      op.path == '/project-management/tasks/{task_id}/tags';
  Json get _formBody => !_stableTypeName || _initial['name'] == null
      ? op.body
      : {
          ...op.body,
          'properties': {
            ...op.body['properties'],
            'name': {...op.body['properties']['name'], 'readOnly': true},
          },
        };
  AppController get c => widget.controller;
  Json _seedFields(Json fields, Json record) => {
    for (final key in fields.keys)
      if (record.containsKey(key))
        if (record[key] != null || (fields[key] as Map)['nullable'] == true)
          key: record[key]
        else if ((fields[key] as Map).containsKey('default'))
          key: fields[key]['default'],
  };
  bool get _canHydrate =>
      const {'PATCH', 'PUT'}.contains(op.method) &&
      widget.catalog.find('GET', op.path) != null;
  void _acceptRecord(Json record) {
    _initial = record;
    _body = {};
    final fields = Map<String, dynamic>.from(op.body['properties'] ?? {});
    if (op.method == 'PUT') {
      _body.addAll(_seedFields(fields, record));
    }
    for (final key in op.body['required'] as List? ?? []) {
      if (record[key] != null) _body[key] = record[key];
      if (widget.scope[key] != null) _body[key] = widget.scope[key];
    }
    _recordGeneration++;
  }

  Future<void> _hydrate() async {
    if (!_canHydrate ||
        op.parameters
            .where((p) => p['in'] == 'path')
            .any((p) => ({...widget.scope, ..._path})[p['name']] == null)) {
      return;
    }
    setState(() {
      _loading = true;
      _editUnavailable = true;
    });
    try {
      final path = op.path.replaceAllMapped(
        RegExp(r'\{([^}]+)\}'),
        (m) => Uri.encodeComponent('${({...widget.scope, ..._path})[m[1]]}'),
      );
      final row = await c.api.request('GET', path);
      if (mounted) {
        setState(() {
          _acceptRecord(Map<String, dynamic>.from(row));
          _editUnavailable = false;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => _error =
              'Could not load the current record. Reload before saving. $e',
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Map<String, dynamic> get scope => {
    ...widget.scope,
    ..._path,
    ..._body,
    'operation_path': op.path,
  };
  Json _parameterSchema(String location) {
    final fields = <String, dynamic>{}, required = <String>[];
    for (final p in op.parameters.where((p) => p['in'] == location)) {
      if (location == 'path' && widget.scope[p['name']] != null) continue;
      if (location == 'query' &&
          op.mutation &&
          p['required'] != true &&
          (op.body['properties'] as Map? ?? {}).containsKey(p['name'])) {
        continue;
      }
      fields[p['name']] = p['schema'];
      if (p['required'] == true) required.add(p['name'] as String);
    }
    return {'type': 'object', 'properties': fields, 'required': required};
  }

  @override
  void initState() {
    super.initState();
    _initial = Map<String, dynamic>.from(widget.initial);
    for (final p in op.parameters) {
      final schema = p['schema'] as Json, key = p['name'] as String;
      final alias = const {
        'projectId': 'project_id',
        'workspaceId': 'workspace_id',
        'taskId': 'task_id',
      }[key];
      final value =
          widget.scope[key] ?? widget.scope[alias] ?? schema['default'];
      if (value != null) {
        if (p['in'] == 'path') {
          _path[key] = value;
        } else if (p['in'] == 'query') {
          _query[key] = value;
        }
      }
    }
    final fields = Map<String, dynamic>.from(op.body['properties'] ?? {});
    if (op.method == 'PUT') {
      _body.addAll(_seedFields(fields, widget.initial));
    }
    for (final key in (op.body['required'] as List? ?? [])) {
      if (widget.initial[key] != null) _body[key] = widget.initial[key];
      if (widget.scope[key] != null) _body[key] = widget.scope[key];
      if (key == 'base_version' && widget.initial['version'] != null) {
        _body[key] = widget.initial['version'];
      }
      if ((fields[key] as Map?)?['format'] == 'uuid') {
        _body[key] = const Uuid().v4();
      }
    }
    if (op.method == 'POST') {
      for (final entry in fields.entries) {
        if (entry.value is Map && (entry.value as Map).containsKey('default')) {
          _body[entry.key] = entry.value['default'];
        }
      }
      _body.addAll(_seedFields(fields, widget.initial));
    }
    if (op.method == 'POST') {
      for (final key in const ['workspace_id', 'project_id', 'task_id']) {
        if (fields.containsKey(key) && widget.scope[key] != null) {
          _body[key] = widget.scope[key];
        }
      }
    }
    _showFilters =
        op.mutation ||
        validateContract(_parameterSchema('path'), {
              ...widget.scope,
              ..._path,
            }) !=
            null ||
        validateContract(_parameterSchema('query'), _query) != null;
    if (!op.mutation && !_showFilters) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _run());
    } else if (_canHydrate) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _hydrate());
    }
  }

  Future<Object?> _payload() async {
    if (!op.multipart) return _body.isEmpty ? null : _body;
    final form = FormData();
    var bytes = 0;
    for (final entry in _body.entries) {
      if (entry.value is PickedUpload) {
        final file = entry.value as PickedUpload;
        bytes += file.bytes.length;
        form.files.add(
          MapEntry(
            entry.key,
            MultipartFile.fromBytes(file.bytes, filename: file.name),
          ),
        );
      } else {
        form.fields.add(MapEntry(entry.key, '${entry.value}'));
      }
    }
    if (bytes > 3 * 1024 * 1024) {
      throw StateError('Combined file size must be at most 3 MB.');
    }
    return form;
  }

  Future<void> _run({bool more = false}) async {
    if (_loading) return;
    if (_taskTagAdd) {
      final names = '${_body['name'] ?? ''}'
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toSet();
      if ((names.isEmpty && _body['tag_id'] == null) ||
          (names.isNotEmpty && _body['tag_id'] != null) ||
          names.length > 20 ||
          names.any((s) => s.length > 100)) {
        setState(
          () => _error =
              'Choose one existing tag, or enter up to 20 names separated by commas (100 characters per name).',
        );
        _revealStatus();
        return;
      }
    }
    final error =
        validateContract(_parameterSchema('path'), {
          ...widget.scope,
          ..._path,
        }) ??
        validateContract(_parameterSchema('query'), _query) ??
        (op.mutation
            ? validateContract(
                op.body.isEmpty ? {'type': 'object'} : op.body,
                _body,
              )
            : null);
    if (error != null) {
      setState(() => _error = error);
      _revealStatus();
      return;
    }
    if (op.method == 'PATCH' && _body.isEmpty) {
      setState(() => _error = 'Choose a field to update.');
      return;
    }
    if (!op.allowed(c)) {
      setState(
        () => _error = 'Your account does not have permission for this action.',
      );
      return;
    }
    if (op.mutation) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialog) => AlertDialog(
          title: Text('Confirm ${_operationLabel(op).toLowerCase()}'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Workspace: ${c.selected?.name ?? 'Current account'}'),
                if (op.method == 'DELETE')
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text(
                      'This removes the selected record. Review the record before continuing.',
                    ),
                  ),
                ..._body.entries
                    .where(
                      (e) =>
                          e.value is! Map &&
                          e.value is! List &&
                          !RegExp(
                            'secret|token|password|api_key|session_key|request_key|client_id',
                          ).hasMatch(e.key),
                    )
                    .map(
                      (e) => Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          '${fieldLabel(e.key)}: ${e.value is PickedUpload ? (e.value as PickedUpload).name : e.value}',
                        ),
                      ),
                    ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialog, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialog, true),
              child: const Text('Confirm'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
      _notice = null;
    });
    try {
      var path = op.path;
      for (final match in RegExp(r'\{([^}]+)\}').allMatches(op.path)) {
        path = path.replaceAll(
          match.group(0)!,
          Uri.encodeComponent('${{...widget.scope, ..._path}[match.group(1)]}'),
        );
      }
      final data = await _payload();
      final oldItems = more ? records(_result) : <Json>[];
      if (more) {
        final cursor = _result is Map
            ? (_result['next_cursor'] ?? _result['next_before'])
            : null;
        final names = op.parameters.map((p) => p['name']).toSet();
        if (cursor != null) {
          _query[names.contains('before') ? 'before' : 'cursor'] = cursor;
        } else if (names.contains('skip')) {
          _query['skip'] =
              (_query['skip'] as num? ?? 0) + (_query['limit'] as num? ?? 100);
        } else if (names.contains('page')) {
          _query['page'] = (_query['page'] as num? ?? 1) + 1;
        }
      }
      dynamic result;
      if (op.download) {
        final response =
            await c.api.request(
                  op.method,
                  path,
                  data: data,
                  query: _query,
                  responseType: ResponseType.bytes,
                  returnResponse: true,
                )
                as Response;
        var bytes = (response.data as List).cast<int>();
        final location = response.headers.value('location');
        if (location != null) {
          final uri = Uri.parse(c.api.dio.options.baseUrl).resolve(location);
          if (uri.scheme != 'https') {
            throw StateError('The download did not provide a secure URL.');
          }
          final origin = Uri.parse(c.api.dio.options.baseUrl);
          if (uri.origin == origin.origin) {
            bytes =
                (await c.api.request(
                          'GET',
                          uri.toString(),
                          responseType: ResponseType.bytes,
                        )
                        as List)
                    .cast<int>();
          } else {
            // Never forward bearer credentials to a signed file host.
            bytes = (await Dio().get<List<int>>(
              uri.toString(),
              options: Options(
                responseType: ResponseType.bytes,
                followRedirects: false,
              ),
            )).data!;
          }
        }
        _download = bytes;
        final disposition = response.headers.value('content-disposition') ?? '';
        final suggested = RegExp(
          r'filename="?([^";]+)',
        ).firstMatch(disposition)?.group(1);
        _filename = (suggested ?? 'pms-${op.path.split('/').last}.bin')
            .split(RegExp(r'[/\\]'))
            .last
            .replaceAll(RegExp(r'[^a-zA-Z0-9._-]'), '_');
        result = {'file_name': _filename, 'size_bytes': bytes.length};
      } else if (_taskTagAdd &&
          _body['name'] is String &&
          (_body['name'] as String).contains(',')) {
        final tags = (_body['name'] as String)
            .split(',')
            .map((s) => s.trim())
            .where((s) => s.isNotEmpty)
            .toSet();
        final added = <dynamic>[];
        try {
          for (final name in tags) {
            added.add(
              await c.api.request(
                op.method,
                path,
                data: {..._body, 'name': name},
                query: _query,
              ),
            );
          }
        } catch (e) {
          throw ApiFailure(
            'Added ${added.length} of ${tags.length} tags. $e',
            e is ApiFailure ? e.status : null,
          );
        }
        result = {'items': added};
      } else {
        result = await c.api.request(
          op.method,
          path,
          data: data,
          query: _query,
        );
      }
      if (!mounted) return;
      setState(() {
        _result = more && oldItems.isNotEmpty
            ? {
                'items': [...oldItems, ...records(result)],
                if (result is Map) 'next_cursor': result['next_cursor'],
              }
            : result;
        if (op.mutation) _notice = 'Saved successfully.';
        _showFilters = op.mutation ? true : false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = '$e';
          if (e is ApiFailure && const {403, 404}.contains(e.status)) {
            _result = null;
            _download = null;
          }
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        _revealStatus();
      }
    }
  }

  Future<void> _saveDownload(bool share) async {
    if (_download == null || _sharing) return;
    setState(() => _sharing = true);
    try {
      if (share) {
        final directory = await getTemporaryDirectory();
        final file = File('${directory.path}/$_filename');
        await file.writeAsBytes(_download!);
        await SharePlus.instance.share(
          ShareParams(files: [XFile(file.path)], title: _filename),
        );
      } else {
        final saved = await FilePicker.saveFile(
          fileName: _filename,
          bytes: Uint8List.fromList(_download!),
        );
        if (mounted) {
          setState(
            () => _notice = saved == null
                ? 'Save cancelled.'
                : 'File saved successfully.',
          );
        }
        _revealStatus();
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _sharing = false);
    }
  }

  Future<void> _openRecord(Json row) async {
    final next = recordContext(op, row, scope, widget.catalog);
    final added = next.keys.where((k) => next[k] != scope[k]).toSet();
    final related = widget.catalog.operations
        .where(
          (candidate) =>
              candidate.available &&
              !candidate.internal &&
              !candidate.restricted &&
              candidate.allowed(c) &&
              candidate.id != op.id &&
              candidate.parameters.any(
                (p) => p['in'] == 'path' && added.contains(p['name']),
              ),
        )
        .toList();
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => Scaffold(
          appBar: AppBar(
            title: Text(
              recordTitle(row),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          body: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              PmsDataView(data: row),
              if (related.isNotEmpty) ...[
                const Divider(),
                Text(
                  'Actions & related work',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                ...related.map(
                  (action) => ListTile(
                    title: Text(_operationLabel(action)),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => PmsOperationPage(
                          controller: c,
                          catalog: widget.catalog,
                          operation: action,
                          scope: next,
                          initial: row,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
    if (!op.mutation && mounted) await _run();
  }

  @override
  Widget build(BuildContext context) {
    final rows = records(_result);
    final pathSchema = _parameterSchema('path'),
        querySchema = _parameterSchema('query');
    final hasParameters =
        (pathSchema['properties'] as Map).isNotEmpty ||
        (querySchema['properties'] as Map).isNotEmpty;
    final pagination = op.parameters.any(
      (p) => const {'skip', 'cursor', 'before', 'page'}.contains(p['name']),
    );
    return Scaffold(
      appBar: AppBar(
        title: Text(_operationLabel(op)),
        actions: [
          if (_canHydrate)
            IconButton(
              tooltip: 'Reload record',
              onPressed: _loading ? null : _hydrate,
              icon: const Icon(Icons.refresh),
            ),
          if (!op.mutation && hasParameters)
            IconButton(
              tooltip: 'Filters',
              onPressed: () => setState(() => _showFilters = !_showFilters),
              icon: const Icon(Icons.tune),
            ),
          if (!op.mutation)
            IconButton(
              tooltip: 'Refresh feature',
              onPressed: _loading ? null : () => _run(),
              icon: const Icon(Icons.refresh),
            ),
        ],
      ),
      body: Column(
        children: [
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: ListView(
              controller: _formScroll,
              padding: const EdgeInsets.all(20),
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              children: [
                if (c.selected != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Text('${c.selected!.name} · ${c.selected!.role}'),
                  ),
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: SelectableText(
                            _error!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Copy error details',
                          onPressed: () =>
                              Clipboard.setData(ClipboardData(text: _error!)),
                          icon: const Icon(Icons.copy),
                        ),
                      ],
                    ),
                  ),
                if (_stableTypeName)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Text(
                      'Task type ${_initial['name'] ?? ''}: names are stable identifiers. Create another type to use a different name.',
                    ),
                  ),
                if (_taskTagAdd)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 16),
                    child: Text(
                      'Enter tag names separated by commas, or choose one existing tag.',
                    ),
                  ),
                if (_notice != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Text(_notice!),
                  ),
                if (_showFilters)
                  Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ContractFields(
                          schema: pathSchema,
                          values: _path,
                          onChanged: (v) {
                            setState(() => _path = v);
                            _hydrate();
                          },
                          onReferenceSelected: (key, row) {
                            final paths = op.parameters
                                .where((p) => p['in'] == 'path')
                                .toList();
                            if (op.mutation &&
                                !_canHydrate &&
                                paths.isNotEmpty &&
                                paths.last['name'] == key) {
                              setState(() => _acceptRecord(row));
                            }
                          },
                          controller: c,
                          scope: scope,
                          disabled: _loading,
                        ),
                        ContractFields(
                          schema: querySchema,
                          values: _query,
                          onChanged: (v) => setState(() => _query = v),
                          controller: c,
                          scope: scope,
                          disabled: _loading,
                        ),
                        if (op.mutation)
                          ContractFields(
                            key: ValueKey('edit-record-$_recordGeneration'),
                            schema: _formBody,
                            preserveNulls: const {
                              'PATCH',
                              'PUT',
                            }.contains(op.method),
                            values: _body,
                            initial: _initial,
                            onChanged: (v) => setState(() => _body = v),
                            controller: c,
                            scope: scope,
                            disabled: _loading,
                          ),
                        FilledButton(
                          onPressed: _loading || _editUnavailable
                              ? null
                              : () => _run(),
                          child: Text(
                            _loading
                                ? 'Working…'
                                : op.mutation
                                ? 'Save'
                                : 'Apply filters',
                          ),
                        ),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                if (_download != null)
                  Wrap(
                    spacing: 12,
                    children: [
                      FilledButton.icon(
                        onPressed: _sharing ? null : () => _saveDownload(false),
                        icon: const Icon(Icons.save_alt),
                        label: const Text('Save file'),
                      ),
                      OutlinedButton.icon(
                        onPressed: _sharing ? null : () => _saveDownload(true),
                        icon: const Icon(Icons.share),
                        label: const Text('Share file'),
                      ),
                    ],
                  ),
                if (rows.isNotEmpty) ...[
                  Text(
                    '${rows.length} records',
                    style: Theme.of(context).textTheme.labelLarge,
                  ),
                  for (final row in rows)
                    Card(
                      child: ListTile(
                        title: Text(
                          recordTitle(row),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(
                          [
                            row['task_key'],
                            row['status'],
                            row['priority'],
                            row['role'],
                            row['created_at'],
                            row['due_date'],
                          ].where((v) => v != null).join(' · '),
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _openRecord(row),
                      ),
                    ),
                  if (pagination)
                    TextButton(
                      onPressed: _loading ? null : () => _run(more: true),
                      child: const Text('Load more'),
                    ),
                ] else if (_result != null)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      PmsDataView(data: _result),
                      if (_result is Map &&
                          (_result['id'] != null ||
                              _result['confirmation_hash'] != null ||
                              _result['approval_hash'] != null))
                        OutlinedButton(
                          onPressed: () =>
                              _openRecord(Map<String, dynamic>.from(_result)),
                          child: const Text('Record actions'),
                        ),
                    ],
                  )
                else if (!_loading && !_showFilters)
                  const Text('No records yet.'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class PmsDataView extends StatelessWidget {
  const PmsDataView({super.key, required this.data, this.depth = 0});
  final dynamic data;
  final int depth;
  @override
  Widget build(BuildContext context) {
    if (data == null) return const SizedBox.shrink();
    if (data is List) {
      if ((data as List).isEmpty) return const Text('No records yet.');
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final value in data)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: PmsDataView(data: value, depth: depth + 1),
                ),
              ),
            ),
        ],
      );
    }
    if (data is Map) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final entry in (data as Map).entries)
            if (entry.value != null &&
                entry.value != '' &&
                !RegExp(
                  'secret|password|access_token|refresh_token|api_key|token_hash',
                ).hasMatch('${entry.key}'))
              entry.value is Map || entry.value is List
                  ? ExpansionTile(
                      title: Text(fieldLabel('${entry.key}')),
                      initiallyExpanded: depth < 1,
                      children: [
                        PmsDataView(data: entry.value, depth: depth + 1),
                      ],
                    )
                  : Padding(
                      padding: const EdgeInsets.symmetric(vertical: 7),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            fieldLabel('${entry.key}'),
                            style: Theme.of(context).textTheme.labelMedium,
                          ),
                          SelectableText(
                            entry.value is bool
                                ? entry.value
                                      ? 'Yes'
                                      : 'No'
                                : '${entry.value}',
                          ),
                        ],
                      ),
                    ),
        ],
      );
    }
    return SelectableText('$data');
  }
}
