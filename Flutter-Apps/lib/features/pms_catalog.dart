import 'dart:convert';
import 'package:flutter/services.dart';
import '../core/models.dart';
import '../app_controller.dart';

String fieldLabel(String key) {
  key = key.replaceAllMapped(
    RegExp(r'([a-z])([A-Z])'),
    (m) => '${m[1]}_${m[2]!.toLowerCase()}',
  );
  const labels = {
    'wid': 'Workspace',
    'rid': 'Conversation',
    'mid': 'Message',
    'fid': 'Form',
    'did': 'Dashboard',
    'id': 'Record',
    'body': 'Message',
    'log_date': 'Date',
    'is_completed': 'Completed',
    'is_billable': 'Billable',
    'duration_minutes': 'Minutes',
  };
  if (labels.containsKey(key)) return labels[key]!;
  final text = key.replaceAll(RegExp(r'_ids?$'), '').replaceAll('_', ' ');
  return text.isEmpty ? key : '${text[0].toUpperCase()}${text.substring(1)}';
}

List<Json> records(dynamic data) {
  if (data is List) {
    return data
        .map(
          (e) => e is Map
              ? Map<String, dynamic>.from(e)
              : <String, dynamic>{'value': e},
        )
        .toList();
  }
  if (data is Map) {
    for (final key in [
      'items',
      'data',
      'results',
      'messages',
      'conversations',
      'tasks',
      'projects',
      'entries',
      'teams',
      'documents',
      'forms',
      'events',
      'rows',
      'notifications',
      'rules',
      'savepoints',
      'archives',
      'views',
      'reports',
      'links',
      'users',
      'fields',
      'members',
      'columns',
      'departments',
      'branches',
    ]) {
      if (data[key] is List) return records(data[key]);
    }
  }
  return [];
}

String recordTitle(Json row) {
  for (final key in [
    'title',
    'name',
    'subject',
    'label',
    'summary',
    'email',
    'body',
    'description',
    'filename',
    'file_name',
    'task_key',
    'action',
    'value',
  ]) {
    if (row[key] != null && '${row[key]}'.isNotEmpty) return '${row[key]}';
  }
  return row['id'] == null ? 'Details' : 'Record ${row['id']}';
}

class PmsOperation {
  PmsOperation(this.json);
  final Json json;
  String get id => json['id'];
  String get method => json['method'];
  String get path => json['path'];
  String get title => json['title'];
  String get area => json['area'];
  bool get available => json['available'] == true;
  bool get internal => json['internal'] == true;
  bool get restricted => json['restricted'] == true;
  bool get download => json['download'] == true;
  bool get mutation => method != 'GET';
  Json get body => Map<String, dynamic>.from(json['body'] as Map);
  List<Json> get parameters => (json['parameters'] as List).cast<Json>();
  bool get multipart => json['mime'] == 'multipart/form-data';
  bool get administratorOnly =>
      restricted ||
      path.contains('/recovery') ||
      path.contains('/automations') ||
      path.contains('/forms') ||
      path.contains('/tools') ||
      path.contains('/members') ||
      path.contains('/invitations') ||
      path.contains('/custom-fields') ||
      path.contains('/task-types') ||
      path.contains('/tag-manager') ||
      path.contains('/dev-integrations') ||
      path.endsWith('/approve') ||
      path.endsWith('/reject') ||
      path.contains('/commercial') ||
      path.contains('/invoices') ||
      path.contains('/payments');
  bool allowed(AppController c) {
    final invoicePermissions = path.endsWith('/billing')
        ? const {
            'srm_invoice_view',
            'srm_invoice_create',
            'srm_invoice_approve',
            'srm_admin',
          }
        : (path.endsWith('/billing/sources') ||
              path.endsWith('/projects/{project_id}/invoices'))
        ? const {'srm_invoice_create', 'srm_admin'}
        : null;
    if (invoicePermissions != null &&
        c.user?.isSuperuser != true &&
        (c.user?.permissions.intersection(invoicePermissions).isEmpty ??
            true)) {
      return false;
    }
    return restricted
        ? c.user?.isSuperuser == true
        : (!mutation ||
              (c.selected?.canEdit == true &&
                  (!administratorOnly || c.selected?.canManage == true)));
  }
}

class PmsCatalog {
  PmsCatalog(this.operations);
  final List<PmsOperation> operations;
  static Future<PmsCatalog>? _pending;
  static Future<PmsCatalog> load() => _pending ??= _load();
  static Future<PmsCatalog> _load() async {
    final json =
        jsonDecode(await rootBundle.loadString('assets/pms_catalog.json'))
            as Json;
    return PmsCatalog(
      (json['operations'] as List).map((e) => PmsOperation(e as Json)).toList(),
    );
  }

  PmsOperation? find(String method, String path) =>
      operations.where((o) => o.method == method && o.path == path).firstOrNull;
}

Map<String, dynamic> baseContext(
  AppController c, {
  Project? project,
  WorkTask? task,
}) => {
  if (c.selected != null) ...{
    'workspace_id': c.selected!.id,
    'wid': c.selected!.id,
  },
  if (project != null || task != null)
    'project_id': project?.id ?? task!.projectId,
  if (task != null) 'task_id': task.id,
};

Map<String, dynamic> recordContext(
  PmsOperation operation,
  Json row,
  Map<String, dynamic> parent,
  PmsCatalog catalog,
) {
  final context = <String, dynamic>{...parent};
  for (final key in row.keys) {
    if (key.endsWith('_hash') ||
        const {'version', 'session_key'}.contains(key)) {
      context[key] = row[key];
    }
  }
  for (final key in row.keys) {
    if (key.endsWith('_id') && row[key] != null) context[key] = row[key];
  }
  final segment = operation.path.split('/').last;
  const aliases = {
    'projects': 'project_id',
    'tasks': 'task_id',
    'sprints': 'sprint_id',
    'epics': 'epic_id',
    'releases': 'release_id',
    'milestones': 'milestone_id',
    'components': 'component_id',
    'comments': 'comment_id',
    'checklists': 'item_id',
    'checklist': 'item_id',
    'risks': 'risk_id',
    'time-logs': 'time_log_id',
    'timesheets': 'timesheet_id',
    'saved-views': 'view_id',
    'saved-filters': 'filter_id',
    'tags': 'tag_id',
    'task-types': 'type_id',
    'docs': 'document_id',
    'dashboards': 'did',
    'forms': 'fid',
    'teams': 'team_id',
    'members': 'member_id',
    'invitations': 'invitation_id',
    'automations': 'rule_id',
    'tools': 'tool_id',
    'events': 'event_id',
    'files': 'file_id',
    'attachments': 'file_id',
    'conversations': 'conversation_id',
    'messages': 'mid',
    'clients': 'client_id',
    'intake': 'intake_id',
    'dev-integrations': 'integration_id',
    'savepoints': 'point_id',
  };
  if (row['id'] != null) {
    if (aliases[segment] != null) context[aliases[segment]!] = row['id'];
    if (segment == 'conversations' && operation.path.contains('/chat/')) {
      context['rid'] = row['id'];
    }
    for (final candidate in catalog.operations) {
      if (candidate.path.startsWith('${operation.path}/{')) {
        final key = candidate.path
            .substring(operation.path.length + 2)
            .split('}')
            .first;
        context[key] = row['id'];
      }
    }
  }
  if (row['key'] != null) context['key'] = row['key'];
  return context;
}

Future<List<Json>> referenceOptions(
  String field,
  Map<String, dynamic> context,
  AppController c,
) async {
  final canonical = const {
    'projectId': 'project_id',
    'taskId': 'task_id',
    'workspaceId': 'workspace_id',
    'sprintId': 'sprint_id',
    'epicId': 'epic_id',
    'assigneeId': 'assignee_user_id',
    'reporterId': 'reporter_user_id',
  }[field];
  if (canonical != null) return referenceOptions(canonical, context, c);
  if (field == 'workspace_id' || field == 'wid') {
    return c.workspaces.map((w) => {'id': w.id, 'name': w.name}).toList();
  }
  if (field == 'project_id') {
    return (c.overview?.projects ?? [])
        .map((p) => {'id': p.id, 'name': p.name})
        .toList();
  }
  if (field == 'task_id' ||
      field == 'linked_task_id' ||
      field == 'parent_task_id' ||
      field == 'depends_on_task_id' ||
      field == 'predecessor_task_id' ||
      field == 'successor_task_id') {
    return (c.overview?.tasks ?? [])
        .where(
          (t) =>
              context['project_id'] == null ||
              t.projectId == context['project_id'],
        )
        .map((t) => {'id': t.id, 'name': '${t.key} · ${t.title}'})
        .toList();
  }
  if (const {'source_task_id', 'target_task_id'}.contains(field)) {
    return referenceOptions('task_id', context, c);
  }
  if (const {'assignee_id', 'manager_id', 'owner_id'}.contains(field)) {
    return referenceOptions('user_id', context, c);
  }
  if (field.contains('user_id') || field == 'person_id' || field == 'uid') {
    final rows = await c.repository.members(
      context['workspace_id'] ?? c.selected!.id,
    );
    return rows.map((r) => {'id': r['user_id'], 'name': r['email']}).toList();
  }
  final project = context['project_id'];
  if (field == 'member_id') {
    final people = await c.repository.members(
      context['workspace_id'] ?? c.selected!.id,
    );
    final rows =
        '${context['operation_path']}'.contains('/projects/') && project != null
        ? records(
            await c.api.request(
              'GET',
              '/project-management/projects/$project/members',
            ),
          )
        : people;
    return rows
        .map(
          (r) => {
            'id': r['id'],
            'name':
                r['email'] ??
                people
                    .where((p) => p['user_id'] == r['user_id'])
                    .firstOrNull?['email'] ??
                'User ${r['user_id']}',
            'record': r,
          },
        )
        .toList();
  }
  if (const {
        'item_id',
        'comment_id',
        'dependency_id',
        'attachment_id',
      }.contains(field) &&
      context['task_id'] != null) {
    final segment = const {
      'item_id': 'checklists',
      'comment_id': 'comments',
      'dependency_id': 'dependencies',
      'attachment_id': 'attachments',
    }[field];
    final collection =
        field == 'item_id' &&
            '${context['operation_path']}'.contains('/subtasks')
        ? 'subtasks'
        : segment;
    final result = await c.api.request(
      'GET',
      '/project-management/tasks/${context['task_id']}/$collection',
    );
    return records(
      result,
    ).map((r) => {'id': r['id'], 'name': recordTitle(r), 'record': r}).toList();
  }
  const collections = {
    'custom_field_id': 'custom-fields',
    'sprint_id': 'sprints',
    'epic_id': 'epics',
    'release_id': 'releases',
    'milestone_id': 'milestones',
    'component_id': 'components',
    'document_id': 'docs',
    'field_id': 'custom-fields',
  };
  String? path;
  if (collections[field] != null && project != null) {
    path = '/project-management/projects/$project/${collections[field]}';
  }
  const globals = {
    'risk_id': 'risks',
    'tag_id': 'tags',
    'type_id': 'task-types',
    'client_id': 'clients',
    'customer_id': 'business/customers',
    'invoice_id': 'business/collection-invoices',
    'timesheet_id': 'timesheets',
    'time_log_id': 'time-logs',
    'file_id': 'files',
    'did': 'dashboards',
    'view_id': 'saved-views',
  };
  if (globals[field] != null) path = '/project-management/${globals[field]}';
  if (field == 'department_id' || field == 'branch_id') {
    path = field == 'department_id' ? '/org/departments' : '/org/branches';
  }
  if (field == 'rule_id' ||
      field == 'tool_id' ||
      field == 'point_id' ||
      field == 'invitation_id') {
    final collection = {
      'rule_id': 'automations',
      'tool_id': 'tools',
      'point_id': 'recovery',
      'invitation_id': 'invitations',
    }[field];
    path =
        '/project-management/workspaces/${context['workspace_id']}/$collection';
  }
  if (field == 'filter_id' && project != null) {
    path = '/project-management/projects/$project/saved-filters';
  }
  if (field == 'integration_id') path = '/project-management/dev-integrations';
  if (field == 'event_id') path = '/project-management/planner/events';
  if (field == 'rid' || field == 'conversation_id') {
    path =
        '/project-management/workspaces/${context['workspace_id']}/chat/conversations';
  }
  if (field == 'fid') {
    path = '/project-management/workspaces/${context['workspace_id']}/forms';
  }
  if (field == 'team_id') {
    path = '/project-management/workspaces/${context['workspace_id']}/teams';
  }
  if (field == 'column_id' && project != null) {
    final board = await c.api.request(
      'GET',
      '/project-management/projects/$project/board',
    );
    return records(
      board['columns'],
    ).map((r) => {'id': r['id'], 'name': r['name'] ?? r['title']}).toList();
  }
  if (path == null) return [];
  final result = await c.api.request('GET', path);
  return records(
    result,
  ).map((r) => {'id': r['id'], 'name': recordTitle(r), 'record': r}).toList();
}
